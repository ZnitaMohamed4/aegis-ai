"""
AGENT 0: Transcription Agent — Speech-to-Text Gateway.

Handles WhatsApp voice messages directly within the LangGraph pipeline.

Provider strategy (Phase 5 — 2026-06-11):
  1. PRIMARY: Google Gemini 2.5 Flash  — superior Darija transcription quality.
     Produces accurate Arabic-script output for Moroccan Darija, handles
     French/English code-switching, and detects language automatically.
  2. FALLBACK: Groq Whisper-large-v3-turbo  — used only if Gemini fails
     (quota, network error, API key missing).

Flow:
  1. Detect if the incoming message contains audio (audio_message_data is set)
  2. Download audio from Evolution API as base64
  3. Call Gemini 2.5 Flash (primary) or Whisper (fallback)
  4. Set raw_text + detected_language so downstream agents can process it
  5. If no audio, pass through unchanged (text messages skip this agent)

Design rationale:
  - Gemini produces accurate Arabic-script Darija (e.g., "كي داير لاباس")
    while Whisper often garbles it (e.g., "كذى عير لبس")
  - detected_language from the transcriber is reused by the gatekeeper
  - Single API call (no n8n round-trip, no re-transcription needed)
  - Latency tracked in agent_0_latency_ms for dashboard metrics
"""
import base64 as _b64
import logging
import os
import time as _time

import requests

from .state import ModerationState

logger = logging.getLogger(__name__)

# ── Gemini transcription prompt ────────────────────────────────────────────────
# Bilingual-aware: handles Darija (Arabic script), French, and English code-switching.
# Gemini writes Arabic/Darija in Arabic script and keeps French/English in original script.
DARIJA_TRANSCRIPTION_PROMPT = (
    "Transcribe this audio exactly as spoken.\n"
    "Rules:\n"
    "- The audio may contain Moroccan Darija, Arabic, French, or English.\n"
    "- Write Arabic/Darija words in Arabic script.\n"
    "- If French or English words are spoken, keep them in their original script.\n"
    "- Do not translate, just transcribe word-for-word.\n"
    "- If audio is unclear, write [unclear]."
)


# ─────────────────────────────────────────────────────────────────────────────
# Audio download from Evolution API
# ─────────────────────────────────────────────────────────────────────────────

def _download_audio_from_evolution(instance: str, message_data: dict) -> tuple:
    """
    Download audio from Evolution API and return (base64_data, mime_type).

    Returns:
        Tuple of (base64_string, mimetype) or (None, "") on failure.
    """
    evo_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:5002')
    evo_key = os.getenv('EVOLUTION_API_KEY', '')

    try:
        resp = requests.post(
            f"{evo_url}/chat/getBase64FromMediaMessage/{instance}",
            headers={"apikey": evo_key},
            json={"message": message_data},
            timeout=15,
        )
        resp.raise_for_status()
        audio_resp = resp.json()
    except Exception as e:
        logger.warning("[AGENT 0] Failed to download audio from Evolution API: %s", e)
        return None, ""

    # Handle nested response format (Evolution sometimes returns a list)
    if isinstance(audio_resp, list):
        audio_resp = audio_resp[0] if audio_resp else {}

    base64_data = audio_resp.get("base64", "")
    mime_type = audio_resp.get("mimetype", "audio/ogg")

    if not base64_data:
        logger.warning("[AGENT 0] No base64 audio in Evolution API response")
        return None, ""

    # Strip data URI prefix if present (e.g. "data:audio/ogg;base64,...")
    if base64_data.startswith("data:"):
        base64_data = base64_data.split(",", 1)[1] if "," in base64_data else base64_data

    return base64_data, mime_type


# ─────────────────────────────────────────────────────────────────────────────
# Gemini 2.5 Flash transcription (PRIMARY)
# ─────────────────────────────────────────────────────────────────────────────

def _transcribe_with_gemini(base64_data: str, mime_type: str) -> tuple:
    """
    Call Google Gemini 2.5 Flash for high-quality Darija transcription.

    Gemini handles Moroccan Darija, Arabic, French, and English natively.
    It outputs Arabic-script for Darija/Arabic and original script for French/English.

    Returns:
        Tuple of (transcribed_text, detected_language_code) or (None, "") on failure.
        detected_language_code is inferred from the transcribed text: 'ar', 'en', 'fr', etc.
    """
    api_key = os.getenv('GEMINI_API_KEY', '') or os.getenv('GOOGLE_AI_API_KEY', '')
    if not api_key:
        logger.debug("[AGENT 0] GEMINI_API_KEY not set — skipping Gemini")
        return None, ""

    try:
        audio_bytes = _b64.b64decode(base64_data)
    except Exception as e:
        logger.warning("[AGENT 0] Failed to decode base64 audio for Gemini: %s", e)
        return None, ""

    # Gemini API endpoint (Google AI Studio)
    # Use stable model name — Google auto-resolves to latest version
    model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
        f"?key={api_key}"
    )

    # Map common MIME types to what Gemini expects
    gemini_mime = mime_type
    if mime_type == "audio/ogg":
        gemini_mime = "audio/ogg"  # Gemini supports audio/ogg natively

    payload = {
        "contents": [{
            "parts": [
                {"text": DARIJA_TRANSCRIPTION_PROMPT},
                {
                    "inline_data": {
                        "mime_type": gemini_mime,
                        "data": base64_data,
                    }
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 1024,
            # Disable thinking for faster transcription (Gemini 2.5 thinks by default)
            "thinkingConfig": {"thinkingBudget": 0},
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        body = e.response.text[:200] if e.response is not None else ""
        logger.warning("[AGENT 0] Gemini HTTP error %s: %s", status, body)
        return None, ""
    except Exception as e:
        logger.warning("[AGENT 0] Gemini transcription failed: %s", e)
        return None, ""

    # Parse Gemini response
    try:
        # Gemini sometimes returns HTTP 200 with an error in the body (e.g., 503 overload)
        if "error" in result:
            err_msg = result["error"].get("message", "unknown")[:200]
            logger.warning("[AGENT 0] Gemini returned error in 200 response: %s", err_msg)
            return None, ""

        candidates = result.get("candidates", [])
        if not candidates:
            logger.warning("[AGENT 0] Gemini returned no candidates")
            return None, ""

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            logger.warning("[AGENT 0] Gemini returned empty parts")
            return None, ""

        text = parts[0].get("text", "").strip()
        if not text:
            logger.warning("[AGENT 0] Gemini returned empty transcription")
            return None, ""

        # Infer language from the transcribed text
        # (Gemini does not return a language code directly — we detect it from output)
        arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
        latin_chars = sum(1 for c in text if c.isascii() and c.isalpha())
        if arabic_chars > latin_chars:
            lang = "ar"
        elif latin_chars > 0:
            # Could be English or French — downstream fasttext/gatekeeper will refine
            lang = "en"
        else:
            lang = "unknown"

        logger.info("[AGENT 0] Gemini transcription (inferred_lang=%s): %r", lang, text[:100])
        return text, lang

    except (KeyError, IndexError) as e:
        logger.warning("[AGENT 0] Failed to parse Gemini response: %s", e)
        return None, ""


# ─────────────────────────────────────────────────────────────────────────────
# Whisper-large-v3-turbo transcription (FALLBACK)
# ─────────────────────────────────────────────────────────────────────────────

def _transcribe_with_whisper(base64_data: str, mime_type: str) -> tuple:
    """
    Call Groq Whisper-large-v3-turbo with auto language detection.

    Used as fallback when Gemini is unavailable (quota, network, no API key).
    Whisper detects the spoken language and outputs text in the appropriate
    script (Latin for English, Arabic for Darija/Arabic, etc.).

    Returns:
        Tuple of (transcribed_text, detected_language_code) or (None, "") on failure.
        detected_language_code is an ISO 639-1 code: 'en', 'ar', 'fr', etc.
    """
    groq_key = os.getenv('GROQ_API_KEY', '')
    if not groq_key:
        logger.warning("[AGENT 0] GROQ_API_KEY not set — cannot transcribe with Whisper")
        return None, ""

    try:
        audio_bytes = _b64.b64decode(base64_data)
    except Exception as e:
        logger.warning("[AGENT 0] Failed to decode base64 audio: %s", e)
        return None, ""

    try:
        groq_resp = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {groq_key}"},
            files={"file": ("voice.ogg", audio_bytes, mime_type)},
            data={
                "model": "whisper-large-v3-turbo",
                "response_format": "verbose_json",
            },
            timeout=15,
        )
        groq_resp.raise_for_status()
        result = groq_resp.json()
        # Whisper returns full language names (e.g. "arabic", "english", "french")
        # but the gatekeeper expects ISO 639-1 codes ("ar", "en", "fr").
        # Normalize here so downstream routing works correctly.
        _WHISPER_LANG_TO_ISO = {
            "arabic": "ar", "english": "en", "french": "fr",
            "spanish": "es", "german": "de", "italian": "it",
            "portuguese": "pt", "dutch": "nl", "turkish": "tr",
            "indonesian": "id", "malay": "ms", "urdu": "ur",
            "persian": "fa", "hindi": "hi", "chinese": "zh",
            "japanese": "ja", "korean": "ko", "russian": "ru",
            "polish": "pl", "romanian": "ro", "hungarian": "hu",
            "swedish": "sv", "welsh": "cy",
        }
        raw_lang = result.get("language", "")  # e.g. "arabic", "english"
        lang = _WHISPER_LANG_TO_ISO.get(raw_lang.lower(), raw_lang)
        text = result.get("text", "").strip()

        if text:
            logger.info("[AGENT 0] Whisper transcription (lang=%s): %r", lang, text[:100])
            return text, lang
        else:
            logger.warning("[AGENT 0] Whisper returned empty transcription")
            return None, ""

    except Exception as e:
        logger.warning("[AGENT 0] Groq Whisper transcription failed: %s", e)
        return None, ""


# ─────────────────────────────────────────────────────────────────────────────
# Agent 0 Node — entry point for the LangGraph pipeline
# ─────────────────────────────────────────────────────────────────────────────

def transcriber_node(state: ModerationState) -> dict:
    """
    AGENT 0: Transcription Agent — Speech-to-Text Gateway.

    If the message contains audio (audio_message_data is set):
      - Download audio from Evolution API
      - Transcribe with Gemini 2.5 Flash (primary) or Whisper (fallback)
      - Set raw_text + detected_language from the transcriber
      - Mark is_voice_message=True

    If no audio: pass through unchanged (text messages skip this agent).
    """
    _t_start = _time.time()

    audio_data = state.get("audio_message_data")

    # ── No audio? Pass through unchanged ──────────────────────────────────────
    if not audio_data:
        _t_elapsed = int((_time.time() - _t_start) * 1000)
        logger.debug("[AGENT 0] No audio data — passing through (text message)")
        return {"agent_0_latency_ms": _t_elapsed}

    # ── Extract instance and message payload ─────────────────────────────────
    instance = state.get("instance_name", "")
    if not instance:
        logger.warning("[AGENT 0] Cannot determine Evolution API instance")
        _t_elapsed = int((_time.time() - _t_start) * 1000)
        return {
            "raw_text": "(Transcription failed: unknown instance)",
            "is_voice_message": True,
            "agent_0_latency_ms": _t_elapsed,
        }

    # ── Step 1: Download audio from Evolution API ─────────────────────────────
    base64_data, mime_type = _download_audio_from_evolution(instance, audio_data)

    if not base64_data:
        _t_elapsed = int((_time.time() - _t_start) * 1000)
        logger.warning("[AGENT 0] Audio download failed")
        return {
            "raw_text": "(Transcription failed: could not download audio)",
            "is_voice_message": True,
            "agent_0_latency_ms": _t_elapsed,
        }

    # ── Step 2: Transcribe — Gemini (primary with retry) → Whisper (fallback) ──
    transcription, detected_lang, provider = None, "", ""

    # Try Gemini 2.5 Flash (superior for Darija, also good for English)
    # Retry once on 503 high-traffic errors — Gemini overloads are transient
    _GEMINI_MAX_RETRIES = 1
    for attempt in range(1, _GEMINI_MAX_RETRIES + 2):  # 1 initial + 1 retry = 2 attempts
        transcription, detected_lang = _transcribe_with_gemini(base64_data, mime_type)
        if transcription:
            provider = "gemini"
            break
        if attempt <= _GEMINI_MAX_RETRIES:
            logger.info("[AGENT 0] Gemini attempt %d failed — retrying in 1s...", attempt)
            _time.sleep(1)

    # If Gemini failed after retries, fall back to Whisper
    if not transcription:
        logger.info("[AGENT 0] Gemini failed after %d attempts — falling back to Whisper", _GEMINI_MAX_RETRIES + 1)
        transcription, detected_lang = _transcribe_with_whisper(base64_data, mime_type)
        if transcription:
            provider = "whisper"

    _t_elapsed = int((_time.time() - _t_start) * 1000)

    if transcription:
        logger.info(
            "[AGENT 0] Transcription complete in %dms (provider=%s, lang=%s): %r",
            _t_elapsed, provider, detected_lang, transcription[:80]
        )
        return {
            "raw_text": transcription,
            "is_voice_message": True,
            "detected_language": detected_lang,
            "agent_0_latency_ms": _t_elapsed,
        }
    else:
        logger.warning("[AGENT 0] Transcription failed (both providers) after %dms", _t_elapsed)
        return {
            "raw_text": "(Transcription failed)",
            "is_voice_message": True,
            "agent_0_latency_ms": _t_elapsed,
        }
