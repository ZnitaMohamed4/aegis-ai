import os
import json
import requests
import logging

logger = logging.getLogger(__name__)

def analyze_grey_zone(raw_text, primary_class, confidence, m1_score):
    """
    Agent 3: Called when M2 confidence is below 0.75!
    Asks Groq's Mixtral model for a final decision.
    """
    api_key = os.getenv('GROQ_API_KEY')
    model = os.getenv('GROQ_MODEL', 'mixtral-8x7b-32768')
    
    if not api_key:
        logger.error("[AEGIS] ❌ GROQ API KEY MISSING")
        return {"decision": "REVISE", "category": primary_class, "explanation": "API Key missing."}

    # The Prompt - High Precision, Minimal Length
    # High-Precision Kernel Directive
    prompt = f"""[SYSTEM: AEGIS CORE]
Resolve ML Classifier ambiguity. Default to independent verification.
DATA: {{msg: "{raw_text}", suggestion: {primary_class}, confidence: {confidence:.2f}}}

SEMANTIC BOUNDARIES:
1. THREAT: Implied/direct physical violence or real-world consequence.
2. DISCRIMINATION: Must target a SPECIFIC protected characteristic (race, religion, gender, family). If no specific identity is clear, default to verbal_harassment.
3. SEXUAL_HARASSMENT: Predatory avancées, advances, or objectification. Categorize as this even if disguised as a compliment (e.g. "you look hot").
4. VERBAL_HARASSMENT: General insults or rudeness WITHOUT targeting a protected identity or physical harm.
5. SAFE: Sarcasm, friendly banter, or benign criticism.

DECISION TREE:
- Hard identifiers (Identity/Violence) -> BLOCK.
- General Personal Insults -> WARN.
- No clear harm -> ALLOW.

OUTPUT ONLY JSON:
{{"decision": "BLOCK|WARN|ALLOW", "category": "threat|sexual_harassment|discrimination|verbal_harassment", "explanation": "Logic summary."}}"""

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
                "temperature": 0.1, # Keep it extremely logical, no creativity
                "max_tokens": 150
            },
            timeout=5 # Don't hang the system if Groq is down
        )
        
        # Parse the JSON response
        if response.status_code != 200:
            logger.error(f"[AEGIS] ❌ Groq API Rejected: {response.text}")
            return {"decision": "REVISE", "category": primary_class, "explanation": "Groq API Error"}
            
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()

        
        # Sometime LLMs wrap json in markdown blocks ```json 
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
            
        return json.loads(content)
        
    except Exception as e:
        logger.error(f"[AEGIS] ❌ Groq LLM Error: {e}")
        return {"decision": "REVISE", "category": primary_class, "explanation": "LLM failed or timed out."}
