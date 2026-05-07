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

@tool
def fetch_risk_profile(sender_jid: str) -> str:
    """
    Fetches the sender's behavioral risk profile (Digital Twin) built by Agent 4.
    Returns their risk level, Bayesian archetype, and key behavioral evidence.
    Use this when the message is ambiguous, from an unknown contact, or when
    grooming signals are suspected. ALWAYS pass the exact sender_jid from the prompt.
    """
    from moderation.models import UserBehaviorProfile, BehavioralSnapshot
    from django.utils import timezone
    
    try:
        profile = UserBehaviorProfile.objects.get(user_jid=sender_jid)
    except UserBehaviorProfile.DoesNotExist:
        return (
            "NO PROFILE FOUND: This is a first-time sender with zero behavioral history. "
            "Treat as UNKNOWN contact — apply maximum caution for any suspicious content."
        )
    
    days_known = (timezone.now() - profile.first_seen_at).days if profile.first_seen_at else 0
    is_stranger = days_known < 14
    total = max(1, profile.total_messages_sent)
    
    # Get latest Bayesian snapshot
    snapshot = BehavioralSnapshot.objects.filter(profile=profile).order_by('-date_snapshot').first()
    
    lines = [
        "[AEGIS SENDER RISK PROFILE]",
        f"Overall Risk: {profile.risk_level} (Score: {profile.risk_score:.2f})",
    ]
    
    if snapshot:
        lines.append(f"Archetype: {snapshot.archetype}")
        lines.append("")
        lines.append("RISK PATHWAYS:")
        lines.append(f"  - Grooming Probability: {snapshot.grooming_prob*100:.0f}%")
        lines.append(f"  - Bully Probability: {snapshot.bully_prob*100:.0f}%")
        lines.append(f"  - Troll Probability: {snapshot.troll_prob*100:.0f}%")
    
    night_label = "HIGH" if profile.night_activity_ratio > 0.5 else "MODERATE" if profile.night_activity_ratio > 0.2 else "LOW"
    
    lines.append("")
    lines.append("BEHAVIORAL EVIDENCE:")
    lines.append(f"  1. Stranger: {'YES' if is_stranger else 'NO'} (Known for {days_known} days)")
    lines.append(f"  2. Night Activity: {night_label} ({profile.night_activity_ratio:.0%} of messages)")
    lines.append(f"  3. Target Breadth: {profile.unique_targets_count} children contacted")
    lines.append(f"  4. Message Style: avg {profile.avg_message_length:.0f} chars/msg")
    lines.append(f"  5. Child Initiated: {'YES' if profile.child_initiated else 'NO'}")
    lines.append(f"  6. Block Ratio: {profile.block_ratio:.0%} ({profile.total_blocked_messages_sent}/{total} blocked)")
    lines.append(f"  7. Escalation Count: {profile.escalation_count}")
    lines.append(f"  8. Toxicity (EMA): {profile.average_toxicity_score:.2f}")
    
    return "\n".join(lines)
