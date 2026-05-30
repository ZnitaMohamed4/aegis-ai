import os
import tempfile
import logging
import requests
from PIL import Image
from PIL.ExifTags import TAGS

# We use pytesseract for OCR (Optical Character Recognition)
import pytesseract

logger = logging.getLogger(__name__)

# We use global variables to hold our models.
# They are initialized as None and only loaded the FIRST time an image arrives.
# This prevents Django from taking 10 seconds to start.
_nsfw_pipeline = None
_violence_pipeline = None

def _get_nsfw_pipeline():
    global _nsfw_pipeline
    if _nsfw_pipeline is None:
        from transformers import pipeline
        logger.info("Loading NSFW ViT model...")
        _nsfw_pipeline = pipeline("image-classification", model="Falconsai/nsfw_image_detection")
    return _nsfw_pipeline

def _get_violence_pipeline():
    """
    Load the jaranohaal/vit-base-violence-detection model.
    
    The model's config.json on HuggingFace is missing the `model_type` key,
    so pipeline() auto-detection fails. We explicitly load ViTForImageClassification
    and ViTImageProcessor to bypass auto-detection.
    Labels: 0 = non-violent, 1 = violent.
    """
    global _violence_pipeline
    if _violence_pipeline is None:
        from transformers import pipeline as hf_pipeline
        from transformers import ViTForImageClassification, ViTImageProcessor
        
        logger.info("Loading Violence ViT model...")
        model_name = "jaranohaal/vit-base-violence-detection"
        
        model = ViTForImageClassification.from_pretrained(model_name)
        processor = ViTImageProcessor.from_pretrained(model_name)
        
        _violence_pipeline = hf_pipeline(
            "image-classification",
            model=model,
            image_processor=processor,
        )
    return _violence_pipeline

import base64

def download_image(instance_name, message_obj):
    """Fetches the decrypted base64 image from Evolution API and saves it."""
    try:
        api_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
        api_key = os.getenv('EVOLUTION_API_KEY')
        
        url = f"{api_url}/chat/getBase64FromMediaMessage/{instance_name}"
        headers = {"apikey": api_key, "Content-Type": "application/json"}
        
        # Evolution API requires the full message payload to decrypt the media
        payload = {"message": message_obj}
        
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        base64_data = response.json().get("base64")
        if not base64_data:
            logger.error("No base64 data returned from Evolution API!")
            return None
            
        # Strip the data:image/jpeg;base64, prefix if present
        if "," in base64_data:
            base64_data = base64_data.split(",")[1]
            
        fd, temp_path = tempfile.mkstemp(suffix=".jpg")
        with os.fdopen(fd, 'wb') as f:
            f.write(base64.b64decode(base64_data))
            
        return temp_path
    except Exception as e:
        logger.error(f"Failed to fetch image from Evolution API: {e}")
        return None

def classify_image(path):
    """Runs the image through the NSFW and Violence Vision Transformers."""
    result = {
        "nsfw": False,
        "nsfw_score": 0.0,
        "violent": False,
        "violent_score": 0.0
    }
    try:
        image = Image.open(path).convert("RGB")
        
        # 1. NSFW Classification
        nsfw_pipe = _get_nsfw_pipeline()
        nsfw_preds = nsfw_pipe(image)
        # HuggingFace returns a list like: [{'label': 'normal', 'score': 0.9}, {'label': 'nsfw', 'score': 0.1}]
        for pred in nsfw_preds:
            if pred['label'].lower() == 'nsfw':
                result['nsfw_score'] = pred['score']
                if pred['score'] > 0.5:
                    result['nsfw'] = True
                    
        # 2. Violence Classification
        violence_pipe = _get_violence_pipeline()
        violence_preds = violence_pipe(image)
        # The model may return labels as 'violent'/'non-violent' or 'LABEL_0'/'LABEL_1'
        # From model config: 0 = non-violent, 1 = violent
        for pred in violence_preds:
            label = pred['label'].lower()
            if label in ['violent', 'violence', 'label_1']:
                result['violent_score'] = pred['score']
                if pred['score'] > 0.5:
                    result['violent'] = True
    except Exception as e:
        logger.error(f"Error classifying image {path}: {e}")
        
    return result

def extract_ocr_text(path):
    """Extracts text from the image using Tesseract."""
    try:
        image = Image.open(path)
        # We specify English, French, and Arabic as our target languages
        text = pytesseract.image_to_string(image, lang='eng+fra+ara')
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting OCR from {path}: {e}")
        return ""

def extract_metadata(path):
    """Extracts EXIF metadata (like GPS coordinates or camera info) if available."""
    try:
        img = Image.open(path)
        exif = img._getexif()
        return {TAGS.get(k, k): str(v) for k, v in exif.items()} if exif else {}
    except Exception as e:
        # Ignore errors if there is no EXIF data
        return {}

def analyze_image(instance_name, message_obj):
    """
    Main orchestration function.
    Downloads the image via Evolution API, runs all analyses, and cleans up.
    """
    result = {
        "nsfw": False,
        "nsfw_score": 0.0,
        "violent": False,
        "violent_score": 0.0,
        "ocr_text": "",
        "metadata": {}
    }
    
    path = download_image(instance_name, message_obj)
    if not path:
        return result
        
    try:
        # Update results from our ViT models
        classifications = classify_image(path)
        result.update(classifications)
        
        # Add OCR Text
        result["ocr_text"] = extract_ocr_text(path)
        
        # Add EXIF Metadata
        result["metadata"] = extract_metadata(path)
        
    finally:
        # Always delete the temporary file, even if an error occurs!
        if os.path.exists(path):
            os.remove(path)
            
    return result
