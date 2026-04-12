import redis
import json
import hashlib
import re
import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Cache configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CACHE_TTL = 60 * 60 * 24 * 7  # 7 days

try:
    # We use a separate DB or just a prefix to avoid collision with Channels
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
except Exception as e:
    logger.error(f"[AEGIS-CACHE] Failed to connect to Redis: {e}")
    redis_client = None

def normalize_text(text):
    """
    Perform 'Deep Clean' for hashing:
    1. Lowercase
    2. Remove punctuation/emojis
    3. Collapse whitespace
    """
    if not text:
        return ""
    
    # Lowercase
    text = text.lower()
    
    # Remove emojis and punctuation (basic regex)
    # This keeps only alphanumeric and basic spaces
    text = re.sub(r'[^\w\s]', '', text)
    
    # Collapse multiple spaces into one and strip
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def get_message_hash(text):
    """Generate SHA-256 hash of normalized text."""
    normalized = normalize_text(text)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

def get_cached_prediction(text):
    """
    Checks Redis for a cached AI prediction.
    Returns prediction dict or None.
    """
    if not redis_client:
        return None
    
    msg_hash = get_message_hash(text)
    if not msg_hash:
        return None
        
    cache_key = f"aegis:prediction:{msg_hash}"
    
    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            logger.info(f"[AEGIS-CACHE] Hit for: '{text[:20]}...'")
            return json.loads(cached_data)
    except Exception as e:
        logger.error(f"[AEGIS-CACHE] Error reading from Redis: {e}")
        
    return None

def set_cached_prediction(text, prediction_data):
    """
    Saves an AI prediction to Redis.
    """
    if not redis_client:
        return
        
    msg_hash = get_message_hash(text)
    if not msg_hash:
        return
        
    cache_key = f"aegis:prediction:{msg_hash}"
    
    try:
        # Save as JSON string
        redis_client.setex(
            cache_key,
            CACHE_TTL,
            json.dumps(prediction_data)
        )
        logger.info(f"[AEGIS-CACHE] Saved prediction for: '{text[:20]}...'")
    except Exception as e:
        logger.error(f"[AEGIS-CACHE] Error writing to Redis: {e}")
