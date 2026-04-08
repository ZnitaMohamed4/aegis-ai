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


def send_aegis_warning(instance_name, remote_jid, category, is_from_me, decision):
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
    
    payload = {
        "number": remote_jid,
        "text": warning_text
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            logger.info(f"[AEGIS] 🚨 Successfully sent warning Auto-Reply to {remote_jid}")
            return True
    except Exception as e:
        logger.error(f"[AEGIS] ❌ Error sending warning: {e}")
        
    return False
