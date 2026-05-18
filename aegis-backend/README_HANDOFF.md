# 🛡️ Aegis Assistant — AI Handoff Context & Plan

**To the AI reading this:** You are continuing a partially completed implementation of the "Aegis Assistant Bidirectional Protection" feature for the Aegis AI project (a WhatsApp parental control system built with Django, LangGraph, Groq, and Evolution API). Read this carefully to understand the context, what has been done, and what needs to be implemented next.

## 🌟 Project Context
Aegis is shifting from a passive "surveillance" tool to an active "digital ally". 
- **Instance 1 (Monitor):** Linked to the child's WhatsApp. It intercepts incoming/outgoing messages via webhook.
- **Instance 2 (Aegis Assistant Bot):** A second WhatsApp number that lives in the child's phone contacts. It acts as an empathetic chatbot to help the child regulate their behavior (self-moderation) and talk about issues.

The core pipeline is a LangGraph multi-agent system (`ml_pipeline/graph.py`):
- **Agent 1 & 2:** Gatekeeper + Classifier (Toxicity/Threat)
- **Agent 3:** Auditor (Groq LLM for ambiguous cases)
- **Agent 4:** Profiler (Bayesian Network Risk Scoring & Digital Twin update)
- **Agent 5:** Enforcer (WhatsApp actions: Delete, Warn, React, Alert)

---

## 🏗️ The 4-Phase Implementation Plan

### ✅ Phase 0: Data Export & Cleanup (COMPLETED)
- **Goal:** Export the golden dataset without losing data, classify Darija messages, and cleanly reset profiles.
- **Completed:** 
  - Ran `scripts/export_golden_dataset.py`. Exported 486 messages, deduplicated to 411, tagged languages using Groq (English, Darija, etc.), and saved JSONs to `../aegis-ml/digital_twin/data/`.
  - Ran `scripts/reset_profiles.py`. Reset 10 `UserBehaviorProfile` records to zero/LOW and deleted all `BehavioralSnapshot` records. Kept all original messages.

### ✅ Phase 1: SharedGroupsCount Observable (COMPLETED)
- **Goal:** Fix the "permanent stranger" bug caused by disappearing messages and implement the final missing Bayesian Network observable.
- **Completed:**
  - Added `fetch_shared_groups()` to `moderation/evolution_api.py`.
  - Added `shared_groups_metadata` JSONField to `UserBehaviorProfile` and ran Django migrations.
  - Updated `ml_pipeline/agents/profiler.py` to fetch and store shared groups on profile creation.
  - Enriched `ml_pipeline/agent_tools.py` (`fetch_risk_profile`) so Agent 3 (LLM) sees the exact group names, sizes, and creation dates for context.

### 🔄 Phase 2: Self-Moderation System (IN PROGRESS)
- **Goal:** Process the child's OUTGOING messages. If they say something toxic, delete it and send an educational DM via the Bot instance instead of a punitive warning.
- **Completed:** 
  - Modified `moderation/views/webhook.py` to remove the `fromMe` bypass, passing `is_from_me = True` into the LangGraph state.
- **TO DO NEXT:**
  1. **Update `moderation/models.py`**: Add `'EDUCATE'` to `ModerationResult.Decision` choices. Add `is_self_moderation` boolean to `ModerationResult`. Add a new `SelfModerationEvent` model.
  2. **Update `ml_pipeline/agents/enforcer.py`**: Add logic so that if `is_from_me == True` and the message is flagged (BLOCK/ESCALATE/WARN), it deletes the message for everyone (if applicable) and triggers an educational DM, plus a *constructive* parent alert.
  3. **Update `moderation/evolution_api.py`**: Implement `send_educational_dm(bot_instance_name, child_jid, category, original_text)` to send the DM from Instance 2. Implement `send_constructive_parent_alert(...)` which is softer than the standard alert.

### ⏳ Phase 3: Aegis Assistant Chatbot (PENDING)
- **Goal:** Create the standalone empathetic chatbot that lives on the new SIM card.
- **TO DO:**
  1. Ensure the new Evolution API instance (e.g., `aegis-bot`) is set up with the new SIM.
  2. Create `moderation/views/chatbot_views.py` with `webhook_chatbot` to receive direct messages from the child to the bot.
  3. Create `moderation/services/chatbot_service.py` to handle the conversational state and Groq LLM logic (empathetic system prompt, escalation keyword detection).
  4. Wire the URL in `urls.py` and export in `views/__init__.py`. Update `.env`.

### ⏳ Phase 4: Dashboard UI (PENDING)
- **Goal:** Display self-moderation events on the frontend.
- **TO DO:** Add a "Digital Citizenship" tab on the Parent Dashboard to frame the child's mistakes as learning opportunities.

---

## 🛠️ Key Files to Modify Next (Phase 2)
1. `/home/muhammed/Desktop/aegis-ai/aegis-backend/moderation/models.py`
2. `/home/muhammed/Desktop/aegis-ai/aegis-backend/ml_pipeline/agents/enforcer.py`
3. `/home/muhammed/Desktop/aegis-ai/aegis-backend/moderation/evolution_api.py`

## 🧠 Architectural Rules to Follow
- Do not use `time.sleep()`.
- Prioritize saving data for the ML retrain loop (e.g., preserving what the ML originally predicted vs what Agent 3 corrected).
- Remember the `is_from_me` flag determines if the message was sent BY the child.
- We have 1 monitored child, but the system must be built to support multiple. BlockRatio is per-sender, TargetBreadth handles multiple children.

Good luck! Start by finishing Phase 2.
