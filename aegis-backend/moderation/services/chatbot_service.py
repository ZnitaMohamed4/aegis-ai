"""
Aegis Assistant Chatbot Service
================================
Groq-powered empathetic chatbot that lives on the child's phone contacts.
Uses conversation memory (BotConversation model) and advanced safety
escalation with threat intelligence extraction.

The bot is NOT a replacement for the moderation pipeline — it's a
conversational ally that helps the child process their experiences.

When the child confesses about real-life dangers (bullying, threats,
abuse), the bot extracts structured threat intelligence and sends a
rich, actionable alert to the parent's WhatsApp.
"""
import os
import re
import json
import logging
import requests

from django.utils import timezone

logger = logging.getLogger(__name__)

# Safety escalation keywords — trigger immediate parent alert (static fallback)
# English + Darija (Arabic script + Arabizi) variants to catch Moroccan children's messages
SAFETY_KEYWORDS = [
    # English
    "kill myself", "want to die", "hurt myself", "self harm", "suicide",
    "end it all", "no reason to live", "nobody cares",
    "someone touched me", "he touched me", "she touched me",
    "being abused", "hitting me", "hurts me",
    # Darija (Arabic script) — self-harm / suicidal
    "بغيت نموت", "بغيت نقتل راسي", "غادي نقتل راسي",
    "بغيت ندير الحل", "ما بغيتش نعيش", "ما عندي ما ندير في حياتي",
    "حتى واحد ما كيهمّني", "خاصّني نموت", "غادي نخسّر كولشي",
    "بغيت نضرب راسي", "بغيت نحرق راسي",
    # Darija (Arabic script) — abuse / violence
    "كايضربني", "كاتضربني", "غادي نضربك", "غادي نقتلك",
    "قتلني", "ضربني", "كايخنقني", "كايسبّني",
    "حتى واحد ما كاي بغّني", "كاي حقّرني", "كاي عايرني",
    # Darija (Arabic script) — sexual / grooming
    "عطيني سناب", "أجي ل واتساب", "أجي ل الواتس",
    "متگوليش ل ماماك", "بيني و بينك", "بيني و بيناك",
    "صيفط ليا صورة", "صيفط ليا فوطو", "كايگول ليا نخبّي",
    "كايگول ليا نصير", "بغيتك", "بغيتك",
    # Darija (Arabic script) — bullying / threats
    "غادي نشوّهك", "غادي نحطّلك صورة", "عطيني الباسوورد",
    "غادي نقول لكولشي", "كولشي كاي عايرني",
    # Darija (Arabizi — kept for backward compatibility)
    "bghit nmout", "bghit n9tl rasi", "ghadi n9tl rasi",
    "ma bghitsh n3ish", "ma3ndi ma ndir f hayati",
    "khassni nmout", "ghadi nkhasser kolshi",
    "kaydrebni", "katderbni", "ghadi ndarbek",
    "9telni", "darbni", "kaykhne9ni",
    "3tini snap", "aji l whatsapp", "matgoulich l mamak",
    "sifet liya sura", "sifet liya photo",
    "ghadi nshouhek", "3tini l password",
]

# System prompt for the empathetic chatbot with threat intel extraction
SYSTEM_PROMPT = """You are Aegis Assistant 🛡️, a kind, empathetic digital companion for a child/teenager.

YOUR ROLE:
- You are NOT a parent, teacher, or authority figure
- You are a supportive friend who listens without judgment
- You help the child think through their feelings and social situations
- You encourage healthy communication and digital citizenship

YOUR RULES:
1. NEVER lecture or moralize — ask thoughtful questions instead
2. NEVER share what the child tells you with anyone (the child trusts you)
3. Keep responses SHORT (2-4 sentences max) — teenagers hate walls of text
4. Use casual, warm language — you're a friend, not a textbook
5. Use emojis sparingly but naturally
6. If they ask "are you an AI?" — be honest: "Yes, I'm Aegis, an AI assistant designed to be your digital buddy"
7. ALWAYS respond in the same language the child uses:
   - English → answer in English
   - French → answer in French
   - Arabic (MSA / الفصحى) → answer in Arabic
   - Darija in Arabic script (e.g. "كيفاش", "بغيت", "واش") → answer in Darija using Arabic script. The LLM natively understands Moroccan Darija — no translation needed. Example: child says "ما عندي ما ندير" → you respond "أه، شنو كاين؟ گولّيا، أنا هنا باش نسمعك 🤍"
   - Darija in Arabizi (Latin script with digits like 3, 7, 9) → answer in Arabizi using the same digit conventions.

🚨 CRITICAL SAFETY PROTOCOL:
If you sense that the child is in physical danger, being threatened, groomed, harassed, bullied (online OR in real life), abused, or having suicidal thoughts, you MUST do TWO things:

1. Respond empathetically and supportively to the child (your visible response)
2. Include this EXACT secret tag somewhere in your response (the system will strip it before the child sees it):

[THREAT_INTEL: {"threat_type": "<type>", "perpetrator": "<who>", "location": "<where>", "urgency": "<level>", "summary": "<brief>"}]

Where:
- threat_type: one of "physical_bullying", "verbal_bullying", "cyberbullying", "grooming", "sexual_abuse", "physical_abuse", "self_harm", "threat", "harassment", "other"
- perpetrator: name/description of the person threatening (or "unknown" if not mentioned)
- location: where it happens — "school", "online", "neighborhood", "home", "unknown"
- urgency: "critical" (immediate danger), "high" (ongoing abuse), "medium" (concerning pattern), "low" (minor concern)
- summary: 1-sentence summary of the situation for the parent

Examples of when to trigger:
- "Ahmed keeps punching me at school" → physical_bullying, perpetrator=Ahmed, location=school
- "I don't want to live anymore" → self_harm, perpetrator=unknown, urgency=critical
- "This older guy online keeps asking for my photos" → grooming, location=online
- "kaydrebni kol youm f l'madrasa" → physical_bullying, perpetrator=unknown, location=school
- "بغيت نموت ما عندي ما ندير في حياتي" → self_harm, urgency=critical
- "واحد الرجل في الأنستغرام كايطلب منيا صور" → grooming, location=online, urgency=high
- "متگوليش ل ماماك، بيني و بينك" → grooming (forced secrecy), urgency=high

Be VERY careful: normal venting about a bad day is NOT a safety event. Only trigger for real danger signals.

CONTEXT:
- The child may message you after receiving an educational notification from Aegis
- They may want to talk about bullying, peer pressure, or social conflicts
- They may just want someone to listen
- They may confess about real-life situations that aren't happening on WhatsApp
- Moroccan children often mix Darija, French, and English in the same message — this is normal

Remember: Your goal is to make the child feel HEARD, not FIXED."""


class AegisChatbot:
    """Handles conversation with the child via Groq LLM."""
    
    def __init__(self):
        self.groq_api_key = os.getenv('GROQ_API_KEY', '').strip().strip('"')
        self.groq_model = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
        self.bot_instance = os.getenv('AEGIS_BOT_INSTANCE_NAME', 'aegis-bot')
        self.api_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
        self.api_key = os.getenv('EVOLUTION_API_KEY', '')
    
    def check_safety_escalation(self, text):
        """
        Static keyword fallback — checks if the message contains 
        safety-critical keywords that require immediate parent notification.
        
        Returns: (is_critical, matched_keyword) or (False, None)
        """
        text_lower = text.lower()
        for keyword in SAFETY_KEYWORDS:
            if keyword in text_lower:
                return True, keyword
        return False, None
    
    def get_conversation_history(self, child_jid, limit=10):
        """
        Fetch recent conversation history from BotConversation model.
        Returns list of {"role": "user"/"assistant", "content": "..."} dicts.
        """
        from moderation.models import BotConversation
        
        try:
            recent = BotConversation.objects.filter(
                child_jid=child_jid,
            ).order_by('-created_at')[:limit]
            
            history = []
            for msg in reversed(recent):
                history.append({
                    "role": msg.role,
                    "content": msg.content,
                })
            return history
        except Exception as e:
            logger.warning(f"[AEGIS BOT] Could not fetch history: {e}")
            return []
    
    def save_message(self, child_jid, role, content, is_safety_flagged=False, threat_intel=None):
        """Save a message to the BotConversation model."""
        from moderation.models import BotConversation
        
        try:
            BotConversation.objects.create(
                child_jid=child_jid,
                role=role,
                content=content,
                is_safety_flagged=is_safety_flagged,
                threat_intel=threat_intel,
            )
        except Exception as e:
            logger.error(f"[AEGIS BOT] Failed to save conversation message: {e}")
    
    def parse_threat_intel(self, response_text):
        """
        Parse the [THREAT_INTEL: {...}] tag from the LLM response.
        
        Returns:
            tuple: (clean_text, threat_intel_dict_or_None)
            - clean_text: response with the tag stripped out
            - threat_intel_dict: parsed JSON dict, or None if no tag found
        """
        # Match [THREAT_INTEL: {...}] — the JSON may span multiple lines
        pattern = r'\[THREAT_INTEL:\s*(\{[^}]+\})\s*\]'
        match = re.search(pattern, response_text, re.DOTALL)
        
        if not match:
            return response_text, None
        
        # Strip the tag from visible response
        clean_text = response_text[:match.start()] + response_text[match.end():]
        clean_text = clean_text.strip()
        
        # Parse the JSON
        try:
            threat_intel = json.loads(match.group(1))
            # Validate required fields
            required_fields = ['threat_type', 'perpetrator', 'location', 'urgency', 'summary']
            for field in required_fields:
                if field not in threat_intel:
                    threat_intel[field] = 'unknown'
            
            logger.info(f"[AEGIS BOT] 🚨 Threat intel extracted: {threat_intel}")
            return clean_text, threat_intel
        except json.JSONDecodeError as e:
            logger.error(f"[AEGIS BOT] Failed to parse threat intel JSON: {e}")
            # Still strip the malformed tag from the response
            return clean_text, {"threat_type": "unknown", "perpetrator": "unknown",
                               "location": "unknown", "urgency": "high",
                               "summary": "LLM detected danger but JSON parsing failed"}
    
    def generate_response(self, child_jid, message_text):
        """
        Generate an empathetic response using Groq LLM.
        
        Args:
            child_jid: The child's WhatsApp JID
            message_text: The child's message text
            
        Returns:
            str: The bot's response text (may contain [THREAT_INTEL] and
                 [SAFETY_ESCALATE] tags — caller must parse and strip them)
        """
        if not self.groq_api_key:
            logger.error("[AEGIS BOT] GROQ_API_KEY not configured!")
            return "Hey! I'm having a technical issue right now. Try again in a bit? 🛠️"
        
        # Build conversation context
        history = self.get_conversation_history(child_jid)
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        
        # Add conversation history
        messages.extend(history)
        
        # Add current message
        messages.append({"role": "user", "content": message_text})
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.groq_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 300,  # Slightly more to accommodate threat intel tag
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"].strip()
                logger.info(f"[AEGIS BOT] Generated response for {child_jid}: {content[:80]}...")
                return content
            else:
                logger.error(f"[AEGIS BOT] Groq API error: {response.status_code} - {response.text[:200]}")
                return "I'm having trouble thinking right now 😅 Can you try again?"
        except requests.exceptions.Timeout:
            return "Sorry, I'm a bit slow right now. Give me a moment and try again! ⏳"
        except Exception as e:
            logger.error(f"[AEGIS BOT] Error generating response: {e}")
            return "Oops, something went wrong on my end. Try again? 🤖"
    
    def send_reply(self, child_jid, text):
        """Send a reply from the bot instance back to the child."""
        from moderation.evolution_api import send_aegis_presence, send_text_message
        
        # Simulate typing
        send_aegis_presence(self.bot_instance, child_jid, "composing", 1500)
        
        try:
            result = send_text_message(self.bot_instance, child_jid, text)
            if result:
                logger.info(f"[AEGIS BOT] Reply sent to {child_jid}")
                return True
            else:
                logger.error(f"[AEGIS BOT] Failed to send reply via Facade")
                return False
        except Exception as e:
            logger.error(f"[AEGIS BOT] Error sending reply: {e}")
            return False
    
    def notify_parent_safety(self, instance_name, child_jid, trigger_reason):
        """
        Send a basic safety alert to the parent (keyword-based fallback).
        For richer alerts with threat intel, use notify_parent_safety_detailed().
        
        Args:
            instance_name: Evolution API instance to send the alert FROM (should be bot instance)
            child_jid: The child's WhatsApp JID (used to look up parent)
        """
        from moderation.models import MonitoredChild
        from moderation.evolution_api import send_parent_alert
        
        try:
            # Look up child by their JID, not by instance name
            child = MonitoredChild.objects.filter(
                whatsapp_jid=child_jid
            ).first()
            
            if child and child.parent and child.parent.user.phone_number:
                alert_text = (
                    f"Your child mentioned something that Aegis flagged as a safety concern. "
                    f"Please check in with them calmly and without judgment."
                )
                send_parent_alert(
                    instance_name, 
                    child.parent.user.phone_number,
                    child.full_name,
                    "safety_concern",
                    alert_text
                )
                logger.info(f"[AEGIS BOT] 🚨 Safety escalation alert sent for {child_jid}")
            else:
                logger.warning(f"[AEGIS BOT] Cannot send basic alert: no child/parent found for {child_jid}")
        except Exception as e:
            logger.error(f"[AEGIS BOT] Failed to send safety alert: {e}")

    def notify_parent_safety_detailed(self, instance_name, child_jid, threat_intel):
        """
        Send a rich, actionable safety alert to the parent with extracted threat intelligence.
        
        Args:
            instance_name: Evolution API instance name (monitoring instance)
            child_jid: The child's WhatsApp JID
            threat_intel: dict with keys: threat_type, perpetrator, location, urgency, summary
        """
        from moderation.models import MonitoredChild
        
        try:
            # Look up child by their JID, not by instance name
            child = MonitoredChild.objects.filter(
                whatsapp_jid=child_jid
            ).first()
            
            if not child or not child.parent or not child.parent.user.phone_number:
                logger.warning(f"[AEGIS BOT] Cannot send detailed alert: no parent phone found")
                return
            
            # Build the rich alert message
            threat_type = threat_intel.get('threat_type', 'unknown').replace('_', ' ').title()
            perpetrator = threat_intel.get('perpetrator', 'Unknown')
            location = threat_intel.get('location', 'Unknown').title()
            urgency = threat_intel.get('urgency', 'medium').upper()
            summary = threat_intel.get('summary', 'Your child mentioned a safety concern.')
            
            # Urgency emoji mapping
            urgency_emoji = {
                'CRITICAL': '🔴',
                'HIGH': '🟠',
                'MEDIUM': '🟡',
                'LOW': '🟢',
            }
            urgency_icon = urgency_emoji.get(urgency, '🟡')
            
            alert_text = (
                f"🚨 *AEGIS SAFETY ALERT* 🚨\n\n"
                f"Your child *{child.full_name}* confided something concerning "
                f"to Aegis Assistant.\n\n"
                f"*Type:* {threat_type}\n"
                f"*Urgency:* {urgency_icon} {urgency}\n"
            )
            
            if perpetrator and perpetrator.lower() != 'unknown':
                alert_text += f"*Involved Person:* {perpetrator}\n"
            
            if location and location.lower() != 'unknown':
                alert_text += f"*Location:* {location}\n"
            
            alert_text += (
                f"\n📝 *Summary:*\n_{summary}_\n\n"
                f"💡 *Recommended Action:*\n"
            )
            
            # Action recommendations based on urgency
            if urgency == 'CRITICAL':
                alert_text += (
                    "• Check on your child IMMEDIATELY\n"
                    "• If they're in physical danger, contact authorities\n"
                    "• Stay calm — your child trusted Aegis, which means they need help"
                )
            elif urgency == 'HIGH':
                alert_text += (
                    "• Have a calm, private conversation with your child today\n"
                    "• Let them know you're there to support, not punish\n"
                    "• Consider contacting the school or relevant authorities"
                )
            else:
                alert_text += (
                    "• Find a quiet moment to check in with your child\n"
                    "• Ask open-ended questions — don't interrogate\n"
                    "• Monitor the situation over the next few days"
                )
            
            alert_text += "\n\n📊 Check your AEGIS Dashboard for full details."
            
            from moderation.evolution_api import send_text_message
            clean_number = str(child.parent.user.phone_number).replace("+", "").replace("-", "").replace(" ", "")
            
            result = send_text_message(instance_name, clean_number, alert_text)
            
            if result:
                logger.info(
                    f"[AEGIS BOT] 🚨 Detailed safety alert sent to parent "
                    f"({clean_number}) — {threat_type}, urgency={urgency}"
                )
            else:
                logger.error(f"[AEGIS BOT] Failed to send detailed alert via Facade")
                
        except Exception as e:
            logger.error(f"[AEGIS BOT] Failed to send detailed safety alert: {e}")


# Singleton instance
_chatbot_instance = None

def get_chatbot():
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = AegisChatbot()
    return _chatbot_instance
