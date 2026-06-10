"""
AGENT 1 & 2: Gatekeeper + Classifier

Runs the ML pipeline (M1 toxicity + M2 classification), then evaluates
whether the message needs to be sent to Agent 3 (the Groq Auditor).

Language-aware routing:
  - English/other → XLM-R M1 + DeBERTa M2 (existing pipeline)
  - Darija → DarijaBERT-mix M1D (Darija-native pipeline)
             All M1D-flagged messages go to Agent 3 for severity classification.

Extracted from graph.py during Phase 2 audit refactoring (2026-04-21).
"""
import logging

from .state import (
    ModerationState,
    SHADOW_LOW, SHADOW_HIGH,
    ESCALATION_AUDIT_THRESHOLD,
)
from .escalation import compute_escalation_risk

logger = logging.getLogger(__name__)


def _detect_darija_script(text: str) -> str:
    """
    Classify a Darija message's script type.
    Returns: 'arabic', 'arabizi', or 'mixed'.
    """
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    latin_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    arabizi_digits = sum(1 for c in text if c in "235789")

    if arabic_chars >= 2 and latin_chars >= 2:
        return 'mixed'
    elif arabic_chars >= 2:
        return 'arabic'
    elif arabizi_digits >= 1 or latin_chars >= 2:
        return 'arabizi'
    return 'arabic'  # default


def ml_pipeline_node(state: ModerationState) -> dict:
    """
    AGENT 1 & 2: Gatekeeper + Classifier
    With language-aware routing: Darija → M1D, English → M1+M2.
    """
    import time as _time
    _t_start = _time.time()

    raw_text = state["raw_text"]

    # ── Language Detection ────────────────────────────────────────────
    from ml_pipeline.models_pkg.language_detector import detect_language, is_likely_darija
    lang_code = detect_language(raw_text)
    is_darija = is_likely_darija(raw_text, lang_code)
    darija_script = _detect_darija_script(raw_text) if is_darija else None

    # ── Pipeline Routing ──────────────────────────────────────────────
    from django.conf import settings
    stub_mode = getattr(settings, 'AEGIS_STUB_MODE', False)

    if is_darija and not stub_mode:
        # 🇲🇦 DARIJA TRACK — try DarijaBERT-mix M1D
        from ml_pipeline.models_pkg.darija_inference import DarijaPipeline, run_darija_pipeline
        darija_pipeline = DarijaPipeline.get_instance()

        if darija_pipeline is not None:
            logger.info(
                f"[GATEKEEPER] 🇲🇦 Darija detected (lang={lang_code}, script={darija_script}) "
                f"→ routing to M1D DarijaBERT"
            )
            result = run_darija_pipeline(raw_text)
        else:
            # M1D not loaded → fall back to English pipeline (will underperform)
            logger.warning(
                f"[GATEKEEPER] ⚠️ Darija detected but M1D not available. "
                f"Falling back to English pipeline (lang={lang_code})."
            )
            from ml_pipeline.inference import run_pipeline, run_pipeline_stub
            _pipeline_fn = run_pipeline_stub if stub_mode else run_pipeline
            result = _pipeline_fn(raw_text)
            is_darija = False  # Mark as not-routed for state tracking
    else:
        # 🇬🇧 ENGLISH TRACK — existing M1/M2
        logger.info(
            f"[GATEKEEPER] 🇬🇧 English track (lang={lang_code}, is_darija={is_darija}) "
            f"→ routing to M1+M2 XLM-R"
        )
        from ml_pipeline.inference import run_pipeline, run_pipeline_stub
        _pipeline_fn = run_pipeline_stub if stub_mode else run_pipeline
        result = _pipeline_fn(raw_text)

    # --- Behavioral Escalation Gate ---
    escalation_risk, escalation_reason = compute_escalation_risk(
        state["sender_jid"], state["instance_name"], result.m1_score
    )

    # Evaluate Auditor Triggers
    needs_audit = False
    audit_reason = ""

    # ✅ TRUST-BUT-VERIFY: ALL non-ALLOW decisions go to Agent 3
    if result.decision != 'ALLOW':
        needs_audit = True
        # Darija-flagged messages get a specific audit reason
        if is_darija:
            audit_reason = "darija-flagged"
        else:
            audit_reason = "ml-flagged"

    # 🚨 ESCALATION GATE: Safe-looking message but behavioral pattern is alarming
    elif escalation_risk >= ESCALATION_AUDIT_THRESHOLD:
        needs_audit = True
        audit_reason = f"escalation-gate({escalation_risk:.2f}): {escalation_reason}"
        logger.warning(
            f"[ESCALATION GATE] 🚨 Triggered for {state['sender_jid']} "
            f"(score={escalation_risk:.2f}): {escalation_reason}"
        )

    # SHADOW REVIEW: Borderline safe messages
    elif result.decision == 'ALLOW' and SHADOW_LOW <= result.m1_score <= SHADOW_HIGH:
        word_count = len(raw_text.strip().split())
        # Short messages (≤3 words) with very low toxicity are almost certainly
        # greetings/filler ("supp", "yoo bro", "haha ok") — skip the expensive LLM call.
        if word_count <= 3 and result.m1_score < 0.15:
            needs_audit = False
        else:
            needs_audit = True
            audit_reason = "shadow-zone"

    # Store the raw ML decision BEFORE any potential Agent 3 override
    ml_original_decision = result.decision
    ml_original_class = result.primary_class

    # ── IMAGE FLAG OVERRIDE ──────────────────────────────────────────
    # If ViT detected NSFW or violence in an image, the text-based ML models
    # will still see the injected "[IMAGE FLAGGED: ...]" tag as safe text.
    # Override the ML decision so image-flagged messages reach Agent 3 and
    # the Enforcer with the correct severity.
    image_override_decision = result.decision
    image_override_class = result.primary_class
    image_needs_audit = needs_audit

    if state.get("image_nsfw", False):
        image_override_decision = "BLOCK"
        image_override_class = "nsfw_image"
        image_needs_audit = True
        audit_reason = "image-flagged-nsfw"
        logger.info("[GATEKEEPER] 📸 Image NSFW override → BLOCK / nsfw_image")
    elif state.get("image_violent", False):
        image_override_decision = "BLOCK"
        image_override_class = "violent_image"
        image_needs_audit = True
        audit_reason = "image-flagged-violence"
        logger.info("[GATEKEEPER] 📸 Image violence override → BLOCK / violent_image")

    _t_elapsed = int((_time.time() - _t_start) * 1000)

    return {
        "normalized_text": result.normalized_text,
        "m1_score": result.m1_score,
        "is_harmful": result.is_harmful,
        "primary_class": image_override_class,
        "secondary_class": getattr(result, "secondary_class", None),
        "m2_confidence": result.m2_confidence,
        "decision": image_override_decision,
        "needs_audit": image_needs_audit,
        "ml_original_decision": ml_original_decision,
        "ml_original_class": ml_original_class,
        "ml_corrected": False,
        "escalation_risk": escalation_risk,
        "escalation_reason": escalation_reason,
        "agent_1_2_latency_ms": _t_elapsed,
        # Darija routing metadata
        "detected_language": lang_code,
        "is_darija": is_darija,
        "darija_script": darija_script,
    }
