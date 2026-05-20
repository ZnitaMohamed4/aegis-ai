"""
Evolution API Client — Facade Pattern.

Centralizes all Evolution API HTTP interactions behind a single client class.
Each public method is a thin wrapper around the shared ``_request()`` method,
which handles authentication, headers, error logging, and timeouts.

Module-level convenience functions (``send_text_message``, ``delete_message_from_whatsapp``,
etc.) are preserved for backward compatibility — they delegate to the singleton client.

Refactored during Phase 3 architecture cleanup (2026-05-20).
"""
import os
import logging

import requests

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# FACADE: EvolutionAPIClient
# ══════════════════════════════════════════════════════════════════════════════

class EvolutionAPIClient:
    """Facade for all Evolution API HTTP interactions.

    Reads ``EVOLUTION_API_URL`` and ``EVOLUTION_API_KEY`` from the environment
    once at construction time and reuses them for every call.
    """

    def __init__(self):
        self.base_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
        self.api_key = os.getenv('EVOLUTION_API_KEY', '')

    # ── Core HTTP helper ─────────────────────────────────────────────────

    def _request(self, method, path, payload=None, *, timeout=10,
                 extra_headers=None, raw_response=False):
        """Centralised HTTP method — handles auth, errors, and logging.

        Returns parsed JSON on success, or *None* on failure.
        When *raw_response* is True the raw ``requests.Response`` is returned
        instead so callers can inspect status codes themselves.
        """
        if not self.api_key:
            logger.error("[EVO API] ❌ Evolution API Key missing in .env!")
            return None

        headers = {"apikey": self.api_key, "Content-Type": "application/json"}
        if extra_headers:
            headers.update(extra_headers)

        url = f"{self.base_url}/{path.lstrip('/')}"

        try:
            resp = requests.request(
                method, url, json=payload, headers=headers, timeout=timeout,
            )
            if raw_response:
                return resp
            if resp.status_code in (200, 201):
                try:
                    return resp.json()
                except ValueError:
                    return True  # HTTP 200 but no JSON body
            logger.error(
                f"[EVO API] {method} {path} → {resp.status_code}: "
                f"{resp.text[:200]}"
            )
        except requests.exceptions.Timeout:
            logger.warning(f"[EVO API] {method} {path} → Timeout ({timeout}s)")
        except Exception as e:
            logger.error(f"[EVO API] {method} {path} → Exception: {e}")

        return None

    def _get(self, path, **kw):
        return self._request("GET", path, **kw)

    def _post(self, path, payload=None, **kw):
        return self._request("POST", path, payload=payload, **kw)

    def _delete(self, path, payload=None, **kw):
        return self._request("DELETE", path, payload=payload, **kw)

    # ── Messaging ────────────────────────────────────────────────────────

    def send_text(self, instance, jid, text, delay=1500):
        """Send a plain text message."""
        return self._post(f"message/sendText/{instance}", {
            "number": jid, "text": text, "delay": delay,
        })

    def send_reaction(self, instance, jid, message_key_id, is_from_me,
                      reaction="🚨"):
        """Pin a reaction emoji onto a message."""
        if not message_key_id:
            return None
        return self._post(f"message/sendReaction/{instance}", {
            "key": {
                "remoteJid": jid,
                "fromMe": is_from_me,
                "id": message_key_id,
            },
            "reaction": reaction,
        })

    def send_presence(self, instance, jid, presence="composing", delay=1500):
        """Simulate typing indicator."""
        return self._post(f"chat/sendPresence/{instance}", {
            "number": jid, "presence": presence, "delay": delay,
        })

    # ── Message Deletion ─────────────────────────────────────────────────

    def delete_message_for_everyone(self, instance, message_key_id, jid,
                                    is_from_me):
        """Delete a message for everyone.

        WhatsApp protocol limitation: we can only delete-for-everyone for
        messages **we** originated (``is_from_me=True``).
        """
        if not is_from_me:
            logger.warning(
                f"[EVO API] ⚠️ Cannot delete incoming message "
                f"{message_key_id}. Relying on Auto-Reply deterrence."
            )
            return False
        result = self._delete(
            f"chat/deleteMessageForEveryone/{instance}",
            payload={
                "id": message_key_id,
                "remoteJid": jid,
                "fromMe": is_from_me,
            },
        )
        if result is not None:
            logger.info("[EVO API] 🗑️ Successfully deleted message for everyone")
            return True
        return False

    # ── Warning / Alert Messages ─────────────────────────────────────────

    def send_warning(self, instance, jid, warning_text, *,
                     message_key_id=None, is_from_me=False, delay=1500):
        """Send a warning auto-reply, optionally as a quoted reply.

        Returns ``(msg_key_id, timestamp, full_response)`` on success
        so callers can use the response as an archive anchor.
        """
        payload = {"number": jid, "text": warning_text, "delay": delay}
        if message_key_id:
            payload["quoted"] = {
                "key": {
                    "id": message_key_id,
                    "remoteJid": jid,
                    "fromMe": is_from_me,
                }
            }

        resp = self._post(f"message/sendText/{instance}", payload)
        if resp and isinstance(resp, dict):
            logger.info(f"[EVO API] 🚨 Warning sent to {jid}")
            msg_id = resp.get("key", {}).get("id")
            msg_ts = resp.get("messageTimestamp")
            if msg_id and msg_ts:
                return (msg_id, msg_ts, resp)
            return True
        return False

    def send_parent_alert(self, instance, parent_phone, alert_text):
        """Send an alert message to a parent's WhatsApp number."""
        clean = str(parent_phone).replace("+", "").replace("-", "").replace(" ", "")
        result = self._post(f"message/sendText/{instance}", {
            "number": clean, "text": alert_text,
        })
        if result is not None:
            logger.info(f"[EVO API] 🚨 Parent alert sent to {clean}")
            return True
        return False

    def send_educational_dm(self, bot_instance, child_jid, dm_text):
        """Send an educational DM via the Aegis Assistant bot instance.

        Returns ``(message_key_id, dm_text)`` or ``(None, dm_text)`` on failure.
        """
        if not bot_instance:
            logger.warning("[EVO API] ⚠️ Bot instance not configured — skipping educational DM.")
            return None, dm_text

        resp = self._post(f"message/sendText/{bot_instance}", {
            "number": child_jid, "text": dm_text, "delay": 2000,
        })
        if resp and isinstance(resp, dict):
            msg_key_id = resp.get("key", {}).get("id")
            logger.info(f"[EVO API] 📚 Educational DM sent via {bot_instance}")
            return msg_key_id, dm_text
        return None, dm_text

    # ── Contact Management ───────────────────────────────────────────────

    def block_contact(self, instance, jid):
        """Block a contact so they can't send any more messages."""
        clean = jid.split('@')[0]
        logger.info(f"[EVO API] 🛡️ Attempting to BLOCK {clean}")
        result = self._post(f"chat/updateBlockStatus/{instance}", {
            "number": clean, "status": "block",
        })
        if result is not None:
            logger.info(f"[EVO API] 🛑 Successfully BLOCKED: {jid}")
            return True
        return False

    # ── Archive ──────────────────────────────────────────────────────────

    def archive_chat(self, instance, remote_jid, *,
                     warning_msg_key_id=None, warning_timestamp=None,
                     full_last_message=None, lid_jid=None):
        """Archive a chat via Evolution API / Baileys chatModify.

        Implements two strategies with retry logic to work around
        Evolution API's internal JID routing quirks.
        """
        import time as _time
        import json as _json

        effective_target = lid_jid if lid_jid else remote_jid

        # ── Strategy A: LID in lastMessage.key.remoteJid ─────────────
        def _build_strategy_a_payload():
            payload = {"chat": effective_target, "archive": True}
            if full_last_message:
                last_msg_node = dict(full_last_message)
                if isinstance(last_msg_node.get("key"), dict):
                    last_msg_node["key"] = dict(last_msg_node["key"])
                    last_msg_node["key"]["remoteJid"] = effective_target
                    last_msg_node["key"]["participant"] = remote_jid
                if not last_msg_node.get("message"):
                    last_msg_node["message"] = {"conversation": "⚠️"}
                payload["lastMessage"] = last_msg_node
            elif warning_msg_key_id:
                ts = warning_timestamp or int(_time.time())
                payload["lastMessage"] = {
                    "key": {
                        "remoteJid": effective_target,
                        "fromMe": True,
                        "id": warning_msg_key_id,
                        "participant": remote_jid,
                    },
                    "messageTimestamp": ts,
                    "message": {"conversation": "⚠️"},
                }
            return payload

        # ── Strategy B: No lastMessage — Prisma auto-lookup ──────────
        def _build_strategy_b_payload():
            return {"chat": remote_jid, "archive": True}

        strategies = [
            ("A: LID-in-remoteJid", _build_strategy_a_payload),
            ("B: Prisma-auto-lookup", _build_strategy_b_payload),
        ]

        url_path = f"chat/archiveChat/{instance}"

        for strategy_name, build_fn in strategies:
            payload = build_fn()
            logger.info("=" * 60)
            logger.info(f"[ARCHIVE] ── Strategy {strategy_name} ──")
            logger.info(f"[ARCHIVE] chat         : {payload.get('chat')}")
            last_key = payload.get("lastMessage", {}).get("key", {})
            logger.info(f"[ARCHIVE] lm.remoteJid : {last_key.get('remoteJid', 'N/A (Prisma lookup)')}")
            logger.info(f"[ARCHIVE] lm.id        : {last_key.get('id', 'N/A')}")
            logger.info(f"[ARCHIVE] FULL JSON:\n{_json.dumps(payload, indent=2, default=str)}")
            logger.info("=" * 60)

            delays = [0, 3, 7]
            for attempt, delay in enumerate(delays, 1):
                if delay > 0:
                    logger.info(f"[ARCHIVE] ⏳ Retry {attempt}/3 in {delay}s...")
                    _time.sleep(delay)

                resp = self._request(
                    "POST", url_path, payload=payload, raw_response=True,
                )
                if resp is None:
                    continue

                if resp.status_code in (200, 201):
                    resp_text = resp.text[:500]
                    logger.info(
                        f"[ARCHIVE] ✅ HTTP {resp.status_code} | "
                        f"Strategy {strategy_name} | Attempt {attempt}/3"
                    )
                    try:
                        resp_data = resp.json()
                        if resp_data.get("archived") is True:
                            logger.info(f"[EVO API] 🗃️ ✅ Archive CONFIRMED for {effective_target}")
                            return True
                        elif resp_data.get("archived") is False:
                            logger.warning(f"[ARCHIVE] ⚠️ API returned archived=false: {resp_text}")
                            break  # Try next strategy
                    except Exception:
                        pass
                    return True
                else:
                    logger.error(
                        f"[ARCHIVE] ❌ HTTP {resp.status_code} | "
                        f"Attempt {attempt}/3 | {resp.text[:500]}"
                    )
                    if resp.status_code == 404:
                        break

            logger.warning(f"[ARCHIVE] Strategy {strategy_name} exhausted. Trying next...")

        logger.error(f"[EVO API] ❌ All archive strategies failed for {effective_target}")
        return False

    # ── Instance Management ──────────────────────────────────────────────

    def create_instance(self, instance_name):
        """Create a new WhatsApp instance."""
        return self._post("instance/create", {
            "instanceName": instance_name,
            "integration": "WHATSAPP-BAILEYS",
            "qrcode": True,
        })

    def get_qr_code(self, instance_name):
        """Get the QR code for device pairing."""
        return self._get(f"instance/connect/{instance_name}")

    def set_webhook(self, instance_name, webhook_url):
        """Configure the webhook for an instance."""
        self._post(f"webhook/set/{instance_name}", {
            "webhook": {
                "enabled": True,
                "url": webhook_url,
                "byEvents": False,
                "base64": False,
                "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"],
            }
        })

    def delete_instance(self, instance_name):
        """Delete a WhatsApp instance."""
        self._delete(f"instance/delete/{instance_name}")

    def get_connection_status(self, instance_name):
        """Check if an instance is connected."""
        return self._get(f"instance/connectionState/{instance_name}")

    def get_instance_details(self, instance_name):
        """Fetch instance details including connected phone number."""
        data = self._get(
            f"instance/fetchInstances?instanceName={instance_name}",
        )
        if data and isinstance(data, list) and len(data) > 0:
            return data[0]
        return None

    def get_all_instances(self):
        """Fetch all instances from the Evolution API server."""
        data = self._get("instance/fetchInstances")
        return data if isinstance(data, list) else []

    # ── Chat History ─────────────────────────────────────────────────────

    def fetch_messages(self, instance, jid_field, jid_value):
        """Fetch messages from chat history, ordered by timestamp ascending."""
        return self._post(f"chat/findMessages/{instance}", {
            "where": {"key": {jid_field: jid_value}},
            "orderBy": {"messageTimestamp": "asc"},
            "take": 1,
        })

    def fetch_all_groups(self, instance):
        """Fetch all groups with participant lists."""
        return self._get(
            f"group/fetchAllGroups/{instance}?getParticipants=true",
            timeout=15,
        )


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ══════════════════════════════════════════════════════════════════════════════

_client = None


def get_evolution_client() -> EvolutionAPIClient:
    """Return the module-level singleton client instance."""
    global _client
    if _client is None:
        _client = EvolutionAPIClient()
    return _client


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
