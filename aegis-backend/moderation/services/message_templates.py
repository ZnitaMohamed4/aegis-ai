"""
WhatsApp message templates for AEGIS automated responses.

Separated from API transport logic so templates can be reviewed, translated,
and tested independently of the HTTP layer.

Language support: English (default), French, Arabic/Darija.
The language parameter ensures warnings are understood by the recipient.

Extracted during Phase 3 architecture cleanup (2026-05-20).
Language-aware templates added during Phase 4 hardening (2026-06-10).
"""


# ══════════════════════════════════════════════════════════════════════════════
# WARNING TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

def _format_category(category: str, language: str = "en") -> str:
    """Convert 'verbal_harassment' → human-readable label in the target language."""
    if language == "fr":
        _FR_CATEGORIES = {
            'verbal_harassment': 'Harcèlement Verbal',
            'threat': 'Menace',
            'sexual_harassment': 'Harcèlement Sexuel',
            'discrimination': 'Discrimination',
            'nsfw_image': 'Image Inappropriée',
            'violent_image': 'Image Violente',
            'safe': 'Sûr',
        }
        return _FR_CATEGORIES.get(category, category.replace('_', ' ').title())
    elif language in ("ar", "darija"):
        _AR_CATEGORIES = {
            'verbal_harassment': 'تحرش لفظي',
            'threat': 'تهديد',
            'sexual_harassment': 'تحرش جنسي',
            'discrimination': 'تمييز',
            'nsfw_image': 'صورة غير لائقة',
            'violent_image': 'صورة عنيفة',
            'safe': 'آمن',
        }
        return _AR_CATEGORIES.get(category, category.replace('_', ' ').title())
    # English (default)
    return category.replace('_', ' ').title()


def get_warning_text(category, decision, is_from_me, *, image_flags=None, language="en"):
    """Return the warning auto-reply text for a given moderation decision.

    Args:
        category: Detected harassment category code (e.g. 'verbal_harassment').
        decision: Final pipeline decision (BLOCK, ESCALATE, WARN, REVISE).
        is_from_me: Whether the flagged message was sent by the monitored child.
        image_flags: Optional dict with keys: nsfw, violent, ocr_text.
        language: Target language ("en", "fr", "ar", "darija"). Default: "en".
    """
    is_nsfw = image_flags and image_flags.get("nsfw", False)
    is_violent = image_flags and image_flags.get("violent", False)
    has_ocr = image_flags and image_flags.get("ocr_text", "")
    cat_label = _format_category(category, language)

    if language == "fr":
        if is_from_me:
            return _outgoing_warning_fr(cat_label, decision, is_nsfw, is_violent, has_ocr)
        return _incoming_warning_fr(cat_label, decision, is_nsfw, is_violent, has_ocr)
    elif language in ("ar", "darija"):
        if is_from_me:
            return _outgoing_warning_ar(cat_label, decision, is_nsfw, is_violent, has_ocr)
        return _incoming_warning_ar(cat_label, decision, is_nsfw, is_violent, has_ocr)

    # English (default)
    if is_from_me:
        return _outgoing_warning(cat_label, decision, is_nsfw, is_violent, has_ocr)
    return _incoming_warning(cat_label, decision, is_nsfw, is_violent, has_ocr)


def _outgoing_warning(cat_label, decision, is_nsfw, is_violent, has_ocr):
    """Warning text when the child sent the flagged message (self-moderation)."""
    header = "🛡️ *[AEGIS SAFETY SYSTEM]* 🛡️\n\n"

    if is_nsfw:
        return (
            f"{header}"
            f"📸 An image sent from this device was blocked for *NSFW Content*.\n\n"
            f"⚠️ _The image was flagged by our AI vision system and this incident has been logged._"
        )
    if is_violent:
        return (
            f"{header}"
            f"📸 An image sent from this device was blocked for *Violent Content*.\n\n"
            f"⚠️ _The image was flagged by our AI vision system and this incident has been logged._"
        )
    if has_ocr and decision in ('BLOCK', 'ESCALATE'):
        return (
            f"{header}"
            f"📸 An image sent from this device contained text flagged for *{cat_label}*.\n\n"
            f"⚠️ _The text was extracted and analyzed. This incident has been logged._"
        )
    if decision in ('BLOCK', 'ESCALATE'):
        return (
            f"{header}"
            f"A message sent by this device was blocked for *{cat_label}*.\n\n"
            f"⚠️ _The message was deleted and this incident has been logged to the Parental Dashboard._"
        )
    # WARN / REVISE
    return (
        f"{header}"
        f"A message sent by this device was flagged as a *Warning* for *{cat_label}*.\n\n"
        f"⚠️ _The message was NOT deleted, but this incident has been logged. Please be respectful._"
    )


def _incoming_warning(cat_label, decision, is_nsfw, is_violent, has_ocr):
    """Warning text when an external sender sent the flagged message."""
    header = "🛡️ *[AEGIS SAFETY SYSTEM]* 🛡️\n\n"

    if is_nsfw:
        return (
            f"{header}"
            f"📸 Your image was flagged for *NSFW Content* and violated safety protocols.\n\n"
            f"🚨 _This incident has been logged and reported. "
            f"Sending inappropriate images to a minor is a serious offense._"
        )
    if is_violent:
        return (
            f"{header}"
            f"📸 Your image was flagged for *Violent Content* and violated safety protocols.\n\n"
            f"🚨 _This incident has been logged and reported. "
            f"Further violations will result in an automatic block._"
        )
    if has_ocr and decision in ('BLOCK', 'ESCALATE'):
        return (
            f"{header}"
            f"📸 Text extracted from your image was flagged for *{cat_label}* "
            f"and violated safety protocols.\n\n"
            f"⚠️ _This incident has been logged and reported. "
            f"Further violations will result in an automatic block._"
        )
    if decision in ('BLOCK', 'ESCALATE'):
        return (
            f"{header}"
            f"Your message was flagged for *{cat_label}* and violated safety protocols.\n\n"
            f"⚠️ _This incident has been logged and reported. "
            f"Further violations will result in an automatic block._"
        )
    # WARN / REVISE
    return (
        f"{header}"
        f"Your message was flagged as a *Warning* for *{cat_label}*.\n\n"
        f"⚠️ _This incident has been lightly logged. Please maintain a respectful environment._"
    )


# ── FRENCH WARNING TEMPLATES ─────────────────────────────────────────────────

def _outgoing_warning_fr(cat_label, decision, is_nsfw, is_violent, has_ocr):
    """Warning en français quand l'enfant a envoyé le message signalé (auto-modération)."""
    header = "🛡️ *[SYSTÈME DE SÉCURITÉ AEGIS]* 🛡️\n\n"

    if is_nsfw:
        return (
            f"{header}"
            f"📸 Une image envoyée depuis cet appareil a été bloquée pour *Contenu NSFW*.\n\n"
            f"⚠️ _L'image a été signalée par notre système de vision IA et cet incident a été enregistré._"
        )
    if is_violent:
        return (
            f"{header}"
            f"📸 Une image envoyée depuis cet appareil a été bloquée pour *Contenu Violent*.\n\n"
            f"⚠️ _L'image a été signalée par notre système de vision IA et cet incident a été enregistré._"
        )
    if has_ocr and decision in ('BLOCK', 'ESCALATE'):
        return (
            f"{header}"
            f"📸 Le texte extrait d'une image envoyée depuis cet appareil a été signalé pour *{cat_label}*.\n\n"
            f"⚠️ _Le texte a été extrait et analysé. Cet incident a été enregistré._"
        )
    if decision in ('BLOCK', 'ESCALATE'):
        return (
            f"{header}"
            f"Un message envoyé depuis cet appareil a été bloqué pour *{cat_label}*.\n\n"
            f"⚠️ _Le message a été supprimé et cet incident a été enregistré dans le Tableau de Bord Parental._"
        )
    # WARN / REVISE
    return (
        f"{header}"
        f"Un message envoyé depuis cet appareil a reçu un *Avertissement* pour *{cat_label}*.\n\n"
        f"⚠️ _Le message n'a PAS été supprimé, mais cet incident a été enregistré. Merci d'être respectueux._"
    )


def _incoming_warning_fr(cat_label, decision, is_nsfw, is_violent, has_ocr):
    """Warning en français quand un expéditeur externe a envoyé le message signalé."""
    header = "🛡️ *[SYSTÈME DE SÉCURITÉ AEGIS]* 🛡️\n\n"

    if is_nsfw:
        return (
            f"{header}"
            f"📸 Votre image a été signalée pour *Contenu NSFW* et a violé les protocoles de sécurité.\n\n"
            f"🚨 _Cet incident a été enregistré et signalé. "
            f"Envoyer des images inappropriées à un mineur est une infraction grave._"
        )
    if is_violent:
        return (
            f"{header}"
            f"📸 Votre image a été signalée pour *Contenu Violent* et a violé les protocoles de sécurité.\n\n"
            f"🚨 _Cet incident a été enregistré et signalé. "
            f"De nouvelles violations entraîneront un blocage automatique._"
        )
    if has_ocr and decision in ('BLOCK', 'ESCALATE'):
        return (
            f"{header}"
            f"📸 Le texte extrait de votre image a été signalé pour *{cat_label}* "
            f"et a violé les protocoles de sécurité.\n\n"
            f"⚠️ _Cet incident a été enregistré et signalé. "
            f"De nouvelles violations entraîneront un blocage automatique._"
        )
    if decision in ('BLOCK', 'ESCALATE'):
        return (
            f"{header}"
            f"Votre message a été signalé pour *{cat_label}* et a violé les protocoles de sécurité.\n\n"
            f"⚠️ _Cet incident a été enregistré et signalé. "
            f"De nouvelles violations entraîneront un blocage automatique._"
        )
    # WARN / REVISE
    return (
        f"{header}"
        f"Votre message a reçu un *Avertissement* pour *{cat_label}*.\n\n"
        f"⚠️ _Cet incident a été légèrement enregistré. Merci de maintenir un environnement respectueux._"
    )


# ── ARABIC/DARIJA WARNING TEMPLATES ──────────────────────────────────────────

def _outgoing_warning_ar(cat_label, decision, is_nsfw, is_violent, has_ocr):
    """Warning text in Arabic/Darija when the child sent the flagged message (self-moderation)."""
    header = "🛡️ *[نظام أيجيس للحماية]* 🛡️\n\n"

    if is_nsfw:
        return (
            f"{header}"
            f"📸 تم حظر صورة مرسلة من هذا الجهاز بسبب *محتوى غير لائق*.\n\n"
            f"⚠️ _تم اكتشاف الصورة بواسطة نظام الرؤية الذكي وتم تسجيل هذا الحادث._"
        )
    if is_violent:
        return (
            f"{header}"
            f"📸 تم حظر صورة مرسلة من هذا الجهاز بسبب *محتوى عنيف*.\n\n"
            f"⚠️ _تم اكتشاف الصورة بواسطة نظام الرؤية الذكي وتم تسجيل هذا الحادث._"
        )
    if has_ocr and decision in ('BLOCK', 'ESCALATE'):
        return (
            f"{header}"
            f"📸 النص المستخرج من صورة مرسلة من هذا الجهاز تم الإبلاغ عنه بسبب *{cat_label}*.\n\n"
            f"⚠️ _تم استخراج النص وتحليله. تم تسجيل هذا الحادث._"
        )
    if decision in ('BLOCK', 'ESCALATE'):
        return (
            f"{header}"
            f"تم حظر رسالة مرسلة من هذا الجهاز بسبب *{cat_label}*.\n\n"
            f"⚠️ _تم حذف الرسالة وتم تسجيل هذا الحادث في لوحة تحكم الوالدين._"
        )
    # WARN / REVISE
    return (
        f"{header}"
        f"تلقت رسالة مرسلة من هذا الجهاز *تحذيراً* بسبب *{cat_label}*.\n\n"
        f"⚠️ _لم يتم حذف الرسالة، ولكن تم تسجيل هذا الحادث. يرجى أن تكون محترماً._"
    )


def _incoming_warning_ar(cat_label, decision, is_nsfw, is_violent, has_ocr):
    """Warning text in Arabic/Darija when an external sender sent the flagged message."""
    header = "🛡️ *[نظام أيجيس للحماية]* 🛡️\n\n"

    if is_nsfw:
        return (
            f"{header}"
            f"📸 تم الإبلاغ عن صورتك بسبب *محتوى غير لائق* وخرقت بروتوكولات الأمان.\n\n"
            f"🚨 _تم تسجيل هذا الحادث والإبلاغ عنه. "
            f"إرسال صور غير لائقة لقاصر يعتبر جريمة خطيرة._"
        )
    if is_violent:
        return (
            f"{header}"
            f"📸 تم الإبلاغ عن صورتك بسبب *محتوى عنيف* وخرقت بروتوكولات الأمان.\n\n"
            f"🚨 _تم تسجيل هذا الحادث والإبلاغ عنه. "
            f"المخالفات المتكررة ستؤدي إلى حظر تلقائي._"
        )
    if has_ocr and decision in ('BLOCK', 'ESCALATE'):
        return (
            f"{header}"
            f"📸 تم الإبلاغ عن النص المستخرج من صورتك بسبب *{cat_label}* "
            f"وخرق بروتوكولات الأمان.\n\n"
            f"⚠️ _تم تسجيل هذا الحادث والإبلاغ عنه. "
            f"المخالفات المتكررة ستؤدي إلى حظر تلقائي._"
        )
    if decision in ('BLOCK', 'ESCALATE'):
        return (
            f"{header}"
            f"تم الإبلاغ عن رسالتك بسبب *{cat_label}* وخرقت بروتوكولات الأمان.\n\n"
            f"⚠️ _تم تسجيل هذا الحادث والإبلاغ عنه. "
            f"المخالفات المتكررة ستؤدي إلى حظر تلقائي._"
        )
    # WARN / REVISE
    return (
        f"{header}"
        f"تلقت رسالتك *تحذيراً* بسبب *{cat_label}*.\n\n"
        f"⚠️ _تم تسجيل هذا الحادث بشكل بسيط. يرجى الحفاظ على بيئة محترمة._"
    )


# ══════════════════════════════════════════════════════════════════════════════
# EDUCATIONAL DM TEMPLATES (Child Self-Moderation)
# ══════════════════════════════════════════════════════════════════════════════

# Category-specific educational messages — empathetic, short, and punchy
EDUCATIONAL_TEMPLATES = {
    'verbal_harassment': (
        "Hey 👋 I noticed your last message was pretty harsh. "
        "Words can really hurt — take a breath before you text. 🧘‍♂️"
    ),
    'threat': (
        "Hey 👋 That last message sounded like a threat. "
        "Even if you're just joking, that can get you in real trouble. 🛑"
    ),
    'sexual_harassment': (
        "Hey 👋 That message could make someone really uncomfortable. "
        "Let's keep the chat respectful. 🙏"
    ),
    'discrimination': (
        "Hey 👋 Using words that target who someone is isn't okay. "
        "Everyone deserves respect. 🌍"
    ),
    'repeated_messages': (
        "Hey 👋 You're sending a lot of messages fast! "
        "Give them some space to reply. 😅"
    ),
    'identity_theft': (
        "Hey 👋 Pretending to be someone else can cause real harm. "
        "Just be yourself! ⚠️"
    ),
}

_EDUCATIONAL_FALLBACK = (
    "Hey 👋 That last message was a bit much. "
    "Take a second to think before you hit send! 🌱"
)


def get_educational_dm_text(category):
    """Return the educational DM text for a child self-moderation event.

    This is NOT a punitive warning — it's an educational ally helping the child
    understand why their message could be harmful.
    """
    body = EDUCATIONAL_TEMPLATES.get(category, _EDUCATIONAL_FALLBACK)
    return (
        f"🛡️ *Aegis Assistant*\n\n"
        f"{body}\n\n"
        f"💡 _If you need to vent, just text me! I'm here to listen._"
    )


# ══════════════════════════════════════════════════════════════════════════════
# ADULT SELF-REFLECTION TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

_ADULT_CATEGORY_TIPS = {
    'threat': (
        "This message contained language that could be perceived as threatening.",
        "💡 Tip: Try rephrasing your concern as an \"I feel...\" statement instead.",
    ),
    'verbal_harassment': (
        "This message was flagged for hostile or aggressive language.",
        "💡 Tip: Consider stepping away for 5 minutes before responding.",
    ),
    'sexual_harassment': (
        "This message contained content that may be inappropriate.",
        "💡 Tip: Would you say this to someone in person? That's a good test.",
    ),
    'discrimination': (
        "This message contained potentially discriminatory language.",
        "💡 Tip: Consider how this message might impact someone from a different background.",
    ),
}

_ADULT_DEFAULT_TIP = (
    "This message was flagged by the moderation system.",
    "💡 Tip: Take a moment to reflect before sending.",
)

# Crisis categories that trigger resource cards
_CRISIS_CATEGORIES = {'self_harm', 'suicide', 'self-harm', 'mental_health_crisis'}

_CRISIS_RESOURCES = (
    "\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "🆘 *You Are Not Alone*\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "If you or someone you know is in crisis:\n\n"
    "🇲🇦 *Morocco*\n"
    "• SOS Amitié: 0522 989 898\n"
    "• Ligne d'écoute AMANE: 0800 00 44 55\n\n"
    "🌍 *International*\n"
    "• 988 Suicide & Crisis Lifeline (US)\n"
    "• Crisis Text Line: Text HOME to 741741\n"
    "• Befrienders Worldwide: befrienders.org\n\n"
    "_These resources are free, confidential, and available 24/7._"
)


def get_adult_reflection_text(category, original_decision, score,
                              text_preview=None):
    """Return the self-reflection message for adult users.

    Includes Crisis Resource Cards for self-harm related categories
    and actionable advice per category.
    """
    tip_text, advice = _ADULT_CATEGORY_TIPS.get(category, _ADULT_DEFAULT_TIP)

    msg = (
        f"💭 *AEGIS Self-Reflection*\n\n"
        f"{tip_text}\n"
        f"Confidence: {score:.0%}\n\n"
        f"{advice}\n\n"
        f"_You can review your patterns on the AEGIS dashboard._"
    )

    if (category in _CRISIS_CATEGORIES
            or (original_decision == 'ESCALATE' and score > 0.85)):
        msg += _CRISIS_RESOURCES

    return msg


# ══════════════════════════════════════════════════════════════════════════════
# PARENT ALERT TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

def get_parent_alert_text(child_name, category, text_preview):
    """Return the critical parent alert text (alarming — 🚨 CRITICAL ALERT)."""
    cat_label = _format_category(category)
    return (
        f"🚨 *AEGIS CRITICAL ALERT* 🚨\n\n"
        f"A severely harmful message categorized as *{cat_label}* "
        f"was just intercepted on {child_name}'s device.\n\n"
        f"📝 _Preview_: \"{text_preview[:100]}...\"\n\n"
        f"Please check your AEGIS Dashboard immediately."
    )


def get_constructive_parent_alert_text(child_name, category):
    """Return the constructive parent notification text (calm — 🌱 GROWTH MOMENT).

    Different from ``get_parent_alert_text`` which is alarming.
    This is supportive and frames the incident as a learning opportunity.
    """
    cat_label = _format_category(category)
    return (
        f"🌱 *Aegis Growth Moment* 🌱\n\n"
        f"Aegis caught a message from {child_name} that was flagged as *{cat_label}*. "
        f"The message was intercepted and {child_name} received a private, "
        f"educational message from Aegis Assistant to help them understand why.\n\n"
        f"💡 _This is normal — children learn digital citizenship through moments like these. "
        f"Consider having a calm conversation about it._\n\n"
        f"📊 Check your AEGIS Dashboard for details."
    )
