"""
WhatsApp message templates for AEGIS automated responses.

Separated from API transport logic so templates can be reviewed, translated,
and tested independently of the HTTP layer.

Extracted during Phase 3 architecture cleanup (2026-05-20).
"""


# ══════════════════════════════════════════════════════════════════════════════
# WARNING TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

def _format_category(category: str) -> str:
    """Convert 'verbal_harassment' → 'Verbal Harassment'."""
    return category.replace('_', ' ').title()


def get_warning_text(category, decision, is_from_me, *, image_flags=None):
    """Return the warning auto-reply text for a given moderation decision.

    Args:
        category: Detected harassment category code (e.g. 'verbal_harassment').
        decision: Final pipeline decision (BLOCK, ESCALATE, WARN, REVISE).
        is_from_me: Whether the flagged message was sent by the monitored child.
        image_flags: Optional dict with keys: nsfw, violent, ocr_text.
    """
    is_nsfw = image_flags and image_flags.get("nsfw", False)
    is_violent = image_flags and image_flags.get("violent", False)
    has_ocr = image_flags and image_flags.get("ocr_text", "")
    cat_label = _format_category(category)

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
