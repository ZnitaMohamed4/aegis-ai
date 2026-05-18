"""
AGENT 4: The Profiler — Digital Twin behavioral risk assessment.

Calculates behavioral risk score using a Random Forest model (with graceful
fallback to a formula) and updates the sender's Digital Twin profile.

Extracted from graph.py during Phase 2 audit refactoring (2026-04-21).
"""
import os
import logging
import datetime

from django.utils import timezone

from .state import ModerationState

logger = logging.getLogger(__name__)

# ── ANSI colors for Agent 4 logging ──────────────────────────
C4_BLUE   = "\033[94m"
C4_GREEN  = "\033[92m"
C4_YELLOW = "\033[93m"
C4_RED    = "\033[91m"
C4_MAGENTA= "\033[95m"
C4_CYAN   = "\033[96m"
C4_RESET  = "\033[0m"
C4_DIVIDER = "═" * 62


def profiler_node(state: ModerationState) -> dict:
    """
    AGENT 4: Profiler 
    Calculates behavioral risk score and updates the Digital Twin profile.
    """
    from moderation.models import UserBehaviorProfile, ModerationResult

    sender_jid = state["sender_jid"]
    m1_score = state.get("m1_score", 0.0)
    decision = state.get("decision", "ALLOW")
    instance_name = state.get("instance_name", "")
    upward_corrected = state.get("upward_corrected", False)
    downward_corrected = state.get("downward_corrected", False)
    
    # ── Agent 3 Correction: Trust the Auditor, not raw ML ────
    # If Agent 3 overrode the ML decision, M1 was WRONG.
    # The raw M1 score stays in ModerationResult (for retraining),
    # but the Digital Twin's behavioral memory uses the CORRECTED
    # reality — what Agent 3 actually decided.
    #
    # TRUTH TABLE:
    #   M1=HIGH + Agent3→ALLOW   = M1 overreacted     → 0.05 (safe)
    #   M1=HIGH + Agent3→WARN    = Agent3 downgraded  → 0.40 (mild)
    #   M1=LOW  + Agent3→BLOCK   = M1 MISSED a threat → 0.85 (dangerous)
    #   M1=LOW  + Agent3→ESCALATE= M1 SEVERELY missed → 0.95 (critical)
    #   No correction            = M1 was right       → m1_score (as-is)
    
    if state.get("llm_triggered"):
        CORRECTED_SCORES = {
            "ALLOW":    0.05,   # Agent 3 says safe → clean signal
            "WARN":     0.40,   # Agent 3 says mild concern
            "HUMAN_REVIEW": 0.50, # Agent 3 says borderline
            "BLOCK":    0.85,   # Agent 3 caught a threat
            "ESCALATE": 0.95,   # Agent 3 caught a SEVERE threat
        }
        effective_toxicity = CORRECTED_SCORES.get(decision, m1_score)
    else:
        effective_toxicity = m1_score
    
    # Fetch the exact user from DB
    profile, created = UserBehaviorProfile.objects.get_or_create(user_jid=sender_jid)
    
    if created and instance_name:
        from moderation.evolution_api import fetch_relationship_start, fetch_shared_groups
        # If this is the very first time AEGIS sees this sender, we query WhatsApp history
        # to find out how long they've ACTUALLY known the child, overriding the default "now".
        try:
            true_start_date, child_initiated = fetch_relationship_start(instance_name, sender_jid)
            if true_start_date:
                profile.first_seen_at = true_start_date
                
            profile.child_initiated = child_initiated
                
            # We save here so the subsequent logic uses the correct date and initiator status
            profile.save(update_fields=['first_seen_at', 'child_initiated'])
        except Exception as e:
            logger.error(f"[AGENT 4] Failed to backdate profile via WhatsApp history: {e}")

        # Fetch shared groups on first creation
        try:
            shared_groups = fetch_shared_groups(instance_name, sender_jid)
            profile.shared_groups_count = len(shared_groups)
            profile.shared_groups_metadata = shared_groups
            profile.save(update_fields=['shared_groups_count', 'shared_groups_metadata'])
            if shared_groups:
                group_names = [g.get('group_name', '?') for g in shared_groups]
                logger.info(f"[AGENT 4] 👥 {sender_jid} shares {len(shared_groups)} groups: {group_names}")
        except Exception as e:
            logger.error(f"[AGENT 4] Failed to fetch shared groups: {e}")

    elif instance_name:
        # Refresh shared groups for EXISTING profiles when:
        #   (a) Count is 0 — clearly stale, do FOREGROUND (blocking) refresh
        #       because the first message's risk score depends critically on this
        #   (b) Every 50 messages — periodic background refresh
        if profile.shared_groups_count == 0:
            # FOREGROUND refresh — blocks pipeline but ensures correct scoring
            try:
                from moderation.evolution_api import fetch_shared_groups as _fetch_groups
                groups = _fetch_groups(instance_name, sender_jid)
                profile.shared_groups_count = len(groups)
                profile.shared_groups_metadata = groups
                profile.save(update_fields=['shared_groups_count', 'shared_groups_metadata'])
                if groups:
                    names = [g.get('group_name', '?') for g in groups]
                    logger.info(f"[AGENT 4] 👥 Foreground shared groups refresh for {sender_jid}: {len(groups)} groups {names}")
            except Exception as e:
                logger.error(f"[AGENT 4] Foreground group refresh failed for {sender_jid}: {e}")
        elif profile.total_messages_sent > 0 and profile.total_messages_sent % 50 == 0:
            # BACKGROUND refresh — periodic, doesn't block the pipeline
            import threading
            from moderation.evolution_api import fetch_shared_groups as _fetch_groups
            
            def _refresh_groups(jid, inst, prof_id):
                """Background refresh — doesn't block the pipeline."""
                try:
                    from moderation.models import UserBehaviorProfile as UBP
                    groups = _fetch_groups(inst, jid)
                    UBP.objects.filter(id=prof_id).update(
                        shared_groups_count=len(groups),
                        shared_groups_metadata=groups,
                    )
                    if groups:
                        names = [g.get('group_name', '?') for g in groups]
                        logger.info(f"[AGENT 4] 🔄 Refreshed shared groups for {jid}: {len(groups)} groups {names}")
                    else:
                        logger.debug(f"[AGENT 4] 🔄 Shared groups refresh for {jid}: 0 groups found")
                except Exception as exc:
                    logger.error(f"[AGENT 4] Background group refresh failed for {jid}: {exc}")
            
            threading.Thread(
                target=_refresh_groups,
                args=(sender_jid, instance_name, profile.id),
                daemon=True
            ).start()


    # --- 1. Update Digital Twin Base Stats ---
    # Total messages
    prev_total = profile.total_messages_sent
    profile.total_messages_sent += 1
    
    # Toxicity (EMA) — uses CORRECTED score, not raw M1
    alpha = 0.3 
    profile.average_toxicity_score = (profile.average_toxicity_score * (1 - alpha)) + (effective_toxicity * alpha)
    
    # Block & Escalation counters
    if decision != "ALLOW":
        profile.total_blocked_messages_sent += 1
    if decision == "ESCALATE":
        profile.escalation_count += 1
        
    # Block ratio
    profile.block_ratio = profile.total_blocked_messages_sent / max(1, profile.total_messages_sent)
    
    # Night activity ratio (22h to 06h) — Use local time for Morocco
    current_hour = timezone.localtime(timezone.now()).hour
    is_night = 1.0 if (current_hour >= 22 or current_hour <= 6) else 0.0
    prev_night_msgs = profile.night_activity_ratio * prev_total
    profile.night_activity_ratio = (prev_night_msgs + is_night) / profile.total_messages_sent
    
    # Unique targets count — count REAL monitored children, not raw instance strings
    # The old code counted distinct instance_name values which inflated numbers.
    from moderation.models import MonitoredChild
    sender_instances = set(
        ModerationResult.objects.filter(sender_jid=sender_jid)
        .values_list('instance_name', flat=True).distinct()
    )
    if instance_name:
        sender_instances.add(instance_name)
    
    # Map instance_names → actual registered MonitoredChild records
    real_children_count = MonitoredChild.objects.filter(
        parent__evolution_instance_name__in=sender_instances
    ).count()
    
    # Use real count; fallback to distinct instances capped at 5 if no children registered
    profile.unique_targets_count = real_children_count if real_children_count > 0 else min(len(sender_instances), 5)
    
    # --- Tier 2 Features ---
    # Agent 3 overrides
    if state.get("llm_triggered"):
        profile.llm_triggers_total += 1
    if upward_corrected:
        profile.upward_corrections_total += 1
    if downward_corrected:
        profile.downward_corrections_total += 1
    
    # Message length EMA
    raw_text = state.get("raw_text", "")
    msg_len = len(raw_text)
    profile.avg_message_length = (profile.avg_message_length * 0.9) + (msg_len * 0.1)
    
    # Time-based metrics (1h, 24h windows)
    now = timezone.now()
    window_24h = now - datetime.timedelta(hours=24)
    recent_24h = ModerationResult.objects.filter(sender_jid=sender_jid, created_at__gte=window_24h).values_list('toxicity_score', 'created_at')
    
    past_max_tox = max([tox for tox, dt in recent_24h], default=0.0)
    profile.max_toxicity_24h = max(past_max_tox, effective_toxicity)
    
    window_1h = now - datetime.timedelta(hours=1)
    profile.message_frequency_1h = sum(1 for tox, dt in recent_24h if dt >= window_1h) + 1
    
    window_10m = now - datetime.timedelta(minutes=10)
    msgs_10m = sum(1 for tox, dt in recent_24h if dt >= window_10m) + 1
    if msgs_10m == 5:  # Trigger exactly once per burst episode
        profile.burst_count_24h += 1
    
    # --- 2. Risk Score: Bayesian Network Inference ---
    from ml_pipeline.bn_evidence import collect_evidence
    from ml_pipeline.bn_engine import get_bn_profiler
    
    prediction_method = "bayesian_network"
    rf_probas = {}
    explanation = {}
    
    try:
        # Collect evidence from profile
        category = state.get("primary_class", "safe")  # From Agent 2
        evidence = collect_evidence(profile, threat_category=category)
        
        # Run Bayesian Network Inference
        bn = get_bn_profiler()
        result = bn.infer(evidence)
        
        profile.risk_score = result["risk_score"]
        profile.risk_level = result["risk_level"]
        archetype = result["archetype"]
        rf_probas = result["probas"]
        explanation = result["explanation"]
        
    except Exception as e:
        logger.error(f"[AGENT 4] BN prediction failed: {e}. Using fallback.")
        prediction_method = "fallback"
        # Old hardcoded formula (graceful degradation)
        volume_penalty = profile.total_blocked_messages_sent * 0.08
        ratio_penalty = profile.block_ratio * 0.20
        toxicity_penalty = profile.average_toxicity_score * 0.30
        raw_risk = volume_penalty + ratio_penalty + toxicity_penalty
        profile.risk_score = min(1.0, max(0.0, raw_risk))
        
        if profile.risk_score >= 0.8:
            profile.risk_level = 'CRITICAL'
        elif profile.risk_score >= 0.5:
            profile.risk_level = 'HIGH'
        elif profile.risk_score >= 0.25:
            profile.risk_level = 'MEDIUM'
        else:
            profile.risk_level = 'LOW'
        
        archetype = {"LOW": "Normal User", "MEDIUM": "Troll Pattern", "HIGH": "Bully Pattern", "CRITICAL": "Groomer Pattern"}.get(profile.risk_level, "Unknown")
        
    profile.save()
    
    # --- 2b. Upsert Daily Behavioral Snapshot ---
    # Creates a time-series record for the frontend risk trajectory charts.
    from moderation.models import BehavioralSnapshot
    today = timezone.now().date()
    
    # Extract per-pathway HIGH probabilities for the snapshot
    grooming_high = explanation.get("GroomingRisk", {}).get("HIGH", 0.0) if explanation else 0.0
    bully_high = explanation.get("BullyRisk", {}).get("HIGH", 0.0) if explanation else 0.0
    troll_high = explanation.get("TrollRisk", {}).get("HIGH", 0.0) if explanation else 0.0
    
    # Get alert_id if this message triggered an alert
    alert_id = state.get("alert_id", None)
    
    try:
            # Instead of just update_or_create, we need to fetch the existing one first
            # to ensure we don't overwrite the peak if it was higher earlier today.
            snapshot, created = BehavioralSnapshot.objects.get_or_create(
                profile=profile,
                date_snapshot=today,
                defaults={
                    'risk_score_snapshot': profile.risk_score,
                    'peak_risk_score': profile.risk_score,
                    'peak_risk_time': timezone.now(),
                    'snapshot_count': 1,
                    'risk_level': profile.risk_level,
                    'archetype': archetype,
                    'grooming_prob': grooming_high,
                    'bully_prob': bully_high,
                    'troll_prob': troll_high,
                    'message_count': profile.total_messages_sent,
                    'blocked_count': profile.total_blocked_messages_sent,
                    'alert_id': str(alert_id) if alert_id else None,
                }
            )
            if not created:
                # Update existing snapshot for today
                snapshot.risk_score_snapshot = profile.risk_score
                snapshot.risk_level = profile.risk_level
                snapshot.archetype = archetype
                snapshot.grooming_prob = grooming_high
                snapshot.bully_prob = bully_high
                snapshot.troll_prob = troll_high
                snapshot.message_count = profile.total_messages_sent
                snapshot.blocked_count = profile.total_blocked_messages_sent
                snapshot.snapshot_count += 1
                
                # THE CRITICAL FIX: Only update the peak if the new score is higher
                if profile.risk_score > snapshot.peak_risk_score:
                    snapshot.peak_risk_score = profile.risk_score
                    snapshot.peak_risk_time = timezone.now()
                    
                if alert_id:
                    snapshot.alert_id = str(alert_id)
                    
                snapshot.save()
    except Exception as e:
        logger.error(f"[AGENT 4] Failed to upsert BehavioralSnapshot: {e}")
    
    # --- 3. Terminal Logging ---
    risk_color = C4_RED if profile.risk_level in ('CRITICAL','HIGH') else C4_YELLOW if profile.risk_level == 'MEDIUM' else C4_GREEN
    
    print(f"\n{C4_DIVIDER}")
    print(f"  📊 {C4_BLUE}[AGENT 4: PROFILER]{C4_RESET} Digital Twin Update")
    print(C4_DIVIDER)
    print(f"  👤 Sender:     {sender_jid}")
    print(f"  📈 Method:     {C4_CYAN}{prediction_method.upper()}{C4_RESET}")
    print(f"  🧠 Prediction: {risk_color}{profile.risk_level}{C4_RESET} ({archetype}) — score {profile.risk_score:.3f}")
    if rf_probas:
        proba_str = " | ".join(f"{k}={v:.2f}" for k, v in sorted(rf_probas.items()))
        print(f"  🎲 Probas:     {proba_str}")
    
    # Calculate rates for logging
    total_msgs = max(1, profile.total_messages_sent)
    up_rate = profile.upward_corrections_total / total_msgs
    down_rate = profile.downward_corrections_total / total_msgs
    days_known = int((timezone.now() - profile.first_seen_at).days) if profile.first_seen_at else 0
    
    # BN Observables for logging
    stranger_val = "YES" if days_known < 14 else "NO"
    block_ratio = profile.total_blocked_messages_sent / total_msgs
    escalation_rate = profile.escalation_count / max(1, days_known)
    child_init_val = "YES" if profile.child_initiated else "NO"
    
    print(f"  📉 Features:   Stranger={stranger_val} | Night={profile.night_activity_ratio:.2f} | Targets={profile.unique_targets_count} | SharedGroups={profile.shared_groups_count}")
    print(f"                 ChildInit={child_init_val} | MsgLen={profile.avg_message_length:.0f} | BlockRatio={block_ratio:.2f} | EscRate={escalation_rate:.2f} | ToxEMA={profile.average_toxicity_score:.2f}")
    print(C4_DIVIDER + "\n")
    
    logger.info(
        f"[AGENT 4: PROFILER] method={prediction_method} | "
        f"risk={profile.risk_level} ({profile.risk_score:.3f}) | "
        f"archetype={archetype}"
    )
    
    # Update the LangGraph state
    return {
        "risk_score": profile.risk_score,
        "risk_level": profile.risk_level
    }
