import os
import requests
import logging

logger = logging.getLogger(__name__)

def delete_message_from_whatsapp(instance_name, message_key_id, remote_jid, is_from_me):
    """
    Calls Evolution API to delete a blocked message.
    If the child sent it, we delete for everyone.
    If a stranger sent it, we delete it locally from the child's phone.
    """
    api_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
    api_key = os.getenv('EVOLUTION_API_KEY')
    
    if not api_key:
        logger.error("[AEGIS] ❌ Evolution API Key missing in .env!")
        return False

    # WhatsApp Protocol Limitation: We CANNOT delete incoming messages locally 
    # from a linked device (Evolution API). We can only "Delete for Everyone" 
    # for messages we originated.
    if not is_from_me:
        logger.warning(f"[AEGIS] ⚠️ Cannot delete incoming message {message_key_id}. Relying on Auto-Reply deterrence.")
        return False

    url = f"{api_url}/chat/deleteMessageForEveryone/{instance_name}"
    
    headers = {
        "apikey": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "id": message_key_id,
        "remoteJid": remote_jid,
        "fromMe": is_from_me
    }

    try:
        response = requests.delete(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            action = "for everyone" if is_from_me else "locally"
            logger.info(f"[AEGIS] 🗑️ Successfully deleted message {action} on WhatsApp")
            return True
        else:
            logger.error(f"[AEGIS] ❌ Failed to delete message. Status: {response.status_code}, Resp: {response.text}")
            return False
    except Exception as e:
        logger.error(f"[AEGIS] ❌ Error calling Evolution API: {e}")
        return False


def send_aegis_warning(instance_name, remote_jid, category, is_from_me, decision, message_key_id=None):
    """
    Sends an automated warning using Evolution API.
    Different text depending on who sent the bad message and whether it was blocked.
    """
    api_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
    api_key = os.getenv('EVOLUTION_API_KEY')
    
    if not api_key:
        return False
        
    url = f"{api_url}/message/sendText/{instance_name}"
    
    headers = {
        "apikey": api_key,
        "Content-Type": "application/json"
    }

    # Format the warning based on who was the attacker and the severity
    if is_from_me:
        if decision in ['BLOCK', 'ESCALATE']:
            warning_text = (
                f"🛡️ *[AEGIS SAFETY SYSTEM]* 🛡️\n\n"
                f"A message sent by this device was blocked for *{category.replace('_', ' ').title()}*.\n\n"
                f"⚠️ _The message was deleted and this incident has been logged to the Parental Dashboard._"
            )
        else: # WARN
            warning_text = (
                f"🛡️ *[AEGIS SAFETY SYSTEM]* 🛡️\n\n"
                f"A message sent by this device was flagged as a *Warning* for *{category.replace('_', ' ').title()}*.\n\n"
                f"⚠️ _The message was NOT deleted, but this incident has been logged. Please be respectful._"
            )
    else:
        if decision in ['BLOCK', 'ESCALATE']:
            warning_text = (
                f"🛡️ *[AEGIS SAFETY SYSTEM]* 🛡️\n\n"
                f"Your message was flagged for *{category.replace('_', ' ').title()}* and violated safety protocols.\n\n"
                f"⚠️ _This incident has been logged and reported. Further violations will result in an automatic block._"
            )
        else: # WARN
            warning_text = (
                f"🛡️ *[AEGIS SAFETY SYSTEM]* 🛡️\n\n"
                f"Your message was flagged as a *Warning* for *{category.replace('_', ' ').title()}*.\n\n"
                f"⚠️ _This incident has been lightly logged. Please maintain a respectful environment._"
            )
    
    # 🎯 DELAY & TYPING LOGIC
    payload = {
        "number": remote_jid,
        "text": warning_text,
        "delay": 1500
    }
    
    # 🎯 QUOTED REPLY LOGIC
    # Evolution API v2 requires the 'quoted' object to be placed at the ROOT of the payload!
    if message_key_id:
        payload["quoted"] = {
            "key": {
                "id": message_key_id,
                "remoteJid": remote_jid,
                "fromMe": is_from_me
            }
        }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            logger.info(f"[AEGIS] 🚨 Successfully sent warning Auto-Reply to {remote_jid}")
            # Extract the message key ID, exact timestamp, AND the full node response from Evolution API.
            # Building a fully valid `lastMessage` anchor requires the full node structural shape.
            try:
                resp_data = response.json()
                warning_msg_id = resp_data.get("key", {}).get("id")
                warning_ts = resp_data.get("messageTimestamp")
                if warning_msg_id and warning_ts:
                    logger.info(f"[AEGIS] 📌 Warning message key ID: {warning_msg_id}, TS: {warning_ts}")
                    return (warning_msg_id, warning_ts, resp_data)
            except Exception:
                pass
            return True
    except Exception as e:
        logger.error(f"[AEGIS] ❌ Error sending warning: {e}")
        
    return False


def send_aegis_reaction(instance_name, remote_jid, message_key_id, is_from_me, reaction="🚨"):
    """
    Instantly slaps a reaction emoji onto a bad message to visually tag it before the warning.
    """
    api_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
    api_key = os.getenv('EVOLUTION_API_KEY')
    
    if not api_key or not message_key_id:
        return False
        
    url = f"{api_url}/message/sendReaction/{instance_name}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    
    # Evolution V2 strictly requires the key object for Reactions!
    payload = {
        "key": {
            "remoteJid": remote_jid,
            "fromMe": is_from_me,
            "id": message_key_id
        },
        "reaction": reaction
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            logger.info(f"[AEGIS] 🚨 Successfully pinned '{reaction}' reaction to message {message_key_id}")
            return True
    except Exception as e:
        logger.error(f"[AEGIS] ❌ Error sending reaction: {e}")
        
    return False

def send_aegis_presence(instance_name, remote_jid, presence="composing", delay=1500):
    """
    Evolution V2 requires a dedicated endpoint to simulate AEGIS magically typing!
    """
    api_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
    api_key = os.getenv('EVOLUTION_API_KEY')
    
    if not api_key:
        return False
        
    url = f"{api_url}/chat/sendPresence/{instance_name}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    
    payload = {
        "number": remote_jid,
        "presence": presence,
        "delay": delay
    }
    
    try:
        requests.post(url, json=payload, headers=headers)
        return True
    except Exception:
        return False

def block_contact(instance_name, remote_jid):
    """
    Instantly blocks the contact so they can't send any more messages.
    """
    api_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
    api_key = os.getenv('EVOLUTION_API_KEY')
    
    if not api_key: return False
    
    # /chat/ is the correct path for v2.3.6 (/message/ returns 404)
    url = f"{api_url}/chat/updateBlockStatus/{instance_name}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    
    # Extract plain phone number from the phone-based JID
    clean_number = remote_jid.split('@')[0]
    
    payload = {
        "number": clean_number,
        "status": "block"
    }
    
    try:
        logger.info(f"[AEGIS] 🛡️ Attempting to BLOCK {clean_number} via {url}")
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            logger.info(f"[AEGIS] 🛑 Successfully BLOCKED attacker: {remote_jid}")
            return True
        else:
            logger.error(f"[AEGIS] ❌ Failed to block contact. Status: {response.status_code}, Resp: {response.text}")
    except Exception as e:
        logger.error(f"[AEGIS] ❌ Error blocking contact: {e}")
    return False

def archive_chat(
    instance_name,
    remote_jid,               # phone JID (@s.whatsapp.net)
    warning_msg_key_id=None,
    warning_timestamp=None,
    full_last_message=None,
    lid_jid=None,             # LID JID (@lid)
):
    """
    Archives a chat via Evolution API / Baileys chatModify.

    CRITICAL BUG FOUND IN EVOLUTION API SOURCE CODE:
    ─────────────────────────────────────────────────
    When `lastMessage` is provided, Evolution API IGNORES the `chat` field entirely.
    The JID passed to Baileys' chatModify() is extracted from `lastMessage.key.remoteJid`:

        // Evolution API source (whatsapp.baileys.service.mjs):
        if (!t && o)
            t = await this.getLastMessage(o);   // only when NO lastMessage
        else
            (t = e.lastMessage, o = t?.key?.remoteJid);  // OVERWRITES chat target!
        await this.client.chatModify({...}, W(o));  // uses overwritten 'o'

    This means our `chat: @lid` was NEVER reaching Baileys.
    The fix: put the LID in `lastMessage.key.remoteJid` so it becomes the chatModify target.

    Strategy A: LID in lastMessage.key.remoteJid (preferred)
    Strategy B: No lastMessage, just `chat` field → Prisma auto-lookup (fallback)
    """
    import time as _time
    import json as _json

    api_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
    api_key = os.getenv('EVOLUTION_API_KEY')

    if not api_key:
        return False

    url = f"{api_url}/chat/archiveChat/{instance_name}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}

    # Resolve the target JID — prefer LID, fallback to phone JID
    effective_target = lid_jid if lid_jid else remote_jid

    # ── STRATEGY A: LID in lastMessage.key.remoteJid ─────────────────────
    # Since Evolution API extracts the chatModify JID from lastMessage.key.remoteJid,
    # we MUST put the correct target (LID) there, not the phone JID.
    def _build_strategy_a_payload():
        """Build payload with LID in lastMessage.key.remoteJid."""
        payload = {"chat": effective_target, "archive": True}

        if full_last_message:
            last_msg_node = dict(full_last_message)
            if isinstance(last_msg_node.get("key"), dict):
                last_msg_node["key"] = dict(last_msg_node["key"])
                # ✅ THE FIX: Put LID here so Evolution API passes it to chatModify
                last_msg_node["key"]["remoteJid"] = effective_target
                last_msg_node["key"]["participant"] = remote_jid  # phone JID for participant
            if not last_msg_node.get("message"):
                last_msg_node["message"] = {"conversation": "⚠️"}
            payload["lastMessage"] = last_msg_node

        elif warning_msg_key_id:
            ts = warning_timestamp or int(_time.time())
            payload["lastMessage"] = {
                "key": {
                    "remoteJid": effective_target,  # ✅ LID here
                    "fromMe": True,
                    "id": warning_msg_key_id,
                    "participant": remote_jid,
                },
                "messageTimestamp": ts,
                "message": {"conversation": "⚠️"},
            }
        return payload

    # ── STRATEGY B: No lastMessage — Prisma auto-lookup ──────────────────
    # Let Evolution API's getLastMessage() query Prisma by the phone JID.
    # When no lastMessage is provided, the `chat` field IS used as the
    # chatModify JID target (it doesn't get overwritten).
    def _build_strategy_b_payload():
        """Build minimal payload — let Evolution API handle lastMessage lookup."""
        return {"chat": remote_jid, "archive": True}

    # ── EXECUTE WITH RETRY ───────────────────────────────────────────────
    strategies = [
        ("A: LID-in-remoteJid", _build_strategy_a_payload),
        ("B: Prisma-auto-lookup", _build_strategy_b_payload),
    ]

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

        # Retry loop: 3 attempts with exponential backoff
        delays = [0, 3, 7]  # seconds before each attempt
        for attempt, delay in enumerate(delays, 1):
            if delay > 0:
                logger.info(f"[ARCHIVE] ⏳ Retry {attempt}/3 in {delay}s...")
                _time.sleep(delay)

            try:
                response = requests.post(url, json=payload, headers=headers)
                resp_text = response.text[:500]

                if response.status_code in [200, 201]:
                    logger.info(f"[ARCHIVE] ✅ HTTP {response.status_code} | Strategy {strategy_name} | Attempt {attempt}/3")
                    logger.info(f"[ARCHIVE] Response: {resp_text}")

                    # Check for actual success vs silent failure
                    try:
                        resp_data = response.json()
                        if resp_data.get("archived") is True:
                            logger.info(f"[AEGIS] 🗃️ ✅ Archive CONFIRMED for {effective_target}")
                            return True
                        elif resp_data.get("archived") is False:
                            logger.warning(f"[ARCHIVE] ⚠️ API returned archived=false: {resp_text}")
                            break  # Try next strategy
                    except Exception:
                        pass

                    return True  # HTTP 200 but couldn't parse — assume success
                else:
                    logger.error(f"[ARCHIVE] ❌ HTTP {response.status_code} | Attempt {attempt}/3 | {resp_text}")
                    if response.status_code == 404:
                        break  # Instance doesn't exist, don't retry
            except Exception as e:
                logger.error(f"[ARCHIVE] ❌ Exception on attempt {attempt}/3: {e}")

        logger.warning(f"[ARCHIVE] Strategy {strategy_name} exhausted. Trying next...")

    logger.error(f"[AEGIS] ❌ All archive strategies failed for {effective_target}")
    return False

def send_parent_alert(instance_name, parent_phone_number, child_name, category, text):
    """
    Sends an immediate critical alert to the parent's actual WhatsApp via Evolution API.
    """
    api_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
    api_key = os.getenv('EVOLUTION_API_KEY')
    
    if not api_key:
        return False
        
    url = f"{api_url}/message/sendText/{instance_name}"
    
    headers = {
        "apikey": api_key,
        "Content-Type": "application/json"
    }

    warning_text = (
        f"🚨 *AEGIS CRITICAL ALERT* 🚨\n\n"
        f"A severely harmful message categorized as *{category.replace('_', ' ').title()}* "
        f"was just intercepted on {child_name}'s device.\n\n"
        f"📝 _Preview_: \"{text[:100]}...\"\n\n"
        f"Please check your AEGIS Dashboard immediately."
    )
    
    clean_number = str(parent_phone_number).replace("+", "").replace("-", "").replace(" ", "")
    
    payload = {
        "number": clean_number,
        "text": warning_text
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            logger.info(f"[AEGIS] 🚨 Successfully sent parent alert to {clean_number}")
            return True
    except Exception as e:
        logger.error(f"[AEGIS] ❌ Error sending parent alert: {e}")
        
    return False


def create_whatsapp_instance(instance_name):
    """
    Step 1: Create the instance in Evolution API.
    """
    api_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
    api_key = os.getenv('EVOLUTION_API_KEY')
    url = f"{api_url}/instance/create"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    payload = {
        "instanceName": instance_name,
        "integration": "WHATSAPP-BAILEYS",
        "qrcode": True
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    except Exception as e:
        logger.error(f"Failed to create instance: {e}")
        return None

def get_qr_code(instance_name):
    """
    Step 2: Get the QR code base64 string for the scan.
    """
    api_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
    api_key = os.getenv('EVOLUTION_API_KEY')
    url = f"{api_url}/instance/connect/{instance_name}"
    headers = {"apikey": api_key}
    try:
        response = requests.get(url, headers=headers)
        return response.json()
    except Exception as e:
        logger.error(f"Failed to get QR: {e}")
        return None

def check_connection_status(instance_name):
    """
    Checks if the instance is currently 'open' (connected) or still 'close'.
    """
    api_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
    api_key = os.getenv('EVOLUTION_API_KEY')
    url = f"{api_url}/instance/connectionState/{instance_name}"
    headers = {"apikey": api_key}
    try:
        response = requests.get(url, headers=headers)
        return response.json()
    except Exception as e:
        logger.error(f"Failed to check connection: {e}")
        return None

def get_instance_details(instance_name):
    """
    Fetches the instance details to get the connected phone number.
    """
    api_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
    api_key = os.getenv('EVOLUTION_API_KEY')
    url = f"{api_url}/instance/fetchInstances?instanceName={instance_name}"
    headers = {"apikey": api_key}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0:
            return data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to get instance details: {e}")
        return None


def fetch_relationship_start(instance_name, remote_jid):
    """
    Queries Evolution API to find the oldest synced message in the chat history.
    Tries both remoteJid and remoteJidAlt to handle LID contacts.
    """
    from django.utils import timezone
    import datetime

    api_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
    api_key = os.getenv('EVOLUTION_API_KEY')

    if not api_key:
        return timezone.now()

    url = f"{api_url}/chat/findMessages/{instance_name}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}

    def try_fetch(jid_field, jid_value):
        payload = {
            "where": {
                "key": {
                    jid_field: jid_value
                }
            },
            "orderBy": {
                "messageTimestamp": "asc"
            },
            "take": 1
        }
        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code in [200, 201]:
                data = response.json()

                messages = []
                if isinstance(data, list):
                    messages = data
                elif isinstance(data, dict):
                    if "messages" in data and isinstance(data["messages"], list):
                        messages = data["messages"]
                    elif "messages" in data and isinstance(data["messages"], dict) and "records" in data["messages"]:
                        messages = data["messages"]["records"]
                    elif "data" in data and isinstance(data["data"], list):
                        messages = data["data"]

                valid_msgs = [m for m in messages if isinstance(m, dict) and "messageTimestamp" in m]
                return valid_msgs
        except Exception as e:
            logger.error(f"[AEGIS] ❌ Error in try_fetch({jid_field}={jid_value}): {e}")
        return []

    # Attempt 1: query by remoteJid (standard @s.whatsapp.net)
    messages = try_fetch("remoteJid", remote_jid)

    # Attempt 2: LID contacts store phone number in remoteJidAlt
    if not messages:
        logger.info(f"[AEGIS] 🔄 No messages found with remoteJid={remote_jid}, trying remoteJidAlt...")
        messages = try_fetch("remoteJidAlt", remote_jid)

    if messages:
        oldest_msg = min(messages, key=lambda m: int(m["messageTimestamp"]))
        oldest_ts = int(oldest_msg["messageTimestamp"])
        oldest_date = datetime.datetime.fromtimestamp(oldest_ts, tz=datetime.timezone.utc)
        child_initiated = oldest_msg.get("key", {}).get("fromMe", False)
        logger.info(f"[AEGIS] 🕒 Retrieved true relationship start date for {remote_jid}: {oldest_date.strftime('%Y-%m-%d')} | Child Initiated: {child_initiated}")
        return oldest_date, child_initiated

    logger.info(f"[AEGIS] 🕒 No historical messages found for {remote_jid}. Defaulting to now.")
    return timezone.now(), False

