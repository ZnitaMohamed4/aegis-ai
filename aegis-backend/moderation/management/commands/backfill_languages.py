import os
import logging
import requests
import time
from django.core.management.base import BaseCommand
from moderation.models import ModerationResult
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '').strip('"').strip("'")
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'mixtral-8x7b-32768').strip('"').strip("'")

def detect_language_via_llm(text):
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set in .env! Returning 'en'")
        return "en"

    prompt = f"""You are an expert NLP language detector. Your ONLY task is to identify the language of the following short text.
    
    Text: "{text}"
    
    Identify if the text belongs to one of these 4 specific categories:
    - "fr" (French)
    - "ar" (Standard Arabic)
    - "darija" (Moroccan Arabic dialect, often written in Latin alphabet/numbers)
    - "en" (English)
    
    If it is none of the above or too short to tell, return "other".
    
    CRITICAL: YOU MUST RESPOND WITH ONLY A SINGLE WORD from the list above. No explanations. No punctuation.
    """
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": 10
            }
        )
        
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip().lower()
        
        if "darija" in content: return "darija"
        if "fr" in content or "french" in content: return "fr"
        if "ar" in content or "arabic" in content: return "ar"
        if "en" in content or "english" in content: return "en"
        return "other"

    except Exception as e:
        logger.warning(f"Groq API Error: {e}")
        if "429" in str(e):
            logger.info("Ratelimit hit, sleeping for 5 seconds...")
            time.sleep(5)
            # Try once more on rate limit
            try:
                response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json={
                        "model": GROQ_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                        "max_tokens": 10
                    }
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"].strip().lower()
                if "darija" in content: return "darija"
                if "fr" in content or "french" in content: return "fr"
                if "ar" in content or "arabic" in content: return "ar"
                if "en" in content or "english" in content: return "en"
                return "other"
            except:
                pass
        return "error"

class Command(BaseCommand):
    help = 'Backfill missing languages on historical ModerationResults using Groq LLM'

    def handle(self, *args, **options):
        # Only re-fetch failed or unclassified ones
        messages = ModerationResult.objects.filter(language__in=['error', 'other', 'en'])
        
        # Or just re-run all: ModerationResult.objects.all()
        messages = ModerationResult.objects.all()
        total = messages.count()
        self.stdout.write(self.style.WARNING(f'Starting Language Backfill with API KEY len {len(GROQ_API_KEY)} for {total} messages...'))
        
        updated = 0
        for i, msg in enumerate(messages, 1):
            if msg.language not in [None, '', 'error']: 
                # If we've got a valid flag, we can skip it, but let's re-eval if it's 'en' just to be 100% sure for Darija cases
                pass
                
            lang = detect_language_via_llm(msg.raw_text)
            
            if lang in ["fr", "ar", "darija", "en", "other"]:
                msg.language = lang
                msg.save(update_fields=['language'])
                self.stdout.write(self.style.SUCCESS(f"[{i}/{total}] '{lang}' -> {msg.raw_text[:40]}"))
                updated += 1
            else:
                self.stdout.write(self.style.NOTICE(f"[{i}/{total}] GROQ FAILED ('{lang}') -> {msg.raw_text[:40]}"))
                
        self.stdout.write(self.style.SUCCESS(f'\nBackfill Complete! {updated} messages checked and updated in DB.'))
