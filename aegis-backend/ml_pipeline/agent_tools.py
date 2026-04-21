import os
import django
from langchain.tools import tool

@tool
def fetch_recent_history(sender_jid: str, instance_name: str) -> str:
    """
    Fetches the last 5 messages sent by a specific user (sender_jid) on a specific instance (instance_name).
    ALWAYS pass the exact sender_jid and instance_name provided in the prompt.
    Use this history to understand the context of the conversation before classifying the message.
    """
    from moderation.models import ModerationResult
    
    try:
        results = ModerationResult.objects.filter(
            instance_name=instance_name, 
            sender_jid=sender_jid
        ).order_by('-created_at')[:5]
        
        if not results:
            return "No previous chat history found between this contact and the child."
            
        history = []
        # Reverse to get chronological order (oldest to newest among the last 5)
        for r in reversed(results):
            history.append(f"[{r.created_at.strftime('%H:%M:%S')}] Text: '{r.raw_text}' | AI_Decision: {r.decision}")
            
        return "\n".join(history)
    except Exception as e:
        return f"Error fetching history: {e}"

@tool
def search_similar_cases(text: str) -> str:
    """
    Searches the AEGIS vector database for similar past messages to see how they were classified.
    ALWAYS pass the raw_text of the message.
    Use this when you are unsure if a phrase is harmful or to see past precedence.
    """
    from moderation.semantic_cache import search_semantic_cache
    
    try:
        match = search_semantic_cache(text)
        if match:
            return (
                f"Found a similar past case:\n"
                f"Is Harmful: {match.get('is_harmful')}\n"
                f"Category: {match.get('category')}\n"
                f"Decision: {match.get('decision')}\n"
                f"Explanation: {match.get('explanation')}"
            )
        return "No strictly similar past cases found in the database. Use your best judgment."
    except Exception as e:
        return f"Error searching cache: {e}"
