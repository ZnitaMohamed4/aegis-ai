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
