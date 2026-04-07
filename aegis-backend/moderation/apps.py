import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)

class ModerationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'moderation'

    def ready(self):
        """
        In Django, the ready() method runs EXACTLY ONCE when the server starts.
        We use this to load heavy AI models into memory so they are instantly
        available when a WhatsApp message arrives.
        """
        from django.conf import settings
        from ml_pipeline.inference import AEGISPipeline

        # 1. Check if we are in "Stub Mode" (Fake AI for testing)
        stub_mode = getattr(settings, 'AEGIS_STUB_MODE', False)
        
        if stub_mode:
            logger.warning("[AEGIS] ⚠️ STUB MODE ACTIVE: Using keyword heuristics instead of real XLM-RoBERTa models.")
            return  # Stop here, don't try to load the heavy models from the hard drive!

        # 2. If Real Mode: get the paths to the M1/M2 models from settings.py
        m1_path = str(settings.BASE_DIR / settings.M1_MODEL_PATH)
        m2_path = str(settings.BASE_DIR / settings.M2_MODEL_PATH)
        threshold = getattr(settings, 'M1_THRESHOLD', 0.48)
        
        # 3. Load them into RAM
        try:
            AEGISPipeline.initialize(m1_path, m2_path, threshold)
            logger.info("[AEGIS] ✅ Real ML pipeline models loaded into memory successfully.")
        except Exception as e:
            logger.error(f"[AEGIS] ❌ Failed to load models from {m1_path} or {m2_path}. Error: {e}")

