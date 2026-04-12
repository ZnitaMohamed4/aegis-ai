import os
import json
import requests
import logging

logger = logging.getLogger(__name__)


def analyze_grey_zone(raw_text, primary_class, confidence, m1_score):
    """
    Agent 3: Called when M2 confidence is below 0.75.
    Returns one of: BLOCK, WARN, ALLOW, HUMAN_REVIEW
    HUMAN_REVIEW means the LLM itself is too uncertain — send to human admin.
    """
    api_key = os.getenv('GROQ_API_KEY')
    model = os.getenv('GROQ_MODEL', 'mixtral-8x7b-32768')

    if not api_key:
        logger.error("[AEGIS] GROQ API KEY MISSING")
        return {"decision": "HUMAN_REVIEW", "category": primary_class, "explanation": "API Key missing, sent to human review."}

    prompt = f"""[AEGIS CHILD-SAFETY CLASSIFIER — STRICT MODE]
You protect children on WhatsApp. A message was flagged as potentially harmful.

Message: "{raw_text}"
ML suggestion: {primary_class} | M2 confidence: {confidence:.2f} | M1 toxicity: {m1_score:.2f}

Classify into exactly ONE category using STRICT definitions:

THREAT: Direct or implied physical violence or real-world harm (e.g. "I will hurt you", "I'll kill you").
SEXUAL_HARASSMENT: Any sexual advance, objectification, explicit content, predatory compliments, requests for intimacy, bed/sex references, or age-restricted content directed at someone (e.g. "I want you in my bed", "send me pics", "can we have +18 chat", "you look so hot").
DISCRIMINATION: Hatred targeting a protected group (race, religion, gender, nationality).
VERBAL_HARASSMENT: General insults, rudeness, threats without physical component or sexual element.
SAFE: Clearly benign — sarcasm, friendly chat, complaints without targeting anyone.

Decision rules — apply in order:
1. If the message is CLEARLY sexual in nature → BLOCK + sexual_harassment
2. If it contains physical threat → BLOCK + threat
3. If it is clearly a general insult/rude → WARN + verbal_harassment
4. If it is clearly safe/benign → ALLOW + safe
5. If you are GENUINELY UNSURE even after analysis (context is ambiguous, could be either harmful or safe) → respond with HUMAN_REVIEW

IMPORTANT: If you choose HUMAN_REVIEW, set explanation to a single phrase explaining WHY it is ambiguous.

Respond ONLY in valid JSON. Explanation max 12 words:
{{"decision": "BLOCK|WARN|ALLOW|HUMAN_REVIEW", "category": "threat|sexual_harassment|discrimination|verbal_harassment|safe", "explanation": "<12 words max>"}}"""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,   # Fully deterministic
                "max_tokens": 80
            },
            timeout=5
        )

        if response.status_code != 200:
            logger.error(f"[AEGIS] Groq API Rejected: {response.text}")
            return {"decision": "HUMAN_REVIEW", "category": primary_class, "explanation": "Groq API error, sent to human review."}

        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()

        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        parsed = json.loads(content)

        # Ensure decision is one of the valid values
        valid_decisions = {"BLOCK", "WARN", "ALLOW", "HUMAN_REVIEW"}
        if parsed.get("decision", "").upper() not in valid_decisions:
            parsed["decision"] = "HUMAN_REVIEW"

        return parsed

    except Exception as e:
        logger.error(f"[AEGIS] Groq LLM Error: {e}")
        return {"decision": "HUMAN_REVIEW", "category": primary_class, "explanation": "LLM failed, sent to human review."}
