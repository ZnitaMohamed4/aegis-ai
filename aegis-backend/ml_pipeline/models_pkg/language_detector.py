"""
Language detection for the AEGIS pipeline using fasttext lid.176.

Detects 176 languages in <1ms per message. The model is loaded once
at module import time (lazy singleton) and reused for all subsequent calls.

Primary use:
  - Populate `detected_language` in the pipeline state
  - Power the admin dashboard language distribution chart
  - Enable future Darija routing (Arabic-script Darija → Agent 3 bypass)
"""
import logging
import os

logger = logging.getLogger(__name__)

# Lazy singleton — model loaded on first call
_model = None

# Default model path (can be overridden via .env)
_DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "trained_models", "fasttext", "lid.176.bin",
)

# fasttext language codes → human-friendly labels
# fasttext uses ISO 639-1 two-letter codes (e.g. "en", "fr", "ar")
# We keep them as-is for simplicity.
_DARIJA_MARKERS = {"ar", "fr", "id", "es", "it", "ms", "tr"}  # Languages Darija is commonly misclassified as


def _get_model():
    """Lazy-load the fasttext model on first use."""
    global _model
    if _model is None:
        import fasttext
        # Suppress fasttext's "Warning: loss/dict/..." startup noise
        fasttext.FastText.eprint = lambda x: None
        model_path = os.getenv("FASTTEXT_MODEL_PATH", _DEFAULT_MODEL_PATH)
        if not os.path.exists(model_path):
            logger.error("fasttext model not found at %s", model_path)
            return None
        _model = fasttext.load_model(model_path)
        logger.info("fasttext lid.176 loaded from %s", model_path)
    return _model


def detect_language(text: str) -> str:
    """
    Detect the language of a text message.

    Returns:
        ISO 639-1 code (e.g. "en", "fr", "ar") or "unknown" if detection fails.
    """
    if not text or not text.strip():
        return "unknown"

    model = _get_model()
    if model is None:
        return "unknown"

    # fasttext expects single-line input (newlines break predictions)
    clean = text.replace("\n", " ").strip()
    try:
        # fasttext uses np.array(..., copy=False) which breaks on NumPy 2.x.
        # Monkey-patch numpy.array to convert copy=False → copy=None for the call.
        import numpy as np
        _original_array = np.array

        def _patched_array(*args, **kwargs):
            if kwargs.get('copy') is False:
                kwargs['copy'] = None
            return _original_array(*args, **kwargs)

        np.array = _patched_array
        try:
            predictions = model.predict(clean, k=1)
        finally:
            np.array = _original_array

        # predictions = (('__label__en',), array([0.98]))
        label = predictions[0][0]  # '__label__en'
        lang_code = label.replace("__label__", "")
        return lang_code
    except Exception as exc:
        logger.warning("Language detection failed: %s", exc)
        return "unknown"


def is_likely_darija(text: str, lang_code: str) -> bool:
    """
    Heuristic check for Moroccan Darija.

    Darija is a diglossic mix of Arabic, French, and Berber.
    fasttext typically classifies it as "ar" (Arabic-script) or misclassifies
    Arabizi as Indonesian/Spanish/Italian. This heuristic adds script-based signals.
    """
    if lang_code not in _DARIJA_MARKERS:
        return False

    # Arabic-script Darija: contains Arabic chars mixed with Latin
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    latin_chars = sum(1 for c in text if c.isascii() and c.isalpha())

    # Arabizi markers: digits 2, 3, 5, 7, 8, 9 used as Arabic letter substitutes
    # These digits are rare in normal text but common in Arabizi transliteration
    arabizi_count = sum(1 for c in text if c in "235789")

    # Mixed Arabic + Latin script is a strong Darija signal
    if arabic_chars >= 2 and latin_chars >= 2:
        return True

    # 2+ Arabizi digits in a message that was misclassified = likely Darija
    if arabizi_count >= 2 and lang_code in {"id", "es", "it", "ms", "tr", "fr"}:
        return True

    # 1+ Arabizi digit with Arabic classification = likely Darija (not MSA)
    if arabizi_count >= 1 and lang_code == "ar":
        return True

    return False
