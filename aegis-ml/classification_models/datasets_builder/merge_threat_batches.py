"""
Merge script: combines original m2_threat_v2.csv with all augmented batches.
Deduplicates on text, shuffles, and saves final m2_threat_v4.csv
"""
import csv, os, random

BASE_DIR = os.path.dirname(__file__)
random.seed(42)

SOURCES = [
    "m2_threat_v2.csv",
    "m2_threat_augmented.csv",  # batch 1
    "threat_batch2.csv",
    "threat_batch3.csv",
    "threat_batch4.csv",
    "threat_batch5.csv",
    "threat_batch6.csv",
    "threat_batch7.csv",
]

OUTPUT = os.path.join(BASE_DIR, "m2_threat_v4.csv")
FIELDNAMES = ["text", "label", "language", "source_dataset", "routing_method"]

all_rows = []
seen_texts = set()

for fname in SOURCES:
    path = os.path.join(BASE_DIR, fname)
    if not os.path.exists(path):
        print(f"  MISSING: {fname} — skipping")
        continue
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count_before = len(all_rows)
        for row in reader:
            txt = row.get("text", "").strip().lower()
            if txt and txt not in seen_texts:
                seen_texts.add(txt)
                # Normalise columns
                clean = {
                    "text": row["text"].strip(),
                    "label": row.get("label", "threat"),
                    "language": row.get("language", "en"),
                    "source_dataset": row.get("source_dataset", fname),
                    "routing_method": row.get("routing_method", "manual"),
                }
                all_rows.append(clean)
        added = len(all_rows) - count_before
        print(f"  {fname}: +{added} rows (dupes dropped)")

print(f"\nTotal unique rows: {len(all_rows)}")

# Shuffle
random.shuffle(all_rows)

# Write
with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
    writer.writeheader()
    writer.writerows(all_rows)

print(f"Saved: {OUTPUT}")

# Summary by source
from collections import Counter
sources = Counter(r["source_dataset"] for r in all_rows)
print("\nBreakdown by source:")
for k, v in sorted(sources.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")
