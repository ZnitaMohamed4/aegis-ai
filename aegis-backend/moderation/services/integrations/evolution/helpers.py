import logging
from .client import get_evolution_client


import requests

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# BACKWARD-COMPATIBLE MODULE-LEVEL FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════
# These thin wrappers keep all existing call sites working without changes.

def delete_message_from_whatsapp(instance_name, message_key_id, remote_jid,
                                 is_from_me):
    """Backward-compatible wrapper — see ``EvolutionAPIClient.delete_message_for_everyone``."""
    return get_evolution_client().delete_message_for_everyone(
        instance_name, message_key_id, remote_jid, is_from_me,
    )


def send_aegis_warning(instance_name, remote_jid, category, is_from_me,
                       decision, message_key_id=None, image_flags=None):
    """Backward-compatible wrapper.

    Builds the warning text via ``message_templates`` then delegates to the client.
    """
    from moderation.services.message_templates import get_warning_text
    warning_text = get_warning_text(category, decision, is_from_me,
                                    image_flags=image_flags)
    return get_evolution_client().send_warning(
        instance_name, remote_jid, warning_text,
        message_key_id=message_key_id, is_from_me=is_from_me,
    )


def send_aegis_reaction(instance_name, remote_jid, message_key_id,
                        is_from_me, reaction="🚨"):
    """Backward-compatible wrapper — see ``EvolutionAPIClient.send_reaction``."""
    return get_evolution_client().send_reaction(
        instance_name, remote_jid, message_key_id, is_from_me, reaction,
    )


def send_aegis_presence(instance_name, remote_jid, presence="composing",
                        delay=1500):
    """Backward-compatible wrapper — see ``EvolutionAPIClient.send_presence``."""
    return get_evolution_client().send_presence(
        instance_name, remote_jid, presence, delay,
    )


def block_contact(instance_name, remote_jid):
    """Backward-compatible wrapper — see ``EvolutionAPIClient.block_contact``."""
    return get_evolution_client().block_contact(instance_name, remote_jid)


def archive_chat(instance_name, remote_jid, warning_msg_key_id=None,
                 warning_timestamp=None, full_last_message=None,
                 lid_jid=None):
    """Backward-compatible wrapper — see ``EvolutionAPIClient.archive_chat``."""
    return get_evolution_client().archive_chat(
        instance_name, remote_jid,
        warning_msg_key_id=warning_msg_key_id,
        warning_timestamp=warning_timestamp,
        full_last_message=full_last_message,
        lid_jid=lid_jid,
    )


def send_parent_alert(instance_name, parent_phone_number, child_name,
                      category, text):
    """Backward-compatible wrapper — builds alert text then sends."""
    from moderation.services.message_templates import get_parent_alert_text
    alert_text = get_parent_alert_text(child_name, category, text)
    return get_evolution_client().send_parent_alert(
        instance_name, parent_phone_number, alert_text,
    )


def send_text_message(instance_name, remote_jid, text):
    """Backward-compatible wrapper — see ``EvolutionAPIClient.send_text``."""
    result = get_evolution_client().send_text(instance_name, remote_jid, text)
    return result is not None


def send_educational_dm(bot_instance_name, child_jid, category,
                        original_text=None):
    """Backward-compatible wrapper — builds DM text then sends.

    Returns ``(message_key_id, dm_text)`` or ``(None, dm_text)`` on failure.
    """
    from moderation.services.message_templates import get_educational_dm_text
    dm_text = get_educational_dm_text(category)
    return get_evolution_client().send_educational_dm(
        bot_instance_name, child_jid, dm_text,
    )


def send_constructive_parent_alert(instance_name, parent_phone_number,
                                   child_name, category):
    """Backward-compatible wrapper — builds constructive alert then sends."""
    from moderation.services.message_templates import (
        get_constructive_parent_alert_text,
    )
    alert_text = get_constructive_parent_alert_text(child_name, category)
    return get_evolution_client().send_parent_alert(
        instance_name, parent_phone_number, alert_text,
    )


def create_whatsapp_instance(instance_name):
    """Backward-compatible wrapper — see ``EvolutionAPIClient.create_instance``."""
    return get_evolution_client().create_instance(instance_name)


def get_qr_code(instance_name):
    """Backward-compatible wrapper — see ``EvolutionAPIClient.get_qr_code``."""
    return get_evolution_client().get_qr_code(instance_name)


def set_webhook_for_instance(instance_name, webhook_url):
    """Backward-compatible wrapper — see ``EvolutionAPIClient.set_webhook``."""
    get_evolution_client().set_webhook(instance_name, webhook_url)


def delete_whatsapp_instance(instance_name):
    """Backward-compatible wrapper — see ``EvolutionAPIClient.delete_instance``."""
    get_evolution_client().delete_instance(instance_name)


def check_connection_status(instance_name):
    """Backward-compatible wrapper — see ``EvolutionAPIClient.get_connection_status``."""
    return get_evolution_client().get_connection_status(instance_name)


def get_instance_details(instance_name):
    """Backward-compatible wrapper — see ``EvolutionAPIClient.get_instance_details``."""
    return get_evolution_client().get_instance_details(instance_name)


def get_all_instances():
    """Backward-compatible wrapper — see ``EvolutionAPIClient.get_all_instances``."""
    return get_evolution_client().get_all_instances()


def fetch_relationship_start(instance_name, remote_jid):
    """Query Evolution API for the oldest synced message in a chat.

    Tries both ``remoteJid`` and ``remoteJidAlt`` to handle LID contacts.
    """
    import datetime
    from django.utils import timezone

    client = get_evolution_client()

    def _try_fetch(jid_field, jid_value):
        data = client.fetch_messages(instance_name, jid_field, jid_value)
        if data is None:
            return []
        messages = []
        if isinstance(data, list):
            messages = data
        elif isinstance(data, dict):
            if "messages" in data and isinstance(data["messages"], list):
                messages = data["messages"]
            elif ("messages" in data and isinstance(data["messages"], dict)
                  and "records" in data["messages"]):
                messages = data["messages"]["records"]
            elif "data" in data and isinstance(data["data"], list):
                messages = data["data"]
        return [m for m in messages
                if isinstance(m, dict) and "messageTimestamp" in m]

    # Attempt 1: standard @s.whatsapp.net
    messages = _try_fetch("remoteJid", remote_jid)

    # Attempt 2: LID contacts store phone in remoteJidAlt
    if not messages:
        logger.info(
            f"[EVO API] 🔄 No messages with remoteJid={remote_jid}, "
            f"trying remoteJidAlt..."
        )
        messages = _try_fetch("remoteJidAlt", remote_jid)

    if messages:
        oldest = min(messages, key=lambda m: int(m["messageTimestamp"]))
        oldest_ts = int(oldest["messageTimestamp"])
        oldest_date = datetime.datetime.fromtimestamp(
            oldest_ts, tz=datetime.timezone.utc,
        )
        child_initiated = oldest.get("key", {}).get("fromMe", False)
        logger.info(
            f"[EVO API] 🕒 Relationship start for {remote_jid}: "
            f"{oldest_date.strftime('%Y-%m-%d')} | "
            f"Child Initiated: {child_initiated}"
        )
        return oldest_date, child_initiated

    logger.info(
        f"[EVO API] 🕒 No historical messages for {remote_jid}. "
        f"Defaulting to now."
    )
    return timezone.now(), False


def fetch_shared_groups(instance_name, sender_jid):
    """Fetch shared WhatsApp groups between the child and a sender.

    Returns a list of dicts with group metadata.
    """
    import datetime as _dt

    client = get_evolution_client()
    data = client.fetch_all_groups(instance_name)

    if data is None:
        return []

    # Normalise response shape
    groups = data
    if isinstance(groups, dict):
        groups = groups.get("data", groups.get("groups", []))
    if not isinstance(groups, list):
        logger.warning(
            f"[EVO API] ⚠️ fetchAllGroups returned unexpected type: "
            f"{type(groups)}"
        )
        return []

    sender_number = sender_jid.split('@')[0].replace('+', '').strip()

    shared = []
    for group in groups:
        participants = group.get("participants", [])
        group_numbers = set()

        for p in participants:
            if isinstance(p, dict):
                phone = p.get("phoneNumber", "")
                if phone:
                    clean = (str(phone).replace('+', '')
                             .replace(' ', '').replace('-', '').strip())
                    if clean:
                        group_numbers.add(clean)
                pid = p.get("id", "")
                if pid and "@s.whatsapp.net" in pid:
                    num = pid.split('@')[0].replace('+', '').strip()
                    if num:
                        group_numbers.add(num)
            elif isinstance(p, str):
                num = p.split('@')[0].replace('+', '').strip()
                if num:
                    group_numbers.add(num)

        if sender_number in group_numbers:
            group_name = group.get("subject", group.get("name", "Unknown Group"))
            creation_ts = group.get("creation", group.get("subjectTime", 0))
            try:
                created_at = (
                    _dt.datetime.fromtimestamp(
                        int(creation_ts), tz=_dt.timezone.utc,
                    ).strftime('%Y-%m-%d')
                    if creation_ts else "unknown"
                )
            except (ValueError, TypeError, OSError):
                created_at = "unknown"

            shared.append({
                "group_jid": group.get("id", ""),
                "group_name": group_name,
                "created_at": created_at,
                "participant_count": len(participants),
            })

    logger.info(
        f"[EVO API] 👥 Shared groups for {sender_jid}: "
        f"{len(shared)} found"
        + (f" — {[g['group_name'] for g in shared]}" if shared else "")
    )
    return shared
