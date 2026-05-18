# AEGIS ML V3 — Final Implementation Plan

> [!IMPORTANT]
> This is the **final, definitive** plan. All dataset investigations are complete. No TBD entries remain. Ready for execution upon approval.

---

## 0. Datasets Evaluated & Dropped

| Dataset | Reason Dropped |
|---------|---------------|
| **TRAC-3** (threat_gap/ files) | Bengali/Hindi, not English |
| **TRAC-1** (Facebook corpus) | Hindi code-mixing, Indian political domain only |
| **Waseem & Hovy** (`waseem_hovy_2016.csv`) | Contains tweet IDs only (integers), no actual text — unusable |
| Golbeck, SafeCity, CAD, WOAH 2021 | Require author email / not downloaded — out of scope |

---

## 1. Shared Text Normalizer

Applied to **every** corpus builder + **every** training notebook tokenizer:

```python
import re

def normalize_text(text: str) -> str:
    """Canonical text normalization for AEGIS pipeline."""
    text = str(text).strip()
    text = text.lower()
    text = re.sub(r'https?://\S+|www\.\S+', '', text)      # URLs
    text = re.sub(r'@\w+', '', text)                         # @mentions
    text = re.sub(r'#(\w+)', r'\1', text)                    # #hashtags → hashtags
    text = re.sub(r'rt\s+', '', text)                        # RT prefix
    text = re.sub(r'&amp;', '&', text)                       # HTML entities
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'<user>', '', text)                       # HateXplain tokens
    text = re.sub(r'\s+', ' ', text).strip()                 # collapse whitespace
    return text
```

---

## 2. M1 V3 — Safe Class Enrichment

### The Problem
M1's safe class = PersonaChat + DailyDialog + EDOS-safe + AEGIS-safe. All dialogue or commentary register. Short casual statements (*"i like this game"*) are distributionally absent → model learned "anything that doesn't look like PersonaChat = harmful".

### The Fix: Hard Negatives from Existing Datasets

Every harmful dataset you have also contains **safe examples you're currently throwing away**. These safe examples are from the *exact same register* as the harmful data.

| # | Safe Source | Path / Filter | Expected Rows | Why Essential |
|---|------------|---------------|---------------|---------------|
| 1 | PersonaChat | existing | ~20,000 | Base conversational |
| 2 | DailyDialog | existing | ~20,000 | Base conversational |
| 3 | EDOS not-sexist | `edos.csv` → `label_sexist='not sexist'` | ~14,000 → cap 3,000 | Gender-topic hard negatives |
| 4 | AEGIS safe | `aegis_safety_corpus` → majority-vote Safe | ~3,958 → cap 1,500 | LLM-chat coverage |
| 5 | **Kaggle not_cyberbullying** | `cyberbullying_tweets.csv` → `type='not_cyberbullying'` | 7,945 → cap 5,000 | Same register as harmful Kaggle |
| 6 | **TweetEval label=0** | `tweeteval_offensive.csv` → `label=0` | 7,975 → cap 5,000 | Twitter safe tweets |
| 7 | **Davidson class=2** | `davidson.csv` → `class=2` (neither) | 4,163 → cap 3,000 | Same source as harmful Davidson |
| 8 | **OLID NOT** | `olid_full.tsv` → `subtask_a='NOT'` | 8,840 → cap 2,500 | Same source as harmful OLID |
| 9 | **Stormfront noHate** | `stormfront_hate_speech18.csv` → `label='noHate'` | 9,507 → cap 2,000 | Hardest negatives (from hate forum) |
| 10 | **HASOC NOT** | HASOC 2019 `task_1='NOT'` + 2020 `task1='NOT'` | 4,456 + 2,637 = 7,093 → cap 3,000 | English tweets, same register as harmful HASOC |
| 11 | **Synthetic hard negatives** | Template-generated (see below) | ~2,000 | Plug surface-pattern gaps |
| | **TOTAL SAFE** | | **~67,000 → cap to 50,000** | |

Harmful pool stays at ~45–50K from current V2 sources. **Final M1 V3: ~100K rows, 50/50 balanced.**

#### Synthetic Hard Negative Templates (~2,000 rows)
```python
safe_templates = [
    "i like {}", "let's {} tomorrow", "wanna {} later?",
    "come {} with me", "let's meet at {}", "did you try {}",
    "this {} will make you laugh", "that {} is killer",
    "{} is deadly good", "i'm dying to see {}", "this {} slaps",
    "you should check out {}", "i love that {}",
    "have you seen {}?", "{} is my favorite",
]
fillers = ["game", "movie", "song", "show", "restaurant", "park",
           "cafe", "class", "gym", "place", "series", "album"]
```

> [!TIP]
> The key insight: we're adding safe data **from the exact same platforms** as the harmful data. This teaches M1: being informal/short/tweet-like doesn't make text harmful — it's the *content* that matters.

---

## 3. M2 V3 — Full Routing Redesign

### Design Principle: **Each source → EXACTLY ONE class. No double-dipping.**

---

### 🔴 Threat Class V3

| Source | Path / Filter | Rows | Status |
|--------|---------------|------|--------|
| Hammer | `threat_gap/hammer_threat.csv` | ~1,191 | ✅ Keep |
| UCB MHS | `ucb_mhs.csv` → violence mean ≥ 3.0 | ~2,250 | ✅ Keep |
| EDOS threats | `edos.csv` → `label_category='1. threats...'` | ~318 | ✅ Keep |
| InViS | `invis.tdf` → Violence=Yes, Sexual Violence≠Yes | ~232 | ✅ Keep |
| Jigsaw | `jigsaw/train.csv` → threat=1, ≤30 words, keyword filter | ~199 | ✅ Keep |
| ETHOS | `threat_gap/ethos_threat.csv` | ~45 | ✅ Keep |
| ConvAbuse threat | `threat_gap/convabuse_threat.csv` | ~71 | ✅ Keep |
| AEGIS threat | majority-vote Threat from aegis_safety | ~50 | ✅ Keep |
| **ImplicitHate** | `threat_gap/implicit_hate_threat.csv` | ~~1,838~~ | ❌ **REMOVE** → Discrimination |
| **TRAC-3 threat** | — | — | ❌ **REMOVED** (not English) |
| **TOTAL** | | **~4,356** | Smaller but CLEANER |

> [!WARNING]
> Removing Implicit Hate drops ~1,838 rows, but these are mislabeled ("white faces will soon be a minority" = discrimination, not threat). Keeping them poisons the threat/discrimination boundary.

---

### 🔵 Sexual Harassment Class V3

| Source | Path / Filter | Rows | Status |
|--------|---------------|------|--------|
| EDOS derog + animosity | `edos.csv` → categories 2 + 3 | ~3,936 | ✅ Keep |
| SBIC | `sbic_social_bias_frames.csv` → sexYN≥0.5 + offensiveYN≥0.5 | ~3,996 | ✅ Keep |
| AEGIS sexual | majority-vote sexual labels from aegis_safety | ~439 | ✅ Keep |
| ConvAbuse sexual | `threat_gap/convabuse_sexual_harassment.csv` | ~287 | ✅ Keep |
| InViS sexual | `invis.tdf` → Sexual Violence=Yes | ~16 | ✅ Keep |
| **CASH (RE-ADD)** | `cash_sexual_harassment_en.csv` → direct-attack filter | ~3,000 | 🆕 **ADD** |
| **TRAC-3 sexual** | — | — | ❌ **REMOVED** (not English) |
| **TOTAL** | | **~11,674 → cap ~7,000** | |

> [!IMPORTANT]
> **CASH must be re-added.** It's in M1's harmful pool but was commented out of M2. This creates a distribution shift — M1 flags CASH patterns as harmful, but M2 never learned to classify them.
>
> **Filter CASH** to only include direct-attack patterns (not victim narratives):
> ```python
> DIRECT_PATTERNS = r'\b(you|your|ur|send|show|give|let me|suck|fuck)\b'
> df_cash = df_cash[df_cash['text'].str.contains(DIRECT_PATTERNS, case=False)]
> ```

---

### 🟢 Verbal Harassment Class V3

> [!CAUTION]
> This class needs the most work. Current state: 65% Davidson (noisy, 46% annotator agreement) + 25% Kaggle (30% label noise from spot-check) = **~70% of the corpus is unreliable.**

| Source | Path / Filter | Rows | Status |
|--------|---------------|------|--------|
| **Davidson class=1** | — | ~~4,234~~ | ❌ **REMOVE** (too noisy, double-dips) |
| TweetEval Offensive | `tweeteval_offensive.csv` → `label=1` | ~3,941 → keep all after dedup | ✅ Keep (uncapped) |
| **HateXplain offensive (FIXED)** | `hatexplain.json` → majority-vote `label='o'` | ~5,761 | 🆕 **FIX + ADD** |
| **OLID IND** | `olid_full.tsv` → `subtask_a='OFF'` + `subtask_c='IND'` | ~2,507 | 🆕 **ADD** |
| **HASOC OFFN** | HASOC 2019 `task_2='OFFN'` + 2020 `task2='OFFN'` | 522 + 490 = ~1,012 | 🆕 **ADD** |
| Kaggle (keyword-filtered) | `cyberbullying_tweets.csv` → `type='other_cyberbullying'` + insult keywords | ~1,500 | 🔧 Keep + filter |
| ConvAbuse verbal | `threat_gap/convabuse_verbal_harassment.csv` | ~210 | ✅ Keep |
| **TRAC-3 verbal** | — | — | ❌ **REMOVED** (not English) |
| **TOTAL** | | **~14,931 → cap ~7,000** | Clean, diverse |

**Key changes explained:**

1. **Drop Davidson entirely** — 46% inter-annotator agreement, dominant source (65%) creating confusion
2. **Fix HateXplain parser** — The JSON uses nested annotator arrays. Current code tries `label_orig='offensive'` but the parsed data has labels as `'o'`, `'h'`, `'n'`. Fix:
   ```python
   # HateXplain correct parsing
   with open(hatexplain_path, 'r') as f:
       data = json.load(f)
   
   rows = []
   for post_id, entry in data.items():
       tokens = entry.get('post_tokens', [])
       text = ' '.join(tokens)
       # Majority vote across annotators
       annotator_labels = [a['label'] for a in entry.get('annotators', [])]
       from collections import Counter
       majority = Counter(annotator_labels).most_common(1)[0][0]
       rows.append({'text': text, 'label': majority})
   
   df_hx = pd.DataFrame(rows)
   # Filter for offensive (label='offensive' in original, stored as full string)
   df_hx_offensive = df_hx[df_hx['label'] == 'offensive']  # ~5,761 rows
   ```
3. **Add OLID IND** — `subtask_c='IND'` = individual-targeted insults = perfect verbal harassment
4. **Add HASOC OFFN** — English tweets labeled as offensive (without group targeting)
5. **Clean Kaggle** — add keyword filter to remove ~30% false positives:
   ```python
   INSULT_KW = ['stupid', 'idiot', 'dumb', 'ugly', 'hate you', 'shut up',
                'loser', 'pathetic', 'disgusting', 'ass', 'bitch',
                'fuck', 'dick', 'moron', 'trash', 'worthless', 'clown']
   df_kaggle = df_kaggle[df_kaggle['text'].str.lower().str.contains('|'.join(INSULT_KW))]
   ```

---

### 🟡 Discrimination Class V3

| Source | Path / Filter | Rows | Status |
|--------|---------------|------|--------|
| **Davidson class=0** | — | ~~1,399~~ | ❌ **REMOVE** (double-dipping) |
| HateXplain hatespeech | `hatexplain.json` → majority `label='hatespeech'` + demographic keyword filter | ~4,000 | 🔧 Keep + filter |
| Implicit Hate (FULL) | `threat_gap/implicit_hate_threat.csv` + existing disc slice | ~3,000 | 🔧 Consolidate both slices |
| OLID GRP | `olid_full.tsv` → `subtask_c='GRP'` | ~696 | ✅ Keep |
| UCB MHS disc | existing filter | ~227 | ✅ Keep |
| ConvAbuse disc | `threat_gap/convabuse_discrimination.csv` | ~63 | ✅ Keep |
| **ToxiGen** | `toxigen_adversarial.csv` → `toxicity_human >= 2.5` | ~4,000 | 🆕 **ADD** |
| **Stormfront hate** | `stormfront_hate_speech18.csv` → `label='hate'` | ~1,196 | 🆕 **ADD** |
| **HASOC HATE** | HASOC 2019 `task_2='HATE'` + 2020 `task2='HATE'` | 1,267 + 216 = ~1,483 | 🆕 **ADD** |
| **Waseem & Hovy** | — | — | ❌ **DROPPED** (tweet IDs only, no text) |
| **TRAC-3 disc** | — | — | ❌ **REMOVED** (not English) |
| **TOTAL** | | **~14,665 → cap ~7,000** | Strict demographic targeting |

**Demographic keyword filter for HateXplain hatespeech:**
```python
DEMOGRAPHIC_KW = [
    'black', 'white', 'asian', 'muslim', 'jew', 'immigrant', 'women',
    'gay', 'trans', 'mexican', 'arab', 'refugee', 'nigger', 'fag',
    'chink', 'spic', 'kike', 'cracker', 'wetback', 'coon',
    'race', 'religion', 'country', 'your kind',
    'go back', 'all of them', 'those people'
]
df_hx_hate = df_hx_hate[df_hx_hate['text'].str.lower().str.contains('|'.join(DEMOGRAPHIC_KW))]
```

---

## 4. Before vs. After Summary

````carousel
### 🔴 Threat
```diff
BEFORE (6,144 rows):
  UCB_MHS              2,250
  ImplicitHate         1,838  ← MISLABELED
  Hammer               1,191
  EDOS                   318
  Jigsaw                 199
  InViS                  117
  ConvAbuse               71
  AEGIS                   50
  ETHOS                   45

AFTER (~4,356 rows — CLEANER):
  UCB_MHS              2,250  (kept)
  Hammer               1,191  (kept)
  EDOS                   318  (kept)
  Jigsaw                 199  (kept)
  InViS                  117  (kept)
  ConvAbuse               71  (kept)
  AEGIS                   50  (kept)
  ETHOS                   45  (kept)
- ImplicitHate         REMOVED → discrimination
- TRAC-3 threat        REMOVED (not English)
```
<!-- slide -->
### 🔵 Sexual Harassment
```diff
BEFORE (~6,500 rows):
  EDOS derog+animosity 3,936
  SBIC                 3,996
  AEGIS                  439
  ConvAbuse              287
  InViS                   16
  CASH                EXCLUDED!

AFTER (~11,674 → cap 7,000):
  EDOS derog+animosity 3,936  (kept)
  SBIC                 3,996  (kept)
+ CASH (direct-attack) ~3,000 (RE-ADDED)
  AEGIS                  439  (kept)
  ConvAbuse              287  (kept)
  InViS                   16  (kept)
- TRAC-3 sexual        REMOVED (not English)
```
<!-- slide -->
### 🟢 Verbal Harassment
```diff
BEFORE (6,500 rows — 70% NOISY):
  Davidson class=1     4,234  (65%) ← NOISY
  Kaggle other_cb      1,653  (25%) ← 30% NOISE
  TweetEval Off          613  ( 9%)

AFTER (~14,931 → cap 7,000 — CLEAN):
- Davidson             REMOVED (too noisy)
  TweetEval Off        3,941  (kept, uncapped)
+ HateXplain off      ~5,761  (FIXED parser)
+ OLID IND            ~2,507  (individual-targeted)
+ HASOC OFFN          ~1,012  (English tweets)
  Kaggle (filtered)   ~1,500  (keyword cleaned)
  ConvAbuse verbal       210  (kept)
- TRAC-3 verbal        REMOVED (not English)
```
<!-- slide -->
### 🟡 Discrimination
```diff
BEFORE (7,250 rows — generic insults mixed in):
  HateXplain hate      4,153  (unfiltered)
  ImplicitHate→disc    1,683
  Davidson class=0     1,399  ← DOUBLE-DIP
  OLID GRP               696
  UCB_MHS disc            227
  ConvAbuse disc           44

AFTER (~14,665 → cap 7,000 — DEMOGRAPHIC-ONLY):
- Davidson             REMOVED (double-dip)
  HateXplain (filtered) ~4,000  (demographic kw)
  ImplicitHate (FULL)  ~3,000  (consolidated)
+ ToxiGen             ~4,000  (group-targeted)
+ Stormfront hate     ~1,196  (white supremacist)
+ HASOC HATE          ~1,483  (English tweets)
  OLID GRP               696  (kept)
  UCB_MHS disc            227  (kept)
  ConvAbuse disc            63  (kept)
- Waseem & Hovy        DROPPED (no text, IDs only)
- TRAC-3 disc          REMOVED (not English)
```
````

---

## 5. Notebook Deliverables

### [NEW] `01_corpusM1_builderV3.ipynb`
- `normalize_text()` on all text
- 11 safe sources (PersonaChat, DailyDialog, EDOS-safe, AEGIS-safe, Kaggle-safe, TweetEval-safe, Davidson-safe, OLID-NOT, Stormfront-noHate, HASOC-NOT, synthetic)
- Same harmful pool as V2 + normalize
- Target: ~100K rows (50K/50K)

### [NEW] `04_m2_threat_corpus_builderV2.ipynb`
- Remove Implicit Hate (→ discrimination)
- Remove TRAC-3
- Add `normalize_text()`
- Expected: ~4,356 rows

### [NEW] `05_m2_sexual_harassment_corpusV2.ipynb`
- Re-add CASH with direct-attack filter
- Remove TRAC-3
- Add `normalize_text()`
- Expected: ~11,674 → cap 7,000

### [NEW] `06_m2_verbal_harassment_corpusV2.ipynb`
- Remove Davidson entirely
- Fix HateXplain parser (join `post_tokens`, majority-vote label, filter `label='offensive'`)
- Add OLID IND (`subtask_c='IND'`)
- Add HASOC OFFN
- Clean Kaggle with insult keyword filter
- Keep ConvAbuse verbal
- Add `normalize_text()`
- Expected: ~14,931 → cap 7,000

### [NEW] `07_m2_discrimination_corpusV3.ipynb`
- Remove Davidson entirely
- Add demographic keyword filter on HateXplain hatespeech
- Consolidate Implicit Hate (move threat slice + keep disc slice → all discrimination)
- Add ToxiGen (toxicity_human ≥ 2.5)
- Add Stormfront hate
- Add HASOC HATE
- Drop Waseem & Hovy (no text)
- Remove TRAC-3
- Add `normalize_text()`
- Expected: ~14,665 → cap 7,000

### Training Notebook Diffs (Apply in Colab)

**`03_model1_finetuningV2.ipynb`:**
```diff
- label_smoothing_factor=0.1,
+ label_smoothing_factor=0.0,
```

**`m2_sequential_finetuningV2.ipynb`:**
```diff
# Tokenizer: dynamic padding instead of static
- padding='max_length',
- max_length=64,
+ padding=True,

# Add DataCollatorWithPadding
+ from transformers import DataCollatorWithPadding
+ data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

# Trainer: add collator
  trainer = Trainer(
      ...
+     data_collator=data_collator,
  )

# FocalLoss: remove explicit class weights
- class_weights = torch.tensor([1.2, 1.5, 1.0, 1.3]).to(device)
+ # Let Focal Loss handle hard examples without double-amplification
+ # gamma=2.0 already down-weights easy examples sufficiently
```

---

## 6. HASOC Integration Details

**Source files on Drive:**
```
/content/drive/MyDrive/AEGIS_ML/data/raw/hosoc_english/
├── english_dataset_2019/
│   ├── english_dataset.tsv          (5,852 rows)
│   └── hasoc2019_en_test-2919.tsv   (1,153 rows)
└── english_dataset_2020/
    ├── hasoc_2020_en_train_new.xlsx  (3,708 rows)
    └── hasoc_2020_en_test_new.xlsx   (1,592 rows)
```

**Combined: 12,305 English rows**

**Routing map:**

| HASOC Label | Our Class | Rows | Logic |
|-------------|-----------|------|-------|
| `task_2/task2 = 'HATE'` | **Discrimination** | ~1,483 | Group-targeted hate speech |
| `task_2/task2 = 'OFFN'` | **Verbal Harassment** | ~1,012 | Offensive, individual-level |
| `task_2/task2 = 'PRFN'` | **SKIP for M2** | ~2,717 | Casual profanity ≠ harassment (*"I fucking love life"*) |
| `task_1/task1 = 'NOT'` | **M1 Safe** | ~7,093 | Hard negatives, same tweet register |
| *All HOF rows* | **M1 Harmful** | ~5,212 | For M1 binary gate only |

> [!NOTE]
> PRFN (profanity) is skipped for M2 because spot-check shows many are positive/neutral sentiment with casual swearing (*"SUCH A FUCKING BEAST HONESTLY"*, *"I fucking love life !!!"*). These would add noise to verbal harassment. They ARE used for M1 harmful since HASOC annotators marked them as HOF.

**Loading code:**
```python
import pandas as pd

# HASOC 2019
h19_train = pd.read_csv(RAW / 'hosoc_english/english_dataset_2019/english_dataset.tsv', sep='\t')
h19_test  = pd.read_csv(RAW / 'hosoc_english/english_dataset_2019/hasoc2019_en_test-2919.tsv', sep='\t')
h19 = pd.concat([h19_train, h19_test], ignore_index=True)
h19 = h19.rename(columns={'task_1': 'task1', 'task_2': 'task2'})

# HASOC 2020
h20_train = pd.read_excel(RAW / 'hosoc_english/english_dataset_2020/hasoc_2020_en_train_new.xlsx')
h20_test  = pd.read_excel(RAW / 'hosoc_english/english_dataset_2020/hasoc_2020_en_test_new.xlsx')
h20 = pd.concat([h20_train, h20_test], ignore_index=True)

# Combine
hasoc = pd.concat([h19[['text','task1','task2']], h20[['text','task1','task2']]], ignore_index=True)
```

---

## 7. Verification Plan

### Automated (in each notebook)
1. **Cross-corpus dedup** — no text appears in both discrimination AND verbal_harassment
2. **Normalization check** — all text lowercase, no raw URLs, no @mentions
3. **Label distribution** — M1 balanced (50/50), M2 classes within 2× of each other
4. **Train/val/test leakage** — zero text overlap across splits
5. **Source diversity** — no single source > 50% of any class

### Adversarial Test Cases (after retraining)

| Input | M1 Expected | M2 Expected |
|-------|-------------|-------------|
| *"i like this game"* | **Safe** (P<0.2) | — |
| *"let's meet tomorrow"* | **Safe** (P<0.2) | — |
| *"send me your nudes"* | Harmful (P>0.9) | sexual_harassment |
| *"TRASH"* vs *"trash"* | Same prediction | Same M2 class |
| *"watch yourself"* vs *"watch yourself !"* | Same | Same M2 class |
| *"idiot"* | Harmful | verbal_harassment |
| *"you people are all the same"* | Harmful | discrimination |
| *"i'll kill you"* | Harmful | threat |
| *"shut up loser"* | Harmful | verbal_harassment (not threat) |
| *"white people are ruining this country"* | Harmful | discrimination (not threat) |

---

## 8. Execution Order

```
Phase 1 — Corpus Building (notebooks, run on Colab):
  1. 01_corpusM1_builderV3.ipynb
  2. 04_m2_threat_corpus_builderV2.ipynb
  3. 05_m2_sexual_harassment_corpusV2.ipynb
  4. 06_m2_verbal_harassment_corpusV2.ipynb
  5. 07_m2_discrimination_corpusV3.ipynb

Phase 2 — Training (diffs applied in Colab):
  6. 03_model1_finetuningV3.ipynb  (label_smoothing=0.0)
  7. m2_sequential_finetuningV3.ipynb  (dynamic padding, focal loss fix)

Phase 3 — Validation:
  8. Run adversarial test suite
  9. Compare M1/M2 metrics vs V2 baseline
```
