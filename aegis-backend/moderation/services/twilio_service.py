import os
import logging
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

logger = logging.getLogger(__name__)

def get_twilio_client():
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    if not account_sid or not auth_token:
        logger.warning("Twilio credentials not found in environment variables.")
        return None
    return Client(account_sid, auth_token)

def get_twilio_number():
    return os.getenv('TWILIO_PHONE_NUMBER')

def call_parent_emergency(parent_phone, child_name, category, severity="CRITICAL"):
    """
    Calls the parent with an automated voice message about a critical event.
    """
    client = get_twilio_client()
    from_number = get_twilio_number()
    
    if not client or not from_number:
        logger.error("Cannot make emergency call: Twilio is not configured.")
        return False
        
    try:
        # Build TwiML instruction for the call using Amazon Polly voice
        response = VoiceResponse()
        
        message = (
            f"This is the Aegis Safety System. "
            f"A critical event involving {child_name} has been detected. "
            f"The incident category is {category}. "
            f"Please check your parent dashboard immediately."
        )
        
        response.say(message, voice='Polly.Joanna', language='en-US')
        response.pause(length=1)
        response.say("I repeat. " + message, voice='Polly.Joanna', language='en-US')
        
        # Initiate the call
        call = client.calls.create(
            twiml=str(response),
            to=parent_phone,
            from_=from_number
        )
        
        logger.info(f"Initiated emergency call to {parent_phone} (Call SID: {call.sid})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initiate Twilio voice call: {e}")
        return False

def send_sms_alert(parent_phone, child_name, category, preview=""):
    """
    Sends an SMS alert to the parent.
    """
    client = get_twilio_client()
    from_number = get_twilio_number()
    
    if not client or not from_number:
        logger.error("Cannot send SMS alert: Twilio is not configured.")
        return False
        
    try:
        body = f"🚨 AEGIS ALERT: {child_name} - {category}. Check dashboard now."
        if preview:
            # truncate preview to keep SMS short
            body += f" Preview: {preview[:60]}..."
            
        message = client.messages.create(
            body=body,
            to=parent_phone,
            from_=from_number
        )
        
        logger.info(f"Sent emergency SMS to {parent_phone} (Message SID: {message.sid})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send Twilio SMS: {e}")
        return False
