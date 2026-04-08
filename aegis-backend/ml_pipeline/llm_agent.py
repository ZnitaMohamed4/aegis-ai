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

    # The Prompt - We act as a strict instructor
    prompt = f"""You are AEGIS, an expert AI safety agent protecting children on WhatsApp.
A message was flagged as potentially harmful by our local ML classifier.

Message: "{raw_text}"
ML Initial Category: {primary_class} (confidence: {confidence:.2f})
Toxicity Score: {m1_score:.2f}

Your task is to correct the ML model. DO NOT simply agree with the ML Initial Category. Think independently.

CRITICAL RULES:
1. Physical violence or implied consequences (e.g., "strangle", "see what happens") = 'threat' + BLOCK.
2. Targeting race, religion, nationality, group, or family = 'discrimination' + BLOCK.
3. General insults/rudeness without violence or prejudice = 'verbal_harassment' + WARN.
4. Pure sarcasm or safe chat = ALLOW.

Respond ONLY in valid JSON format, nothing else:
{{"decision": "BLOCK|WARN|ALLOW", "category": "threat|sexual_harassment|discrimination|verbal_harassment", "explanation": "Short 1 sentence reason."}}"""

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
