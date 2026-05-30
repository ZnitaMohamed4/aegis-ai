import re

def normalize_text(text: str) -> str:
    """Canonical text normalization for AEGIS pipeline."""
    text = str(text).strip()
    text = text.lower()
    text = re.sub(r'https?://\S+|www\.\S+', '', text) # URLs
    text = re.sub(r'@\w+', '', text) # @mentions
    text = re.sub(r'#(\w+)', r'\1', text) # #hashtags → hashtags
    text = re.sub(r'rt\s+', '', text) # RT prefix
    text = re.sub(r'&amp;', '&', text) # HTML entities
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'<user>', '', text) # HateXplain tokens
    text = re.sub(r'\s+', ' ', text).strip() # collapse whitespace
    return text
