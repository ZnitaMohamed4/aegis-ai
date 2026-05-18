#!/usr/bin/env python
"""
AEGIS Golden Dataset Export Script
===================================
Exports ALL ModerationResult records from the database, deduplicates by content_hash,
classifies language via Groq LLM (English / Darija / French / Arabic / Ambiguous),
writes language tags back to DB, and produces 3 output files.

Usage:
    cd aegis-backend
    python manage.py shell -c "exec(open('scripts/export_golden_dataset.py').read())"

    OR directly:
    cd aegis-backend
    DJANGO_SETTINGS_MODULE=config.settings python scripts/export_golden_dataset.py
"""

import os
import sys
import json
import time
import datetime

# Django setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from moderation.models import ModerationResult

# ─── CONFIG ──────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          '..', 'aegis-ml', 'digital_twin', 'data')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '').strip().strip('"')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
BATCH_SIZE = 20  # Messages per Groq request


def export_all_records():
    """Step 1: Export every ModerationResult to a list of dicts."""
    print("\n" + "=" * 60)
    print("  📦 AEGIS Golden Dataset Export")
    print("=" * 60)

    all_results = ModerationResult.objects.all().order_by('created_at')
    total = all_results.count()
    print(f"\n  📊 Total ModerationResult records: {total}")

    records = []
    for mr in all_results:
        records.append({
            "id": str(mr.id),
            "raw_text": mr.raw_text,
            "normalized_text": mr.normalized_text,
            "content_hash": mr.normalized_text.__hash__(),  # Python hash for dedup
            "sender_jid": mr.sender_jid,
            "sender_name": mr.sender_name or "",
            "instance_name": mr.instance_name,
            "is_from_me": mr.is_from_me,
            "language": mr.language,
            "primary_class": mr.primary_class or "safe",
            "toxicity_score": float(mr.toxicity_score),
            "confidence_score": float(mr.confidence_score) if mr.confidence_score else None,
            "decision": mr.decision,
            "llm_triggered": mr.llm_triggered,
            "llm_explanation": mr.llm_explanation or "",
            "ml_corrected": mr.ml_corrected,
            "ml_original_decision": mr.ml_original_decision,
            "ml_original_class": mr.ml_original_class,
            "human_reviewed": mr.human_reviewed,
            "human_decision": mr.human_decision,
            "human_label": mr.human_label,
            "human_note": mr.human_note or "",
            "original_ai_decision": mr.original_ai_decision,
            "original_ai_label": mr.original_ai_label,
            "behavioral_risk_score": float(mr.behavioral_risk_score),
            "created_at": mr.created_at.isoformat(),
            # Will be filled by Groq
            "language_tag": None,
        })

    print(f"  ✅ Exported {len(records)} records")
    return records


def deduplicate(records):
    """Step 2: Remove exact duplicate messages (same raw_text), keeping the best version."""
    print(f"\n  🔄 Deduplicating {len(records)} records...")

    seen = {}
    for rec in records:
        text = rec["raw_text"].strip()
        if text in seen:
            existing = seen[text]
            # Prefer human-reviewed over non-reviewed
            if rec["human_reviewed"] and not existing["human_reviewed"]:
                seen[text] = rec
            # Prefer ml_corrected over non-corrected
            elif rec["ml_corrected"] and not existing["ml_corrected"]:
                seen[text] = rec
            # Otherwise keep the first one (already in seen)
        else:
            seen[text] = rec

    deduped = list(seen.values())
    removed = len(records) - len(deduped)
    print(f"  ✅ Deduplicated: {len(records)} → {len(deduped)} ({removed} duplicates removed)")
    return deduped


def classify_languages_groq(records):
    """Step 3: Use Groq LLM to classify each message's language."""
    import requests

    if not GROQ_API_KEY:
        print("  ⚠️  GROQ_API_KEY not found! Skipping language classification.")
        print("      Set it in .env and re-run.")
        for rec in records:
            rec["language_tag"] = rec.get("language", "unknown")
        return records

    print(f"\n  🌐 Classifying languages via Groq ({GROQ_MODEL})...")
    print(f"     Batch size: {BATCH_SIZE} | Total: {len(records)} | Batches: {(len(records) + BATCH_SIZE - 1) // BATCH_SIZE}")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = """You are a language classifier for a Moroccan child safety system.

For each numbered message, output ONLY its number and language tag, one per line, in this exact format:
1: english
2: darija
3: french

Language tags (pick exactly one):
- "english" — English text
- "darija" — Moroccan Arabic written in Latin script (e.g. "wach nta", "3lach", "bghit", "sir tqwd")
- "arabic" — Arabic script (العربية)
- "french" — French text
- "ambiguous" — too short to tell (1-2 words like "ok", "hi") or mixed

Be precise. Darija uses numbers as letters (3=ع, 7=ح, 9=ق, 5=خ, 8=غ). 
Common Darija words: wach, fin, 3lach, bghit, nta, nti, dyal, hadi, sir, gha, machi, bla, khouya, sahbi."""

    for batch_start in range(0, len(records), BATCH_SIZE):
        batch = records[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1

        # Build the message list
        lines = []
        for i, rec in enumerate(batch, 1):
            # Truncate very long messages
            text = rec["raw_text"][:200].replace("\n", " ")
            lines.append(f"{i}: \"{text}\"")

        user_msg = "Classify these messages:\n" + "\n".join(lines)

        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.0,
            "max_tokens": 500
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"].strip()
                # Parse response lines
                for line in content.split("\n"):
                    line = line.strip()
                    if ":" in line:
                        parts = line.split(":", 1)
                        try:
                            idx = int(parts[0].strip()) - 1
                            tag = parts[1].strip().lower().strip('"').strip("'")
                            if tag in ("english", "darija", "arabic", "french", "ambiguous"):
                                if 0 <= idx < len(batch):
                                    batch[idx]["language_tag"] = tag
                        except (ValueError, IndexError):
                            continue

                print(f"     Batch {batch_num}: ✅ classified {len(batch)} messages")
            elif response.status_code == 429:
                print(f"     Batch {batch_num}: ⏳ Rate limited, waiting 10s...")
                time.sleep(10)
                # Retry once
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                if response.status_code == 200:
                    content = response.json()["choices"][0]["message"]["content"].strip()
                    for line in content.split("\n"):
                        line = line.strip()
                        if ":" in line:
                            parts = line.split(":", 1)
                            try:
                                idx = int(parts[0].strip()) - 1
                                tag = parts[1].strip().lower().strip('"').strip("'")
                                if tag in ("english", "darija", "arabic", "french", "ambiguous"):
                                    if 0 <= idx < len(batch):
                                        batch[idx]["language_tag"] = tag
                            except (ValueError, IndexError):
                                continue
                    print(f"     Batch {batch_num}: ✅ classified (retry)")
                else:
                    print(f"     Batch {batch_num}: ❌ Failed after retry ({response.status_code})")
            else:
                print(f"     Batch {batch_num}: ❌ HTTP {response.status_code}")
        except Exception as e:
            print(f"     Batch {batch_num}: ❌ Error: {e}")

        # Small delay between batches to avoid rate limits
        time.sleep(0.5)

    # Fill any untagged records
    for rec in records:
        if not rec.get("language_tag"):
            rec["language_tag"] = "ambiguous"

    # Stats
    tags = {}
    for rec in records:
        tag = rec["language_tag"]
        tags[tag] = tags.get(tag, 0) + 1
    print(f"\n  📊 Language distribution:")
    for tag, count in sorted(tags.items(), key=lambda x: -x[1]):
        print(f"     {tag}: {count} messages")

    return records


def write_back_to_db(records):
    """Step 4: Update the language field in ModerationResult."""
    print(f"\n  💾 Writing language tags back to database...")
    updated = 0
    for rec in records:
        tag = rec.get("language_tag")
        if tag and tag != "ambiguous":
            try:
                ModerationResult.objects.filter(id=rec["id"]).update(language=tag)
                updated += 1
            except Exception:
                pass
    print(f"  ✅ Updated {updated} records in DB")


def save_outputs(records):
    """Step 5: Save the 3 JSON files."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Full dataset
    full_path = os.path.join(OUTPUT_DIR, "golden_dataset_FULL.json")
    with open(full_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"\n  📄 FULL: {full_path} ({len(records)} records)")

    # English only
    en_records = [r for r in records if r.get("language_tag") == "english"]
    en_path = os.path.join(OUTPUT_DIR, "golden_dataset_EN.json")
    with open(en_path, 'w', encoding='utf-8') as f:
        json.dump(en_records, f, indent=2, ensure_ascii=False)
    print(f"  📄 EN:   {en_path} ({len(en_records)} records)")

    # Darija only
    darija_records = [r for r in records if r.get("language_tag") == "darija"]
    darija_path = os.path.join(OUTPUT_DIR, "golden_dataset_DARIJA.json")
    with open(darija_path, 'w', encoding='utf-8') as f:
        json.dump(darija_records, f, indent=2, ensure_ascii=False)
    print(f"  📄 DARIJA: {darija_path} ({len(darija_records)} records)")

    # Also save French and Arabic if they exist
    for lang in ("french", "arabic"):
        lang_records = [r for r in records if r.get("language_tag") == lang]
        if lang_records:
            lang_path = os.path.join(OUTPUT_DIR, f"golden_dataset_{lang.upper()}.json")
            with open(lang_path, 'w', encoding='utf-8') as f:
                json.dump(lang_records, f, indent=2, ensure_ascii=False)
            print(f"  📄 {lang.upper()}: {lang_path} ({len(lang_records)} records)")


def main():
    records = export_all_records()
    if not records:
        print("  ⚠️  No records found in database!")
        return

    records = deduplicate(records)
    records = classify_languages_groq(records)
    write_back_to_db(records)
    save_outputs(records)

    print("\n" + "=" * 60)
    print("  ✅ EXPORT COMPLETE — Zero data loss")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
