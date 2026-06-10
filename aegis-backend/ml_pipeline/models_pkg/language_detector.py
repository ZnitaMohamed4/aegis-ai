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
_DARIJA_MARKERS = {"ar", "fr", "id", "es", "it", "ms", "tr", "en", "ur", "de", "hu", "pt", "nl", "zh", "ro", "pl", "sv"}  # Languages Darija is commonly misclassified as

# Common Darija lexical markers — words that are uniquely Moroccan dialectal
# and almost never appear in MSA, French, English, or other languages.
# These are the strongest signal for detecting Darija in both scripts.
_DARIJA_LEXICAL_MARKERS = {
    # ── Latin-script markers (Arabizi / transliterated) ──────────────
    # Pronouns / particles
    "dyal", "dyali", "dyalk", "dyalkom", "dyalha", "dyalo",
    "machi", "makaynch", "wakha", "yalah", "daba",
    "bzzaf", "bezaf", "shwiya", "chwia",
    "nta", "nti", "ntouma", "huwa", "hiya", "hna",
    # Greetings / common phrases
    "salam", "salamo", "alek", "alekom", "alik",
    "labas", "labass", "labasse", "la bas", "bikhir", "hamdulah", "lhamdullah", "nchallah", "inchallah",
    "khouya", "khoya", "sahbi", "sahbiya",
    "elik", "3lik", "3liya",
    # Question words
    "chno", "chnou", "kifach", "fach", "shkun", "chkun",
    "wach", "wash", "3lach", "3lash", "fin", "fink",
    # Verbs
    "bghit", "bghiti", "bgha", "kandir", "kadir", "kaydir",
    "ghadi", "mshi", "mshina", "sir", "jib",
    # Common verb conjugations (Darija suffixes: -ek/-ik/-u/-ha/-ni)
    "bghitek", "bghitu", "bghitek", "bghiti", "bghitk",
    "kandiro", "kadiri", "ghadin", "mshit",
    "kat3awd", "katdir", "kaydir", "kaykon",
    "3tini", "3tini", "aji", "nji", "njik",
    # Adjectives
    "zwina", "zwin", "mzyan", "mazyan", "khyb", "khyba",
    "mzyana", "zwin", "zwina",
    # Nouns
    "lflous", "flous", "weld", "bent", "wlad",
    # Offensive (common Darija insults — strong signal)
    "9a7ba", "l9a7ba", "l9ahba", "qahba",
    "7mar", "7mara", "t9awd", "tqwd", "azaml", "zamel",
    # Prepositions / pronouns
    "m3aya", "m3ak", "m3aha", "m3ah", "binatna",
    # Interjections
    "wllh", "wlh", "afin",
    # Darija prefix patterns (imperfect conjugation markers)
    # "ka-" / "ta-" / "kat-" / "tat-" prefixes are distinctly Darija
    # ── Arabic-script markers ────────────────────────────────────────
    # These are Darija-specific words written in Arabic script that
    # almost never appear in MSA. Strong signal for Arabic-script Darija.
    "ديال", "ديالي", "ديالك", "ديالكم",
    "ماشي", "ماكاينش", "واخا", "يلاه", "دابا",
    "بزاف", "شوية",
    "لاباس", "لاباس؟", "بخير", "الحمدلله", "ان شاء الله",
    "خويا", "صاحبي", "صحبي",
    "شنو", "كيفاش", "فاش", "شكون",
    "بغيت", "بغيتي", "بغا", "غادي", "كندير", "كادير",
    "مزيان", "زوين", "zwina", "خيب",
    "الفلوس", "فلوس",
    "والله",
    # Darija pronouns (Arabic script) — distinct from MSA
    "نتا", "نتي", "نتوما",  # you (masc/fem/pl)
    "فين", "فينك", "فينكم",  # where (MSA uses أين)
    "واش", "آش",  # what/question marker
    "علاش", "علاه",  # why (MSA uses لماذا)
    # Darija verbs (Arabic script)
    "سير", "جي", "مشا", "جا",  # go, come (imperative/past)
    "قود", "تقود",  # go (Maghrebi)
    "بغى", "بغيت",  # want
    "دار", "دير",  # do
    # Darija nouns/adjectives (Arabic script)
    "ولد", "بنت", "ولاد",  # boy, girl, boys (Maghrebi)
    "قحبة", "القحبة", "حمار", "الحمار",  # offensive
    # Common Darija phrases (multi-word for extra precision)
    "كي داير", "كيداير",
    "الله يهديك", "الله يعطيك",
    "هدا", "هاد", "هاذ",  # Darija demonstratives (not MSA)
    "سير تقود", "ولد القحبة",  # common offensive phrases
}


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
    Arabizi as ANY random language (Welsh, Volapük, Persian, Indonesian, etc.)
    because Darija transliteration is not a known language to fasttext.

    Detection strategy (priority order):
      1. Arabizi digits (2+ in any text) → strong Darija signal regardless of lang
      2. Darija lexical markers → strong signal regardless of lang
      3. Mixed Arabic + Latin script → strong signal
      4. Arabizi digits with Arabic lang → likely Darija (not MSA)
    """

    # Arabic-script Darija: contains Arabic chars mixed with Latin
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    latin_chars = sum(1 for c in text if c.isascii() and c.isalpha())

    # Arabizi markers: digits 2, 3, 5, 7, 8, 9 used as Arabic letter substitutes
    # These digits are rare in normal text but common in Arabizi transliteration
    arabizi_count = sum(1 for c in text if c in "235789")

    # ── Signal 1: Arabizi digits (STRONGEST — overrides lang code) ────
    # fasttext cannot classify Arabizi and returns random languages.
    # 2+ Arabizi digits in ANY text is a strong Darija signal.
    if arabizi_count >= 2:
        return True

    # ── Signal 2: Darija lexical markers (strong — overrides lang code) ─
    # Check for common Darija words. Works regardless of what fasttext says.
    # Strip BOTH Arabic and Latin punctuation so words like "salam." match "salam"
    _all_punct = str.maketrans('', '', '؟،؛٠.,!?;:\'"()-')
    text_clean = text.lower().translate(_all_punct)
    text_words = set(text_clean.split())
    if text_words & _DARIJA_LEXICAL_MARKERS:
        return True

    # Also check for multi-word markers via substring matching
    for marker in _DARIJA_LEXICAL_MARKERS:
        if ' ' in marker and marker in text_clean:
            return True

    # ── Signal 3: Mixed Arabic + Latin script ────────────────────────
    if arabic_chars >= 2 and latin_chars >= 2:
        return True

    # ── Signal 4: Single Arabizi digit + known Darija lang code ──────
    if arabizi_count >= 1 and lang_code in _DARIJA_MARKERS:
        return True

    return False
