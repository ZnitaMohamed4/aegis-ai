"""
Darija Offensive Language Detection Pipeline (M1D)

Mirrors the English AEGISPipeline (M1+M2) but uses DarijaBERT-mix fine-tuned
on the merged OMCD+DarLoad dataset (29,681 samples, F1-Macro 0.947).

Architecture:
  - M1D: DarijaBERT-mix binary gate (offensive / non-offensive)
  - No M2D: All Darija-flagged messages are routed to Agent 3 (LLM Auditor)
            for fine-grained severity classification with Darija cultural context.

The DarijaPipeline singleton is loaded once at Django startup alongside the
English AEGISPipeline, and is invoked by the gatekeeper when language detection
identifies a message as Moroccan Darija.
"""
import logging
import re
import time as _time
from dataclasses import dataclass
from typing import Optional

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from .inference import PipelineResult

logger = logging.getLogger(__name__)

# ── M1D Threshold ──────────────────────────────────────────────────────
# Same default as English M1. The M1D model outputs well-calibrated softmax
# probabilities (test F1=0.947 at this threshold), so 0.48 is appropriate.
M1D_THRESHOLD = 0.48

# ── Arabizi → Arabic letter mapping (supplementary aid) ───────────────
# DarijaBERT-mix was trained on both scripts natively, but explicit mapping
# helps align digit-Arabizi tokens closer to Arabic-script embeddings.
ARABIZI_TO_ARABIC = {
    '2': 'ا',   # hamza / alif
    '3': 'ع',   # ain
    '5': 'خ',   # kha
    '7': 'ح',   # ha
    '8': 'ق',   # qaf
    '9': 'ق',   # qaf (variant)
}

# Multi-char Arabizi digraphs (must be replaced before single-char digits)
ARABIZI_DIGRAPHS = {
    'ch': 'ش',  # shin
    'gh': 'غ',  # ghain
    'kh': 'خ',  # kha
    'sh': 'ش',  # shin
    'th': 'ث',  # tha
    'dh': 'ذ',  # dhal
}


# ═════════════════════════════════════════════════════════════════════
# DARIJA TEXT NORMALIZER
# ═════════════════════════════════════════════════════════════════════

def normalize_darija(text: str, apply_arabizi: bool = False) -> str:
    """
    Darija-specific text normalization before tokenization.

    Steps:
      1. Strip leading/trailing whitespace
      2. Normalize Alif variants (أ, إ, آ → ا) — reduces vocab fragmentation
      3. Normalize Ya variants (ى → ي)
      4. Remove tatweel elongation (كـــتـاب → كتاب)
      5. Strip URLs and @mentions (same as English normalizer)
      6. [Optional] Convert digit-Arabizi to Arabic letters
      7. Collapse whitespace

    Design note: Tashkeel (diacritics) stripping is OFF by default because
    DarijaBERT-mix was pre-trained WITH tashkeel present. Removing it would
    degrade tokenization quality.
    """
    text = str(text).strip()

    # URLs and mentions
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'@\w+', '', text)

    # Alif normalization: أ, إ, آ → bare ا
    text = re.sub(r'[أإآ]', 'ا', text)

    # Ya normalization: ى → ي
    text = text.replace('ى', 'ي')

    # Tatweel (elongation) removal: ـ
    text = text.replace('ـ', '')

    # Optional: Arabizi digit → Arabic letter conversion
    if apply_arabizi:
        # Replace digraphs first (ch → ش before c+h separately)
        for digraph, letter in ARABIZI_DIGRAPHS.items():
            text = text.replace(digraph, letter)
        # Then single digits
        for digit, letter in ARABIZI_TO_ARABIC.items():
            text = text.replace(digit, letter)

    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def has_arabizi_digits(text: str) -> bool:
    """Check if text contains digit-Arabizi (2,3,5,7,8,9 used as letter substitutes)."""
    return any(c in "235789" for c in text)


# ═════════════════════════════════════════════════════════════════════
# DARIJA PIPELINE (Singleton)
# ═════════════════════════════════════════════════════════════════════

class DarijaPipeline:
    """
    Singleton wrapper for the M1D DarijaBERT-mix model.
    Loaded once at Django startup, mirrors AEGISPipeline pattern.
    """
    _instance: Optional['DarijaPipeline'] = None

    def __init__(self, m1d_path: str, threshold: float = M1D_THRESHOLD):
        self.threshold = threshold
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"[M1D-Darija] Loading DarijaBERT-mix on device: {self.device}")

        # Load M1D (DarijaBERT-mix fine-tuned for binary offensive detection)
        self.m1d_tokenizer = AutoTokenizer.from_pretrained(m1d_path)
        self.m1d_model = AutoModelForSequenceClassification.from_pretrained(
            m1d_path
        ).to(self.device).eval()

        logger.info("[M1D-Darija] DarijaBERT-mix model ready.")

    @classmethod
    def get_instance(cls) -> Optional['DarijaPipeline']:
        return cls._instance

    @classmethod
    def initialize(cls, m1d_path: str, threshold: float = M1D_THRESHOLD):
        if cls._instance is None:
            cls._instance = cls(m1d_path, threshold)


# ═════════════════════════════════════════════════════════════════════
# INFERENCE FUNCTION
# ═════════════════════════════════════════════════════════════════════

def run_darija_pipeline(raw_text: str) -> PipelineResult:
    """
    Run the M1D Darija offensive language detection pipeline.

    Returns a PipelineResult compatible with the English pipeline output.
    When M1D flags a message as offensive:
      - primary_class = 'offensive_darija' (generic — Agent 3 will classify severity)
      - decision = 'WARN' (ensures routing to Agent 3 for fine-grained analysis)
    When M1D says clean:
      - primary_class = 'safe'
      - decision = 'ALLOW'
    """
    from moderation.cache_utils import get_cached_prediction, set_cached_prediction

    # Check semantic cache first (same cache shared with English pipeline)
    cache_key = f"[darija]{raw_text}"
    cached = get_cached_prediction(cache_key)
    if cached:
        return PipelineResult(**cached)

    pipeline = DarijaPipeline.get_instance()
    if pipeline is None:
        raise RuntimeError("DarijaPipeline not initialized. Check M1D model loading at startup.")

    # Detect if text contains Arabizi digits → enable Arabizi normalization
    use_arabizi = has_arabizi_digits(raw_text)
    text = normalize_darija(raw_text, apply_arabizi=use_arabizi)

    # ── M1D Inference ─────────────────────────────────────────────────
    t_start = _time.time()
    inputs = pipeline.m1d_tokenizer(
        text,
        return_tensors='pt',
        truncation=True,
        max_length=128,
        padding=True,
    ).to(pipeline.device)

    with torch.no_grad():
        logits = pipeline.m1d_model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)

    # Label 1 = offensive, Label 0 = non-offensive (same as training)
    m1d_score = probs[0][1].item()
    t_elapsed = int((_time.time() - t_start) * 1000)

    is_offensive = m1d_score >= pipeline.threshold

    if not is_offensive:
        result = PipelineResult(
            normalized_text=text,
            m1_score=m1d_score,
            is_harmful=False,
            primary_class='safe',
            secondary_class=None,
            m2_confidence=None,
            decision='ALLOW',
            m1_latency_ms=t_elapsed,
            m2_latency_ms=0,
        )
        logger.info(
            f"[M1D] ✅ ALLOW | score={m1d_score:.4f} (threshold={pipeline.threshold}) "
            f"| latency={t_elapsed}ms | '{text[:60]}'"
        )
        set_cached_prediction(cache_key, result.__dict__)
        return result

    # ── Offensive detected → route to Agent 3 for severity classification ──
    # We set decision='WARN' so the gatekeeper's trust-but-verify logic
    # automatically sends this to Agent 3 (LLM Auditor with Darija awareness).
    # Agent 3 will determine: threat, sexual_harassment, discrimination, etc.
    result = PipelineResult(
        normalized_text=text,
        m1_score=m1d_score,
        is_harmful=True,
        primary_class='offensive_darija',
        secondary_class=None,
        m2_confidence=None,
        decision='WARN',
        m1_latency_ms=t_elapsed,
        m2_latency_ms=0,
    )
    logger.info(
        f"[M1D] 🚨 FLAGGED | score={m1d_score:.4f} (threshold={pipeline.threshold}) "
        f"| class=offensive_darija → Agent 3 | latency={t_elapsed}ms | '{text[:60]}'"
    )
    set_cached_prediction(cache_key, result.__dict__)
    return result
