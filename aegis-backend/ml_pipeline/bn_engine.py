"""
AEGIS Bayesian Profiler Engine

Defines the Bayesian Network structure, CPTs, and inference logic
for behavioral risk assessment. Replaces the Random Forest model.

Architecture:
  10 observable variables → 3 intermediate risk nodes → 1 output node

The CPTs encode domain expertise from:
  - O'Connell (2003): Grooming stages
  - Olweus (1993): Bullying criteria
  - NCMEC/DHS: Predator indicators
  - AEGIS operational data: Cobra Effect, severity-aware corrections
"""

import logging
import numpy as np
from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination

logger = logging.getLogger(__name__)


class BayesianProfiler:
    """
    Encapsulates the Bayesian Network for behavioral risk assessment.
    Loaded once at Django startup. Thread-safe for read-only inference.
    """

    # Risk score weights for each OverallRisk modality
    RISK_WEIGHTS = {"LOW": 0.05, "MEDIUM": 0.35, "HIGH": 0.65, "CRITICAL": 0.95}

    def __init__(self):
        self.model = self._build_network()
        self.inference = VariableElimination(self.model)
        logger.info("[AGENT 4] ✅ Bayesian Network loaded and ready")

    def _build_network(self) -> DiscreteBayesianNetwork:
        """Build the complete DAG structure with CPTs."""

        # ── 1. Define edges (causal relationships) ───────────
        model = DiscreteBayesianNetwork([
            # Grooming pathway
            ("Stranger", "GroomingRisk"),
            ("ChildInitiated", "GroomingRisk"),
            ("SharedGroupsCount", "GroomingRisk"),
            ("NightActive", "GroomingRisk"),
            ("UpwardCorrection", "GroomingRisk"),
            ("DownwardCorrection", "GroomingRisk"),
            ("MessageStyle", "GroomingRisk"),
            ("ThreatCategory", "GroomingRisk"),
            # Bully pathway
            ("ToxicityLevel", "BullyRisk"),
            ("BlockRatio", "BullyRisk"),
            ("TargetBreadth", "BullyRisk"),
            ("ThreatCategory", "BullyRisk"),
            ("DownwardCorrection", "BullyRisk"),
            # Troll pathway
            ("MessageBehavior", "TrollRisk"),
            ("TargetBreadth", "TrollRisk"),
            ("Stranger", "TrollRisk"),
            ("MessageStyle", "TrollRisk"),
            # Final output
            ("GroomingRisk", "OverallRisk"),
            ("BullyRisk", "OverallRisk"),
            ("TrollRisk", "OverallRisk"),
        ])

        # ── 2. Prior CPTs for root/observable nodes ──────────
        # These represent base rates in the AEGIS population

        cpd_stranger = TabularCPD(
            "Stranger", 2, [[0.70], [0.30]],
            state_names={"Stranger": ["NO", "YES"]}
        )

        cpd_child_initiated = TabularCPD(
            "ChildInitiated", 2, [[0.50], [0.50]],
            state_names={"ChildInitiated": ["NO", "YES"]}
        )

        cpd_shared_groups = TabularCPD(
            "SharedGroupsCount", 3, [[0.80], [0.15], [0.05]],
            state_names={"SharedGroupsCount": ["ZERO", "ONE", "MANY"]}
        )

        cpd_night = TabularCPD(
            "NightActive", 3, [[0.60], [0.25], [0.15]],
            state_names={"NightActive": ["LOW", "MEDIUM", "HIGH"]}
        )

        cpd_toxicity = TabularCPD(
            "ToxicityLevel", 4, [[0.50], [0.25], [0.15], [0.10]],
            state_names={"ToxicityLevel": ["CLEAN", "MILD", "MODERATE", "SEVERE"]}
        )

        cpd_upward = TabularCPD(
            "UpwardCorrection", 3, [[0.75], [0.15], [0.10]],
            state_names={"UpwardCorrection": ["LOW", "MEDIUM", "HIGH"]}
        )

        cpd_downward = TabularCPD(
            "DownwardCorrection", 3, [[0.70], [0.20], [0.10]],
            state_names={"DownwardCorrection": ["LOW", "MEDIUM", "HIGH"]}
        )

        cpd_targets = TabularCPD(
            "TargetBreadth", 3, [[0.65], [0.25], [0.10]],
            state_names={"TargetBreadth": ["FEW", "SOME", "MANY"]}
        )

        cpd_block = TabularCPD(
            "BlockRatio", 3, [[0.70], [0.20], [0.10]],
            state_names={"BlockRatio": ["LOW", "MEDIUM", "HIGH"]}
        )

        cpd_behavior = TabularCPD(
            "MessageBehavior", 3, [[0.60], [0.30], [0.10]],
            state_names={"MessageBehavior": ["CALM", "ACTIVE", "BURSTY"]}
        )

        cpd_style = TabularCPD(
            "MessageStyle", 3, [[0.30], [0.50], [0.20]],
            state_names={"MessageStyle": ["SHORT", "MEDIUM", "LONG"]}
        )

        cpd_category = TabularCPD(
            "ThreatCategory", 5,
            [[0.70], [0.12], [0.08], [0.05], [0.05]],
            state_names={"ThreatCategory": [
                "SAFE", "VERBAL", "THREAT", "SEXUAL", "DISCRIMINATION"
            ]}
        )

        # ── 3. Conditional CPTs for hidden nodes ─────────────
        # These encode domain expertise about risk patterns

        cpd_grooming = self._build_grooming_cpt()
        cpd_bully = self._build_bully_cpt()
        cpd_troll = self._build_troll_cpt()
        cpd_overall = self._build_overall_cpt()

        # ── 4. Assemble and validate ─────────────────────────
        model.add_cpds(
            cpd_stranger, cpd_child_initiated, cpd_shared_groups, cpd_night, cpd_toxicity, cpd_upward,
            cpd_downward, cpd_targets, cpd_block, cpd_behavior,
            cpd_style, cpd_category,
            cpd_grooming, cpd_bully, cpd_troll, cpd_overall,
        )

        if not model.check_model():
            raise ValueError("BN model validation failed! Check CPT dimensions.")

        logger.info("[AGENT 4] BN model validated: %d nodes, %d edges",
                    len(model.nodes()), len(model.edges()))
        return model

    # ══════════════════════════════════════════════════════════
    #  GROOMING RISK CPT
    # ══════════════════════════════════════════════════════════
    # Parents: Stranger(2) × NightActive(3) × UpwardCorrection(3)
    #          × DownwardCorrection(3) × MessageStyle(3) × ThreatCategory(5)
    # Total combos: 2×3×3×3×3×5 = 810 columns
    #
    # Strategy: Build programmatically using scoring rules rather than
    # hand-filling 810 entries. Each parent contributes a "grooming
    # score" and we convert to probabilities via softmax-like mapping.
    # ══════════════════════════════════════════════════════════

    def _build_grooming_cpt(self) -> TabularCPD:
        """
        Build GroomingRisk CPT programmatically.

        Each parent combination gets a grooming score based on
        how strongly each parent state indicates grooming.
        The score is then converted to P(LOW), P(MED), P(HIGH).
        """
        # Parent order: Stranger, ChildInitiated, SharedGroupsCount, NightActive,
        #               UpwardCorrection, DownwardCorrection, MessageStyle, ThreatCategory
        stranger_states = ["NO", "YES"]
        child_init_states = ["NO", "YES"]
        groups_states = ["ZERO", "ONE", "MANY"]
        night_states = ["LOW", "MEDIUM", "HIGH"]
        upward_states = ["LOW", "MEDIUM", "HIGH"]
        downward_states = ["LOW", "MEDIUM", "HIGH"]
        style_states = ["SHORT", "MEDIUM", "LONG"]
        category_states = ["SAFE", "VERBAL", "THREAT", "SEXUAL", "DISCRIMINATION"]

        # Grooming contribution scores for each parent state
        stranger_scores = {"NO": 0.0, "YES": 0.35}
        child_init_scores = {"NO": 0.15, "YES": -0.20}
        groups_scores = {"ZERO": 0.0, "ONE": -0.30, "MANY": -0.40}
        night_scores = {"LOW": 0.0, "MEDIUM": 0.10, "HIGH": 0.20}
        upward_scores = {"LOW": 0.0, "MEDIUM": 0.20, "HIGH": 0.35}
        downward_scores = {"LOW": 0.0, "MEDIUM": -0.10, "HIGH": -0.25}  # Negative = reduces risk
        style_scores = {"SHORT": -0.05, "MEDIUM": 0.0, "LONG": 0.15}
        category_scores = {"SAFE": 0.0, "VERBAL": -0.05, "THREAT": -0.05,
                           "SEXUAL": 0.25, "DISCRIMINATION": -0.05}

        values = []  # Will be 3 rows × 4860 columns

        for s in stranger_states:
            for ci in child_init_states:
                for sg in groups_states:
                    for n in night_states:
                        for u in upward_states:
                            for d in downward_states:
                                for st in style_states:
                                    for c in category_states:
                                        score = (stranger_scores[s] + child_init_scores[ci] +
                                                 groups_scores[sg] + night_scores[n] +
                                                 upward_scores[u] + downward_scores[d] +
                                                 style_scores[st] + category_scores[c])
                                        # Clamp to [0, 1]
                                        score = max(0.0, min(1.0, score))
                                        # Convert score to probabilities
                                        probs = self._score_to_3probs(score)
                                        values.append(probs)

        # Reshape: values is list of 4860 tuples of (p_low, p_med, p_high)
        arr = np.array(values).T  # Shape: (3, 4860)

        return TabularCPD(
            "GroomingRisk", 3, arr.tolist(),
            evidence=["Stranger", "ChildInitiated", "SharedGroupsCount", "NightActive", "UpwardCorrection",
                       "DownwardCorrection", "MessageStyle", "ThreatCategory"],
            evidence_card=[2, 2, 3, 3, 3, 3, 3, 5],
            state_names={
                "GroomingRisk": ["LOW", "MEDIUM", "HIGH"],
                "Stranger": stranger_states,
                "ChildInitiated": child_init_states,
                "SharedGroupsCount": groups_states,
                "NightActive": night_states,
                "UpwardCorrection": upward_states,
                "DownwardCorrection": downward_states,
                "MessageStyle": style_states,
                "ThreatCategory": category_states,
            }
        )

    # ══════════════════════════════════════════════════════════
    #  BULLY RISK CPT
    # ══════════════════════════════════════════════════════════
    # Parents: ToxicityLevel(4) × BlockRatio(3) × TargetBreadth(3)
    #          × ThreatCategory(5) × DownwardCorrection(3)
    # Total: 4×3×3×5×3 = 540 columns

    def _build_bully_cpt(self) -> TabularCPD:
        """Build BullyRisk CPT programmatically."""
        tox_states = ["CLEAN", "MILD", "MODERATE", "SEVERE"]
        block_states = ["LOW", "MEDIUM", "HIGH"]
        target_states = ["FEW", "SOME", "MANY"]
        cat_states = ["SAFE", "VERBAL", "THREAT", "SEXUAL", "DISCRIMINATION"]
        down_states = ["LOW", "MEDIUM", "HIGH"]

        # Bully contribution scores
        tox_scores = {"CLEAN": 0.0, "MILD": 0.10, "MODERATE": 0.30, "SEVERE": 0.40}
        block_scores = {"LOW": 0.0, "MEDIUM": 0.15, "HIGH": 0.25}
        # FEW targets + high toxicity = focused bullying (Olweus)
        target_scores = {"FEW": 0.10, "SOME": 0.05, "MANY": -0.05}
        cat_scores = {"SAFE": -0.05, "VERBAL": 0.15, "THREAT": 0.25,
                      "SEXUAL": 0.0, "DISCRIMINATION": 0.15}
        down_scores = {"LOW": 0.0, "MEDIUM": -0.10, "HIGH": -0.25}

        values = []
        for t in tox_states:
            for b in block_states:
                for tg in target_states:
                    for c in cat_states:
                        for d in down_states:
                            score = (tox_scores[t] + block_scores[b] +
                                     target_scores[tg] + cat_scores[c] +
                                     down_scores[d])
                            score = max(0.0, min(1.0, score))
                            values.append(self._score_to_3probs(score))

        arr = np.array(values).T
        return TabularCPD(
            "BullyRisk", 3, arr.tolist(),
            evidence=["ToxicityLevel", "BlockRatio", "TargetBreadth",
                       "ThreatCategory", "DownwardCorrection"],
            evidence_card=[4, 3, 3, 5, 3],
            state_names={
                "BullyRisk": ["LOW", "MEDIUM", "HIGH"],
                "ToxicityLevel": tox_states,
                "BlockRatio": block_states,
                "TargetBreadth": target_states,
                "ThreatCategory": cat_states,
                "DownwardCorrection": down_states,
            }
        )

    # ══════════════════════════════════════════════════════════
    #  TROLL RISK CPT
    # ══════════════════════════════════════════════════════════
    # Parents: MessageBehavior(3) × TargetBreadth(3) × Stranger(2)
    #          × MessageStyle(3)
    # Total: 3×3×2×3 = 54 columns

    def _build_troll_cpt(self) -> TabularCPD:
        """Build TrollRisk CPT programmatically."""
        beh_states = ["CALM", "ACTIVE", "BURSTY"]
        target_states = ["FEW", "SOME", "MANY"]
        stranger_states = ["NO", "YES"]
        style_states = ["SHORT", "MEDIUM", "LONG"]

        beh_scores = {"CALM": 0.0, "ACTIVE": 0.10, "BURSTY": 0.35}
        target_scores = {"FEW": 0.0, "SOME": 0.10, "MANY": 0.30}
        stranger_scores = {"NO": 0.0, "YES": 0.15}
        style_scores = {"SHORT": 0.15, "MEDIUM": 0.0, "LONG": -0.10}

        values = []
        for b in beh_states:
            for t in target_states:
                for s in stranger_states:
                    for st in style_states:
                        score = (beh_scores[b] + target_scores[t] +
                                 stranger_scores[s] + style_scores[st])
                        score = max(0.0, min(1.0, score))
                        values.append(self._score_to_3probs(score))

        arr = np.array(values).T
        return TabularCPD(
            "TrollRisk", 3, arr.tolist(),
            evidence=["MessageBehavior", "TargetBreadth", "Stranger", "MessageStyle"],
            evidence_card=[3, 3, 2, 3],
            state_names={
                "TrollRisk": ["LOW", "MEDIUM", "HIGH"],
                "MessageBehavior": beh_states,
                "TargetBreadth": target_states,
                "Stranger": stranger_states,
                "MessageStyle": style_states,
            }
        )

    # ══════════════════════════════════════════════════════════
    #  OVERALL RISK CPT
    # ══════════════════════════════════════════════════════════
    # Parents: GroomingRisk(3) × BullyRisk(3) × TrollRisk(3)
    # Total: 3×3×3 = 27 columns
    # Output: 4 states (LOW, MEDIUM, HIGH, CRITICAL)

    def _build_overall_cpt(self) -> TabularCPD:
        """
        Build OverallRisk CPT.

        Key rules:
        - GroomingRisk=HIGH → CRITICAL (regardless of others)
        - BullyRisk=HIGH → HIGH (unless grooming overrides to CRITICAL)
        - TrollRisk=HIGH → MEDIUM-HIGH
        - All LOW → LOW
        """
        risk_states = ["LOW", "MEDIUM", "HIGH"]

        values = []
        for g in risk_states:
            for b in risk_states:
                for t in risk_states:
                    probs = self._overall_logic(g, b, t)
                    values.append(probs)

        arr = np.array(values).T  # Shape: (4, 27)
        return TabularCPD(
            "OverallRisk", 4, arr.tolist(),
            evidence=["GroomingRisk", "BullyRisk", "TrollRisk"],
            evidence_card=[3, 3, 3],
            state_names={
                "OverallRisk": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                "GroomingRisk": risk_states,
                "BullyRisk": risk_states,
                "TrollRisk": risk_states,
            }
        )

    @staticmethod
    def _overall_logic(g: str, b: str, t: str) -> tuple:
        """
        Compute P(OverallRisk | GroomingRisk, BullyRisk, TrollRisk).
        Returns (P_LOW, P_MEDIUM, P_HIGH, P_CRITICAL).
        """
        # Convert to numeric levels
        level = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        gl, bl, tl = level[g], level[b], level[t]

        # Grooming HIGH → CRITICAL dominates
        if gl == 2:
            if bl >= 1:
                return (0.01, 0.02, 0.12, 0.85)  # Groomer + bully signals
            return (0.02, 0.03, 0.15, 0.80)       # Pure groomer

        # Grooming MEDIUM → elevated concern
        if gl == 1:
            if bl == 2:
                return (0.03, 0.07, 0.45, 0.45)   # Potential groomer + bully
            if bl == 1:
                return (0.05, 0.15, 0.40, 0.40)
            if tl == 2:
                return (0.05, 0.20, 0.35, 0.40)
            return (0.10, 0.30, 0.35, 0.25)

        # No grooming signal — bully/troll only
        if bl == 2:
            if tl >= 1:
                return (0.02, 0.08, 0.75, 0.15)   # Bully + troll
            return (0.03, 0.07, 0.80, 0.10)        # Pure bully

        if bl == 1:
            if tl == 2:
                return (0.05, 0.30, 0.55, 0.10)
            if tl == 1:
                return (0.10, 0.40, 0.40, 0.10)
            return (0.15, 0.45, 0.30, 0.10)

        # No bully signal either
        if tl == 2:
            return (0.10, 0.55, 0.30, 0.05)       # Pure troll
        if tl == 1:
            return (0.30, 0.50, 0.15, 0.05)
        return (0.85, 0.10, 0.03, 0.02)            # All LOW → normal user

    @staticmethod
    def _score_to_3probs(score: float) -> tuple:
        """
        Convert a [0, 1] score into (P_LOW, P_MEDIUM, P_HIGH).

        Uses a smooth mapping:
        - score ~0.0 → mostly LOW
        - score ~0.5 → mostly MEDIUM
        - score ~1.0 → mostly HIGH
        """
        # Ensure score is in valid range
        score = max(0.0, min(1.0, score))

        if score <= 0.25:
            # Mostly LOW
            p_low = 0.90 - score * 2.0
            p_med = 0.08 + score * 1.5
            p_high = 0.02 + score * 0.5
        elif score <= 0.55:
            # Transition to MEDIUM
            t = (score - 0.25) / 0.30
            p_low = 0.40 - t * 0.30
            p_med = 0.45 + t * 0.10
            p_high = 0.15 + t * 0.20
        else:
            # Mostly HIGH
            t = (score - 0.55) / 0.45
            p_low = 0.10 - t * 0.08
            p_med = 0.55 - t * 0.40
            p_high = 0.35 + t * 0.48

        # Normalize to sum to 1.0
        total = p_low + p_med + p_high
        return (round(p_low / total, 4),
                round(p_med / total, 4),
                round(p_high / total, 4))

    # ══════════════════════════════════════════════════════════
    #  INFERENCE
    # ══════════════════════════════════════════════════════════

    def infer(self, evidence: dict) -> dict:
        """
        Run BN inference given observed evidence.

        Args:
            evidence: dict from collect_evidence()
                      e.g. {"Stranger": "YES", "NightActive": "HIGH", ...}

        Returns:
            dict with:
              - risk_score: float in [0, 1] (calibrated)
              - risk_level: str (LOW/MEDIUM/HIGH/CRITICAL)
              - archetype: str (Normal User/Troll Pattern/Bully Pattern/Groomer Pattern)
              - probas: dict of {level: probability}
              - explanation: dict of per-pathway probabilities
        """
        # Query the OverallRisk posterior
        result = self.inference.query(
            variables=["OverallRisk"],
            evidence=evidence,
            show_progress=False
        )

        # Extract probabilities
        overall_states = result.state_names["OverallRisk"]
        probas = {
            state: float(result.values[i])
            for i, state in enumerate(overall_states)
        }

        # Compute risk score (weighted sum of probabilities)
        risk_score = sum(
            probas[state] * self.RISK_WEIGHTS[state]
            for state in probas
        )

        # Determine risk level (highest probability)
        risk_level = max(probas, key=probas.get)

        # Get per-pathway explanation
        explanation = {}
        for pathway in ["GroomingRisk", "BullyRisk", "TrollRisk"]:
            try:
                pw_result = self.inference.query(
                    variables=[pathway],
                    evidence=evidence,
                    show_progress=False
                )
                pw_states = pw_result.state_names[pathway]
                explanation[pathway] = {
                    state: float(pw_result.values[i])
                    for i, state in enumerate(pw_states)
                }
            except Exception as e:
                logger.warning(f"[AGENT 4] BN pathway query failed for {pathway}: {e}")
                explanation[pathway] = {"LOW": 0.33, "MEDIUM": 0.34, "HIGH": 0.33}

        # Determine archetype from dominant pathway
        dominant_pathway = max(
            explanation,
            key=lambda p: explanation[p].get("HIGH", 0)
        )
        archetype_map = {
            "GroomingRisk": "Groomer Pattern",
            "BullyRisk": "Bully Pattern",
            "TrollRisk": "Troll Pattern",
        }
        archetype = archetype_map.get(dominant_pathway, "Normal User")

        # If overall risk is LOW, override archetype
        if risk_level == "LOW":
            archetype = "Normal User"

        return {
            "risk_score": round(risk_score, 4),
            "risk_level": risk_level,
            "archetype": archetype,
            "probas": probas,
            "explanation": explanation,
        }


# ═══════════════════════════════════════════════════════════════
#  SINGLETON
# ═══════════════════════════════════════════════════════════════

_BN_PROFILER = None


def get_bn_profiler() -> BayesianProfiler:
    """Get or create the singleton BayesianProfiler instance."""
    global _BN_PROFILER
    if _BN_PROFILER is None:
        _BN_PROFILER = BayesianProfiler()
    return _BN_PROFILER
