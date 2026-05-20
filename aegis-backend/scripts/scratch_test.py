"""
═══════════════════════════════════════════════════════════════
  AEGIS Digital Twin — COMPREHENSIVE SCENARIO TEST
═══════════════════════════════════════════════════════════════

6 diverse scenarios to stress-test the Random Forest:

  A: Arthur    — GROOMER (subtle, night, stranger)
  B: Karim     — NORMAL  (high-toxicity gaming banter, old friend)
  C: Yassine   — BULLY   (escalating hostility toward one victim)
  D: SpamBot   — TROLL   (rapid-fire spam to MANY kids)
  E: BigBro    — NORMAL  (protective older sibling, sometimes harsh)
  F: SlowBurn  — GROOMER (patience predator, builds trust over days)
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'aegis-backend'))
django.setup()

from moderation.models import UserBehaviorProfile, ModerationResult
from ml_pipeline.graph import profiler_node
from django.utils import timezone
from unittest.mock import patch
import datetime


def reset_all():
    """Nuclear clean slate."""
    jids = [
        "GROOMER@test", "GAMER@test", "BULLY@test",
        "SPAMBOT@test", "BIGBRO@test", "SLOWBURN@test"
    ]
    for jid in jids:
        UserBehaviorProfile.objects.filter(user_jid=jid).delete()
        ModerationResult.objects.filter(sender_jid=jid).delete()


def msg(sender_jid, instance, text, m1, decision,
        llm_triggered=False, ml_corrected=False, is_night=False):
    """Send one simulated message through Agent 4."""
    if is_night:
        mock_time = timezone.now().replace(hour=2, minute=30)
    else:
        mock_time = timezone.now().replace(hour=14, minute=0)

    with patch('django.utils.timezone.now', return_value=mock_time):
        state = {
            "sender_jid": sender_jid,
            "instance_name": instance,
            "raw_text": text,
            "m1_score": m1,
            "decision": decision,
            "llm_triggered": llm_triggered,
            "ml_corrected": ml_corrected,
        }
        ModerationResult.objects.create(
            instance_name=instance,
            sender_jid=sender_jid,
            raw_text=text,
            normalized_text=text.lower(),
            toxicity_score=m1,
            final_score=m1,
            decision=decision,
            created_at=mock_time
        )
        return profiler_node(state)


def backdate_first_seen(jid, days_ago):
    """Make a sender appear as a known contact from X days ago."""
    p = UserBehaviorProfile.objects.get(user_jid=jid)
    p.first_seen_at = timezone.now() - datetime.timedelta(days=days_ago)
    p.save()


def print_header(emoji, label, name, expected):
    print(f"\n\n{'─' * 62}")
    print(f"  {emoji} {label}: '{name}' — Expected: {expected}")
    print(f"{'─' * 62}")


def print_summary():
    print(f"\n\n{'█' * 62}")
    print(f"  📋 FINAL DIGITAL TWIN SCOREBOARD")
    print(f"{'█' * 62}")
    
    tests = [
        ("GROOMER@test",  "Arthur (Groomer)",    "CRITICAL"),
        ("GAMER@test",    "Karim (Gamer)",       "LOW"),
        ("BULLY@test",    "Yassine (Bully)",     "HIGH"),
        ("SPAMBOT@test",  "SpamBot (Troll)",     "MEDIUM"),
        ("BIGBRO@test",   "BigBro (Sibling)",    "LOW"),
        ("SLOWBURN@test", "SlowBurn (Groomer2)", "CRITICAL"),
    ]
    
    correct = 0
    total = len(tests)
    
    for jid, label, expected in tests:
        try:
            p = UserBehaviorProfile.objects.get(user_jid=jid)
            status = "✅" if p.risk_level == expected else "❌"
            if p.risk_level == expected:
                correct += 1
            days = (timezone.now() - p.first_seen_at).days if p.first_seen_at else 0
            
            print(f"\n  ── {label} ──")
            print(f"     {status} Risk Level:    {p.risk_level} (expected: {expected}) — score: {p.risk_score:.3f}")
            print(f"        Messages:      {p.total_messages_sent}")
            print(f"        Blocked:       {p.total_blocked_messages_sent} ({p.block_ratio:.0%})")
            print(f"        Avg Toxicity:  {p.average_toxicity_score:.3f}")
            print(f"        Night Ratio:   {p.night_activity_ratio:.2f}")
            print(f"        Targets:       {p.unique_targets_count}")
            print(f"        Corrections:   {p.correction_rate:.2f}")
            print(f"        Days Known:    {days}")
        except UserBehaviorProfile.DoesNotExist:
            print(f"\n  ── {label} ── NOT FOUND")
    
    print(f"\n  {'═' * 58}")
    print(f"  📊 ACCURACY: {correct}/{total} ({correct/total*100:.0f}%)")
    print(f"  {'═' * 58}")
    print(f"{'█' * 62}\n")


def main():
    reset_all()
    
    print(f"\n{'█' * 62}")
    print(f"  🧪 AEGIS DIGITAL TWIN — COMPREHENSIVE STRESS TEST")
    print(f"  📅 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'█' * 62}")

    # ═══════════════════════════════════════════════════════════
    #  A: ARTHUR — Classic Groomer
    #  Night messages, stranger, low toxicity, long messages,
    #  Agent 3 catches manipulation M1 misses.
    # ═══════════════════════════════════════════════════════════
    print_header("🔴", "SENDER A", "Arthur", "CRITICAL (Groomer)")
    
    msg("GROOMER@test", "child_A", 
        "Hey, is this Sarah? I got your number from Instagram",
        m1=0.03, decision="ALLOW", is_night=True)
    
    msg("GROOMER@test", "child_A",
        "How old are you? I'm a photographer, I think you'd be great for a shoot",
        m1=0.05, decision="ALLOW",
        llm_triggered=True, ml_corrected=True, is_night=True)
    
    msg("GROOMER@test", "child_A",
        "You're so pretty for your age, do you have Snapchat so we can talk privately?",
        m1=0.08, decision="WARN",
        llm_triggered=True, ml_corrected=True, is_night=True)
    
    msg("GROOMER@test", "child_A",
        "Don't tell your parents about us okay? It's our little secret, they wouldn't understand",
        m1=0.12, decision="BLOCK",
        llm_triggered=True, ml_corrected=True, is_night=True)

    # ═══════════════════════════════════════════════════════════
    #  B: KARIM — Normal Gamer
    #  High-toxicity words, but: known friend (120 days), daytime,
    #  zero blocks, Agent 3 always overrides to ALLOW.
    # ═══════════════════════════════════════════════════════════
    print_header("🟢", "SENDER B", "Karim", "LOW (Normal)")
    
    msg("GAMER@test", "child_A",
        "Yo bro wanna play tonight?",
        m1=0.02, decision="ALLOW")
    backdate_first_seen("GAMER@test", 120)
    
    msg("GAMER@test", "child_A",
        "I'm gonna DESTROY you bro you're absolutely DEAD",
        m1=0.82, decision="ALLOW",
        llm_triggered=True, ml_corrected=True)
    
    msg("GAMER@test", "child_A",
        "GET REKT NOOB hahaha your aim is TRASH",
        m1=0.78, decision="ALLOW",
        llm_triggered=True, ml_corrected=True)
    
    msg("GAMER@test", "child_A",
        "lol gg bro that was insane, same time tomorrow?",
        m1=0.02, decision="ALLOW")
    
    msg("GAMER@test", "child_A",
        "bro you awake? I just got a new skin let's gooo",
        m1=0.01, decision="ALLOW")
    
    msg("GAMER@test", "child_A",
        "I'll MURDER you in Warzone tonight haha",
        m1=0.88, decision="ALLOW",
        llm_triggered=True, ml_corrected=True)

    # ═══════════════════════════════════════════════════════════
    #  C: YASSINE — Bully
    #  Targets ONE specific kid, escalating aggression,
    #  short aggressive messages, daytime.
    # ═══════════════════════════════════════════════════════════
    print_header("🟡", "SENDER C", "Yassine", "HIGH (Bully)")
    
    msg("BULLY@test", "child_B",
        "you're weird",
        m1=0.25, decision="WARN")
    
    msg("BULLY@test", "child_B",
        "nobody likes you, everyone thinks you're a loser",
        m1=0.55, decision="BLOCK")
    
    msg("BULLY@test", "child_B",
        "I'll beat you up after school if you tell anyone",
        m1=0.92, decision="ESCALATE", llm_triggered=True)
    
    msg("BULLY@test", "child_B",
        "you're dead meat tomorrow, watch your back",
        m1=0.95, decision="ESCALATE", llm_triggered=True)
    
    msg("BULLY@test", "child_B",
        "ugly freak nobody would miss you",
        m1=0.70, decision="BLOCK")

    # ═══════════════════════════════════════════════════════════
    #  D: SPAMBOT — Troll/Spammer
    #  Hits MANY different kids, short spammy messages,
    #  rapid-fire burst, new account, moderate toxicity.
    # ═══════════════════════════════════════════════════════════
    print_header("🟠", "SENDER D", "SpamBot", "MEDIUM (Troll)")
    
    msg("SPAMBOT@test", "child_A",
        "check out this link bro free vbucks",
        m1=0.15, decision="WARN")
    
    msg("SPAMBOT@test", "child_B",
        "yo click this link you won a giveaway",
        m1=0.18, decision="WARN")
    
    msg("SPAMBOT@test", "child_C",
        "free robux no scam I swear click here",
        m1=0.20, decision="BLOCK")
    
    msg("SPAMBOT@test", "child_D",
        "you stupid if you don't click this link lol",
        m1=0.35, decision="BLOCK")
    
    msg("SPAMBOT@test", "child_E",
        "hey add me on snap I got free stuff for you",
        m1=0.12, decision="WARN")
    
    msg("SPAMBOT@test", "child_F",
        "click this or ur gay lmaooo",
        m1=0.40, decision="BLOCK")

    # ═══════════════════════════════════════════════════════════
    #  E: BIGBRO — Protective Older Sibling
    #  Known contact (365 days), sometimes uses harsh language 
    #  in a caring way, Agent 3 always clears him.
    # ═══════════════════════════════════════════════════════════
    print_header("🟢", "SENDER E", "BigBro", "LOW (Normal)")
    
    msg("BIGBRO@test", "child_A",
        "Hey did you finish your homework?",
        m1=0.01, decision="ALLOW")
    backdate_first_seen("BIGBRO@test", 365)
    
    msg("BIGBRO@test", "child_A",
        "If that kid is bothering you at school tell me, I'll handle it",
        m1=0.35, decision="ALLOW",
        llm_triggered=True, ml_corrected=True)
    
    msg("BIGBRO@test", "child_A",
        "I swear if someone touches you I'll kill them",
        m1=0.92, decision="ALLOW",
        llm_triggered=True, ml_corrected=True)
    
    msg("BIGBRO@test", "child_A",
        "Mom said come home for dinner",
        m1=0.01, decision="ALLOW")
    
    msg("BIGBRO@test", "child_A",
        "Stop being dumb and listen to your teacher bro",
        m1=0.30, decision="ALLOW",
        llm_triggered=True, ml_corrected=True)

    # ═══════════════════════════════════════════════════════════
    #  F: SLOWBURN — Patient Groomer (different pattern)
    #  Normal-looking at first, then slowly escalates at night,
    #  targets 2 kids on different instances.
    # ═══════════════════════════════════════════════════════════
    print_header("🔴", "SENDER F", "SlowBurn", "CRITICAL (Groomer)")
    
    # Starts normal during the day
    msg("SLOWBURN@test", "child_A",
        "Hi! I'm your new tutor, your parents told me to message you",
        m1=0.02, decision="ALLOW")
    
    msg("SLOWBURN@test", "child_A",
        "How was school today? Tell me everything",
        m1=0.03, decision="ALLOW", is_night=True)
    
    # Moves to second child
    msg("SLOWBURN@test", "child_B",
        "Hey I'm tutoring your friend Sarah too, she told me about you",
        m1=0.02, decision="ALLOW", is_night=True)
    
    # Gets bolder at night
    msg("SLOWBURN@test", "child_A",
        "You can tell me anything, I'm not like your parents, I actually understand you",
        m1=0.06, decision="ALLOW",
        llm_triggered=True, ml_corrected=True, is_night=True)
    
    msg("SLOWBURN@test", "child_B",
        "Do you have a boyfriend? You're very mature for your age",
        m1=0.10, decision="WARN",
        llm_triggered=True, ml_corrected=True, is_night=True)
    
    msg("SLOWBURN@test", "child_A",
        "Let's keep our conversations between us, no need to tell anyone",
        m1=0.08, decision="BLOCK",
        llm_triggered=True, ml_corrected=True, is_night=True)

    # ═══════════════════════════════════════════════════════════
    print_summary()


if __name__ == "__main__":
    main()
