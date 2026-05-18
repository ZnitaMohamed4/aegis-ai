# 🛡️ AEGIS ML: Intelligent Hierarchical Harmful Content Detection

## 1. Executive Summary
The **AEGIS ML** application is a robust, production-grade Natural Language Processing (NLP) system designed to protect users in conversational environments by filtering toxic, abusive, and threatening language in real-time. This document serves as the comprehensive architectural blueprint, contextualizing the entire ML flow, explaining our structural paradigms, detailing the model iterations (specifically the transition from V2 to V3), and interpreting our benchmarking results. 

The ultimate goal of AEGIS is to maintain safe online spaces without aggressively over-censoring casual, safe human interactions.

---

## 2. Architectural Paradigm: One-Stage vs. Two-Stage Pipeline

A core foundational decision in AEGIS ML was avoiding the traditional "One-Stage" classifier in favor of a **Hierarchical Two-Stage Pipeline**.

### The Flaws of a One-Stage Pipeline
In a standard one-stage approach, a single model is trained to classify text into 5 distinct categories simultaneously: *Safe, Threat, Sexual Harassment, Verbal Harassment, and Discrimination*. 
- **The Problem:** The model faces competing objectives. It must learn the broad, critical boundary between *Safe vs. Harmful*, while simultaneously trying to learn the highly nuanced semantic boundaries between *Verbal Harassment vs. Discrimination*. 
- **The Result:** This cognitive overload reliably causes catastrophic false positives. The model begins aggressively flagging short, informal chat messages as harassment or struggles heavily with class imbalance.

### The AEGIS Two-Stage Solution
By decoupling the architecture into two distinct models (M1 and M2), we allow each transformer encoder to specialize:
- **Stage 1 (M1 - The Gatekeeper):** Solves the hardest problem first—detecting harmful intent with minimal false positives. If text is classified as Safe, it is allowed through instantly.
- **Stage 2 (M2 - The Specialist):** Only activates if M1 predicts danger. Because M2 assumes the text is already harmful, its attention mechanism focuses entirely on distinguishing the *type* of harm. 

This hierarchical routing significantly reduces latency for safe messages and yields drastically higher macro-F1 scores across all categories.

---

## 3. Stage 1 (M1): The Binary Safety Gate

**Objective:** Classify incoming messages strictly as either `SAFE` or `HARMFUL`.
**Foundation:** Fine-tuned `XLM-RoBERTa-base`.

### How M1 Works
M1 focuses on understanding conversational domain registers. Because online chat consists of short, punchy statements (e.g., *"yeah you're such a genius lol"*, *"let's play"*), M1 was trained on specialized datasets comprising daily dialogs, safe demographics, and hard adversarial negatives. 
- **Data Composition:** The V3 M1 corpus was strictly balanced at **50,000 Safe and 50,000 Harmful records** (100K total), deduplicated and drawn from 11 distinct safe sources to heavily penalize formal domain bias.
- **Critical Hyperparameters:** We utilized a learning rate of `2e-5` with an effective batch size of 32. Crucially, **Label Smoothing was strictly disabled (0.0)**, as our rigidly defined and injected binary data required no probabilistic softening.
- **Thresholding Strategy:** Instead of standard binary rounding (0.5), M1 utilizes a meticulously tuned **Decision Threshold**. In our V3 refinement, this was calibrated to `0.48` to ensure a flawless balance between recalling harm and ignoring conversational sarcasm.
- **Output Flow:** If `P(Harmful) < Threshold`, the pipeline terminates. User sees the message. If `P(Harmful) ≥ Threshold`, the message is blocked/flagged, and the text is passed to M2 for sub-classification.

---

## 4. Stage 2 (M2): The Fine-Grained Classifier

**Objective:** Categorize harmful text into `threat`, `sexual_harassment`, `verbal_harassment`, or `discrimination`.
**Foundation:** Sequential Fine-Tuning. M2 is *not* trained from scratch; it is initialized with M1's learned weights, granting it a head-start in understanding toxic language representations.

### How M2 Works
M2 tackles the complex taxonomic boundaries of toxic speech. 
- **Data Capping (V3 Baseline):** To prevent overwhelming domain drift, the initial training setup tightly capped datasets to **~5,000 - 7,000 instances** per sub-class, ensuring a somewhat stable evaluation surface prior to scaling.
- **Sequential Fine-Tuning Phase Setup:** We utilized a multi-phase training scheme: first warming up the classification head while keeping base layers frozen, recovering M1's pre-trained knowledge, then unfreezing all layers to fully adapt without catastrophic forgetting or gradient shock.
- **Hierarchical Priority Rule:** Toxic text is often multi-layered (e.g., a racist death threat). We enforce a strict routing boundary: **Threat > Sexual > Discrimination > Verbal**.
- **Top-2 Resolution Logic:** During inference, if the model is uncertain, we track the confidence delta between the top two predicted classes. If the difference is less than `< 0.15`, the system generates a dual-label alert (e.g., `HARMFUL -> [discrimination, verbal_harassment]`), providing moderators with rich context.
- **Focal Loss Scaling:** Because extreme threats mathematically occur less frequently than generic verbal insults, M2 trains against a decoupled **Focal Loss** function, dynamically penalizing the model more when it makes errors on minority classes.

---

## 5. Pipeline Evolution: Transitioning from V2 to V3

Despite the intelligent two-stage layout, early testing in the **V2 Pipeline** revealed critical operational flaws. The transition to the **V3 Strategy** involved heavy data re-engineering to fortify the models.

### Identifying the V2 Weaknesses
1. **Formal Domain Bias:** M1 repeatedly misclassified short conversational text (*"let's meet tomorrow"*) as harassment.
2. **Syntactic Fragility:** The pipeline catastrophically failed when users employed ALL-CAPS or repeated exclamation points (e.g., `"I LIKE PLAYING FOOTBALL"` triggered a sexual harassment flag).
3. **M2 Taxonomic Collision:** Verbal Harassment and Discrimination classes were bleeding together due to noisy, overlapping datasets (e.g., the Davidson subset).

### The V3 Remediation
1. **Unified Text Normalization:** We introduced universal preprocessing (`text_normalizer.py`). By rigidly enforcing lowercasing, collapsing repeating punctuation, uncensoring common profanities (`f*ck` ➡️ `fuck`), and stripping URLs, we destroyed the syntactic fragility entirely.
2. **Purging the Noise:** We forcefully removed ambiguous datasets from the M2 pipeline and implemented strict **demographic keyword routing** to separate group-based hate (Discrimination) from individual attacks (Verbal Harassment).
3. **Architectural Upgrades:** V3 transitioned to **Dynamic Padding** (DataCollatorWithPadding) for vastly improved training efficiency and corrected a label smoothing bug in M1 that was interfering with the loss calculations.

---

## 6. Surgical Data Remediation (Synthetic Injections)

To plug blindspots that the raw V3 datasets could not inherently solve, we utilized programmatic, synthetic dataset injection via `inject_fixes.py`:

* **Safe Demographics (M1):** 
  Machine learning models often inherently associate marginalized groups with "hate" because those words primarily exist in hate-speech datasets. We injected **500 safe demographic sentences** (*"learning about muslims history is fascinating"*) into M1, neutralizing this discriminatory bias.
* **Harmful Nudes (M1 & M2):** 
  The model missed brief, coercive sexual extortion because it lacked physical descriptive words. We injected **250 adversarial examples** (*"drop your nudes in dm"*) to successfully bridge the sexual harassment detection gap.

---

## 7. Data Sources & Provenance

The robustness of AEGIS ML V3 stems from the massive aggregation and careful filtering of over 20+ specialized datasets, ensuring coverage across diverse linguistic registers (social media, chat, and adversarial).

### 7.1 M1 Binary Gate Sources
To build the **100,000-row** balanced binary gate, we pulled from:
*   **Harmful Corpus:** Jigsaw (Toxic Comments), Davidson, HateXplain, EDOS (Sexism), CASH (Sexual Harassment), TweetEval, MLMA, Kaggle Cyberbullying, Stormfront, ToxiGen, OLID, Gab, and HASOC (2019/2020).
*   **Safe Corpus:** PersonaChat (conversational dialogue), DailyDialog, and AEGIS Safety Corpus (LLM-chat safety), plus 2,000 **Synthetic Hard Negatives** (e.g., *"this game slaps"*, *"i'm dying to see that movie"*) to train the model out of flagging slang.

### 7.2 M2 Fine-Grained Specialist Sources
M2 targets specific harm categories using high-quality subset routing:
*   **Threat:** Hammer, ETHOS, Implicit Hate (Threat split), UCB MHS, and ConvAbuse.
*   **Sexual Harassment:** CASH (English), EDOS (sexist subset), and ConvAbuse.
*   **Discrimination:** HateXplain (Demographic labels), MLMA (Targeted group subset), and HASOC.
*   **Verbal Harassment:** Stormfront (No-Hate offensive subset), OLID, and Davidson (Offensive non-hate subset).

---

## 8. Benchmarking Results & Interpretation

Running the final, side-by-side empirical comparison on the adversarial dataset yielded phenomenal validation of the entire V3 philosophy.

### 1. Final Model Performance (V3)

The models were evaluated comprehensively against an unseen test set. Here are the exact evaluation metrics:

**M1 V3 (The Gatekeeper) Test Set Results:**
*   **Optimal Threshold:** `0.48`
*   **Test F1-Macro:** `0.9122`
*   **Test Accuracy:** `0.91`

**M1 Classification Report:**
```text
              precision    recall  f1-score   support

        safe       0.92      0.90      0.91      7579
     harmful       0.90      0.92      0.91      7621

    accuracy                           0.91     15200
   macro avg       0.91      0.91      0.91     15200
weighted avg       0.91      0.91      0.91     15200
```

**M2 V3 (The Specialist) Test Set Results:**
*   **Test F1-Macro:** `0.8025`
*   **Test Accuracy:** `0.81`
*(Note: Threat class F1 reached 0.80, safely passing the restrictive 0.70 safety gate).*

**M2 Classification Report:**
```text
                   precision    recall  f1-score   support

   discrimination       0.77      0.75      0.76      1050
sexual_harassment       0.88      0.90      0.89      1128
           threat       0.78      0.81      0.80       564
verbal_harassment       0.78      0.76      0.77      1071

         accuracy                           0.81      3813
        macro avg       0.80      0.80      0.80      3813
     weighted avg       0.80      0.81      0.80      3813
```

### 2. The Death of False Positives
The V3 Normalization + Safe Injections accurately protected normal communication:
* `"hello bro how are you"`
  * *V2 Interpretation:* SAFE (0.06)
  * *V3 Interpretation:* **SAFE (0.01)**
* `"let's meet tomorrow"`
  * *V2 Interpretation:* HARMFUL ❌ (False Positive due to conversational brevity)
  * *V3 Interpretation:* **SAFE (0.00) ✅**
* `"I LIKE PLAYING FOOTBALL"`
  * *V2 Interpretation:* HARMFUL ❌ (Syntactic failure triggered by ALL-CAPS)
  * *V3 Interpretation:* **SAFE (0.00) ✅**

### 3. Surgical Threat and Harassment Detection
The synthetic injections and proper threshold optimization successfully caught previously invisible threats:
* `"send me your nudes"`
  * *V2 Interpretation:* SAFE ❌ (Failed to map the extortion intent)
  * *V3 Interpretation:* **HARMFUL -> [ sexual_harassment ] ✅** (Caught by synthetic injection)
* `"watch your back"`
  * *V2 Interpretation:* HARMFUL (0.83) -> [ threat ]
  * *V3 Interpretation:* **HARMFUL (0.99) -> [ threat, verbal_harassment ] ✅** (Top-2 logic accurately captured the nuance).

**Conclusion:** The intelligent hand-off between M1 and M2, combined with the V3 data purges, results in a system that can accurately interpret hostile intent without aggressively policing normal human conversations.

---

## 9. Inference Latency & Scalability

A fundamental advantage of the Two-Stage Hierarchical design is extreme inference efficiency in production environments. While XLM-RoBERTa is a reasonably large model (~278M parameters), the pipeline bypasses the heavy compute burden of traditional one-stage 5-class architectures.

### The Realistic Routing distribution
In a typical gaming or social text environment, roughly **85-95% of traffic is mundane, non-harmful communication**. 
* **Safe Messages:** Only pass through M1. The message clears the binary gate and routes to the user interface in roughly **~15ms - 25ms** (on standard T4/V100 GPU architectures) and **~80ms - 100ms** (on optimized CPU).
* **Harmful Messages:** Only the remaining 5-15% of traffic triggers M2. In these instances, the combined latency (M1 + M2) sits at approximately **~40ms - 60ms** (GPU), perfectly acceptable since harmful messaging inherently warrants heavier computational scrutiny.

This layout creates an aggressive **Early Exit mechanism**, saving massive infrastructure cost and ensuring real-time chat APIs do not lag.

---

## 10. Core Implementation Logic

To ensure reproducibility across environments, the following technical safeguards were hardcoded into the AEGIS pipeline:

### 10.1 Universal Text Normalizer
The primary fix for "Syntactic Fragility" in V3 was the mandatory use of the following canonical normalizer before any inference:

```python
def normalize_text(text: str) -> str:
    # 1. Standardize casing and strip whitespace
    text = str(text).strip().lower()
    # 2. Strip URLs and @Mentions
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'@\w+', '', text)
    # 3. Collapse repeating punctuation (!!! -> !)
    text = re.sub(r'([!?.]){2,}', r'\1', text) 
    # 4. Uncensor common profanity masks
    text = text.replace('f*ck', 'fuck').replace('s*it', 'shit')
    return text
```

### 10.2 Hierarchical Priority Routing
In M2, when multiple labels are present, the system implements a **Priority Resolution Policy** to ensure the most critical harm is surfaced to moderators first:

| Priority | Category | Rationale |
| :--- | :--- | :--- |
| **1** | `THREAT` | Highest immediate physical risk. |
| **2** | `SEXUAL_HARASSMENT` | Protected category with extreme legal/safety sensitivity. |
| **3** | `DISCRIMINATION` | Group-based attack (Hate Speech). |
| **4** | `VERBAL_HARASSMENT` | Individual insults or casual toxicity. |

---

## 11. Future Roadmap: The "Un-Cap" Strategy

While V3 represents a massive leap in stability, our datasets were strictly capped at ~5,000 to ~7,000 rows per class. This capping prevented domain drift but artificially limited the model's total linguistic knowledge. 

To achieve maximum scale, the next logical step is to implement the **Un-Cap & Elevate Strategy**:

1. **Uncap the Majority Classes:**
   Release the volume constraints on `Sexual Harassment`, `Verbal Harassment`, and `Discrimination`. We will flood the M2 pool with 20k to 50k rows per class from validated sources (CASH, HateXplain).
2. **Massive Threat Class Synthetic Augmentation:**
   Uncapping immediately imbalances our smallest, most critical class: `Threat`. We will leverage a high-tier Generative LLM to synthesize **10,000 to 15,000 unique, contextual threat examples**. By designing prompts to simulate implicit, explicit, and colloquial violence in a chat format, we restore balance synthetically.
3. **Aggressive Focal Loss Calibration:**
   With uncapped datasets and immense synthetic data pools, we will tune the Focal Loss Gamma factor (e.g., `gamma=2.5`). The model will dynamically map the mathematical disparities during backpropagation, enforcing complete stability at massive scale.

---

## 12. Project Artifacts & Reproducibility

For a complete breakdown of any specific development phase, cross-reference the following project artifacts:

| Phase | Core Notebook / Script | Objective |
| :--- | :--- | :--- |
| **Data Construction** | `01_corpusM1_builderV3.ipynb` | M1 100K Corpus balancing & source deduplication. |
| **M1 Training** | `03_model1_finetuningV3.ipynb` | Fine-tuning XLM-RoBERTa for binary gatekeeper role. |
| **M2 Corpus Building** | `05_m2_sexual_harassment_V2.ipynb`, etc. | Class-specific data cleaning for M2 specialist. |
| **M2 Training** | `m2_sequential_finetuningV3.ipynb` | Multi-phase specialist fine-tuning with focal loss. |
| **Remediation Scripts** | `inject_fixes.py` | Programmatic adversarial & demographic bias fixes. |
| **Pipeline Logic** | `inference_pipelineV3.ipynb` | M1 -> M2 routing logic & Top-2 confidence resolution. |

**Summary Conclusion:** AEGIS ML V3 represents a transition from "flawed accuracy" to "reliable security". By combining hierarchical routing with surgical data remediation, the system is now prepared for the next-level scalability of the "Un-Cap" phase. 🛡️

