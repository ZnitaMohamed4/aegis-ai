import logging
from dataclasses import dataclass
from typing import Optional
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from .normalizer import normalize_text

logger = logging.getLogger(__name__)

# Constants from V5 Strategy & UML
M1_THRESHOLD = 0.48
TOP2_DELTA_THRESHOLD = 0.15

# Label Maps
M2_LABEL_MAP = {
    0: 'discrimination',
    1: 'sexual_harassment',
    2: 'threat',
    3: 'verbal_harassment',
}

# The Hierarchical Priority Rule (Highest to Lowest)
M2_PRIORITY = ['threat', 'sexual_harassment', 'discrimination', 'verbal_harassment']


@dataclass
class PipelineResult:
    normalized_text: str
    m1_score: float
    is_harmful: bool
    primary_class: Optional[str]
    secondary_class: Optional[str]
    m2_confidence: Optional[float]
    decision: str


class AEGISPipeline:
    """Singleton wrapper for M1/M2 models. Loaded once at Django startup."""
    _instance: Optional['AEGISPipeline'] = None

    def __init__(self, m1_path: str, m2_path: str, threshold: float):
        self.threshold = threshold
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"[AEGIS] Loading models on device: {self.device}")
        
        # Load M1 (Gatekeeper)
        self.m1_tokenizer = AutoTokenizer.from_pretrained(m1_path)
        self.m1_model = AutoModelForSequenceClassification.from_pretrained(m1_path).to(self.device).eval()
        
        # Load M2 (Specialist)
        self.m2_tokenizer = AutoTokenizer.from_pretrained(m2_path)
        self.m2_model = AutoModelForSequenceClassification.from_pretrained(m2_path).to(self.device).eval()
        
        logger.info("[AEGIS] ✅ Pipeline models ready.")

    @classmethod
    def get_instance(cls):
        return cls._instance

    @classmethod
    def initialize(cls, m1_path: str, m2_path: str, threshold: float):
        if cls._instance is None:
            cls._instance = cls(m1_path, m2_path, threshold)


def get_decision_uml(m1_score: float, primary_class: str, confidence: float) -> str:
    """Maps the scores/classes directly to your UML Decisions."""
    # 1. Extreme Threats
    if primary_class == 'threat' and m1_score > 0.95:
        return 'ESCALATE'
    # 2. Grey Zone (Requires Admin / LLM Review)
    if 0.65 <= confidence <= 0.75:
        return 'REVISE'
    # 3. Clear, severe harm
    if primary_class in ('threat', 'sexual_harassment', 'discrimination'):
        return 'BLOCK'
    # 4. Verbal Harassment (depends on M1 severity)
    if primary_class == 'verbal_harassment':
        return 'WARN' if m1_score < 0.85 else 'BLOCK'
        
    return 'ALLOW'


def run_pipeline(raw_text: str) -> PipelineResult:
    """The REAL inference pipeline."""
    pipeline = AEGISPipeline.get_instance()
    if pipeline is None:
        raise RuntimeError("AEGIS pipeline not initialized.")

    text = normalize_text(raw_text)

    # 1. M1 Binary Gate Prediction
    inputs = pipeline.m1_tokenizer(text, return_tensors='pt', truncation=True, max_length=128, padding=True).to(pipeline.device)
    with torch.no_grad():
        probs = torch.softmax(pipeline.m1_model(**inputs).logits, dim=-1)
    
    m1_score = probs[0][1].item()  # Assuming Label 1 is HARMFUL
    is_harmful = m1_score >= pipeline.threshold

    if not is_harmful:
        return PipelineResult(text, m1_score, False, 'safe', None, None, 'ALLOW')

    # 2. M2 Fine-Grained Prediction
    inputs = pipeline.m2_tokenizer(text, return_tensors='pt', truncation=True, max_length=128, padding=True).to(pipeline.device)
    with torch.no_grad():
        probs = torch.softmax(pipeline.m2_model(**inputs).logits, dim=-1)[0]

    top2_idx = torch.topk(probs, k=2).indices.tolist()
    top2_val = torch.topk(probs, k=2).values.tolist()
    
    primary_label = M2_LABEL_MAP[top2_idx[0]]
    secondary_label = M2_LABEL_MAP[top2_idx[1]]
    confidence = top2_val[0]
    delta = top2_val[0] - top2_val[1]
    
    # Top-2 resolution logic (delta < 0.15)
    final_secondary = secondary_label if delta < TOP2_DELTA_THRESHOLD else None

    # Priority override logic
    candidates = [primary_label]
    if final_secondary:
        candidates.append(final_secondary)
        
    for priority_class in M2_PRIORITY:
        if priority_class in candidates:
            primary_label = priority_class
            break

    decision = get_decision_uml(m1_score, primary_label, confidence)

    return PipelineResult(text, m1_score, True, primary_label, final_secondary, confidence, decision)


def run_pipeline_stub(raw_text: str) -> PipelineResult:
    """
    STUB MODE 
    Keyword-based fake pipeline for testing Webhooks & Dashboards without real models.
    """
    text = normalize_text(raw_text)
    
    # Fake logic
    critique_kws = ['kill', 'die']
    block_kws = ['nude', 'hate', 'racist']
    warn_kws = ['stupid', 'idiot']
    revise_kws = ['ambiguous', 'joke']
    
    # Defaults
    primary = 'safe'
    m1_val = 0.05
    conf = None
    dec = 'ALLOW'

    if any(k in text for k in critique_kws):
        primary, m1_val, conf, dec = 'threat', 0.98, 0.95, 'ESCALATE'
    elif any(k in text for k in block_kws):
        primary, m1_val, conf, dec = 'sexual_harassment', 0.88, 0.90, 'BLOCK'
    elif any(k in text for k in warn_kws):
        primary, m1_val, conf, dec = 'verbal_harassment', 0.60, 0.80, 'WARN'
    elif any(k in text for k in revise_kws):
        primary, m1_val, conf, dec = 'discrimination', 0.70, 0.70, 'REVISE' # Triggers grey zone
        
    is_harmful = dec != 'ALLOW'

    return PipelineResult(
        normalized_text=text,
        m1_score=m1_val,
        is_harmful=is_harmful,
        primary_class=primary,
        secondary_class=None,
        m2_confidence=conf,
        decision=dec
    )
