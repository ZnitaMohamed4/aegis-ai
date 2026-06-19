"""
AEGIS RAG Guardrails — Input & Output Safety Checks.

Guardrails run BEFORE and AFTER the ReAct agent to ensure:
  1. Input:  Questions are on-topic for AEGIS domain
  2. Output: Answers are grounded in retrieved sources (no hallucination)
  3. Output: Answers match the user's target language

These are deterministic pre/post processing steps, NOT LLM tools.
The LLM doesn't decide whether to guard itself — we enforce it.
"""
import os
import logging

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)


def _get_fast_llm():
    """Get a fast, cheap LLM for guardrail classification tasks."""
    return ChatGroq(
        api_key=os.getenv("GROQ_API_KEY", "").strip().strip('"'),
        model_name="llama-3.1-8b-instant",
        temperature=0.0,
        max_tokens=200,
    )


# ═══════════════════════════════════════════════════════════════════════
#  INPUT GUARDRAIL: Topic Relevance
#  Blocks off-topic questions before the agent is even invoked
# ═══════════════════════════════════════════════════════════════════════

_TOPIC_CHECK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a topic classifier for AEGIS, a child protection and cybersecurity platform in Morocco.

Your job is to determine if a user's question is RELEVANT to any of these domains:
- Moroccan law (any law, penal code, family code, etc.)
- Child protection and child safety
- Cybersecurity and digital safety
- Data protection and privacy (RGPD, Loi 09-08, CNDP)
- Online harassment, bullying, grooming
- Digital citizenship and online safety education
- Human rights and violence prevention
- Internet safety for families
- Legal procedures (how to file complaints, report abuse, etc.)
- General questions about the AEGIS platform itself

RESPOND WITH EXACTLY ONE WORD:
- "RELEVANT" if the question is related to any of the above domains
- "IRRELEVANT" if the question is completely unrelated (e.g., weather, cooking, sports, entertainment, general chat)

Be GENEROUS in your classification — if there's ANY reasonable connection to child safety, law, or cybersecurity, classify as RELEVANT. Only block clearly off-topic questions."""),
    ("human", "Question: {question}")
])


# Refusal messages per language
_REFUSAL_MESSAGES = {
    "fr": (
        "Je suis l'Assistant Juridique AEGIS, spécialisé en protection de l'enfance "
        "et cybersécurité au Maroc. Je ne peux répondre qu'aux questions liées à ces "
        "domaines.<br><br>N'hésitez pas à me poser des questions sur les lois marocaines, "
        "la protection des enfants en ligne, ou la cybersécurité."
    ),
    "ar": (
        "أنا المساعد القانوني AEGIS، متخصص في حماية الطفولة والأمن السيبراني في المغرب. "
        "يمكنني فقط الإجابة على الأسئلة المتعلقة بهذه المجالات.<br><br>"
        "لا تتردد في سؤالي عن القوانين المغربية أو حماية الأطفال عبر الإنترنت أو الأمن السيبراني."
    ),
    "en": (
        "I'm the AEGIS Legal Assistant, specialized in child protection and "
        "cybersecurity in Morocco. I can only answer questions related to these "
        "domains.<br><br>Feel free to ask me about Moroccan laws, online child "
        "protection, or cybersecurity."
    ),
    "darija": (
        "أنا المساعد ديال AEGIS، متخصص في حماية الطفولة والأمن السيبراني في المغرب. "
        "غير نقدر نجاوب على الأسئلة اللي عندها علاقة بهاد المواضیع.<br><br>"
        "سولني على القوانين المغربية، كيفاش تحمي ولادك في الأنترنت، ولا الأمن السيبراني."
    ),
}

# Hallucination disclaimers per language — prepended when the guardrail
# detects that the answer isn't fully grounded in sources.
_HALLUCINATION_DISCLAIMERS = {
    "fr": (
        "<b>⚠️ Avertissement :</b> Cette réponse n'a pas pu être entièrement "
        "vérifiée dans nos sources. Les informations ci-dessous doivent être "
        "confirmées auprès d'un professionnel.<br><br>"
    ),
    "ar": (
        "<b>⚠️ تنبيه :</b> لم يتسنّ التحقق الكامل من هذه الإجابة في مصادرنا. "
        "يُرجى تأكيد المعلومات أدناه لدى مختص.<br><br>"
    ),
    "en": (
        "<b>⚠️ Disclaimer:</b> This answer could not be fully verified against "
        "our sources. The information below should be confirmed with a "
        "professional.<br><br>"
    ),
    "darija": (
        "<b>⚠️ تنبيه :</b> هاد الجواب ما قدرش يتأكد بالكامل من المصادر ديالنا. "
        "عافاك أكد هاد المعلومات مع شي مختص.<br><br>"
    ),
}


def _is_followup_in_active_session(session) -> bool:
    """Check if this is a follow-up question in a session with prior on-topic exchanges.

    If the session already has assistant responses (meaning prior questions passed
    the guardrail), then any new question in this session is treated as a follow-up
    and allowed through.  This prevents the LLM topic classifier from blocking short
    vague follow-ups like "tell me more" or "yes please" in non-English languages.
    """
    try:
        # Count prior assistant messages — if >= 1, the session already had
        # on-topic exchanges
        assistant_msgs = session.messages.filter(role='assistant').count()
        return assistant_msgs >= 1
    except Exception:
        return False


def input_topic_guardrail(question: str, language: str = "fr", session=None) -> tuple[bool, str]:
    """
    Check if the user's question is on-topic for AEGIS.

    Args:
        question: The user's raw question text
        language: Target language for the refusal message
        session: The current ChatSession (for follow-up detection)

    Returns:
        (is_allowed, reason) tuple:
        - (True, "") if the question is on-topic
        - (False, refusal_message) if the question is off-topic
    """
    from .rag_retrieval import _retrieve_context
    from .rag_config import SIMILARITY_THRESHOLD

    # Follow-up fast path: if the user is in an active session with prior
    # on-topic exchanges, treat follow-up questions as on-topic.  Short vague
    # follow-ups like "tell me more" or "yes please" should NOT be blocked.
    if session and _is_followup_in_active_session(session):
        logger.debug(f"[GUARDRAIL] \u2705 Follow-up in active session \u2014 skipping topic check")
        return True, ""

    try:
        # Fast path: check ChromaDB for any remotely similar context using the
        # canonical similarity threshold from the retrieval system to avoid
        # inconsistent pass/fail behavior between guardrail and retrieval.
        retrieved = _retrieve_context(question)
        if retrieved and retrieved[0]["score"] > SIMILARITY_THRESHOLD:
            logger.debug(f"[GUARDRAIL] ✅ Topic guardrail PASSED (embedding): '{question[:60]}...' (score={retrieved[0]['score']:.3f} >= {SIMILARITY_THRESHOLD})")
            return True, ""

        # Slow path: Fall back to LLM for ambiguous cases
        llm = _get_fast_llm()
        chain = _TOPIC_CHECK_PROMPT | llm | StrOutputParser()
        result = chain.invoke({"question": question}).strip().upper()

        if "IRRELEVANT" in result:
            refusal = _REFUSAL_MESSAGES.get(language, _REFUSAL_MESSAGES["fr"])
            logger.info(f"[GUARDRAIL] ❌ Topic guardrail BLOCKED (LLM): '{question[:60]}...'")
            return False, refusal

        logger.debug(f"[GUARDRAIL] ✅ Topic guardrail PASSED (LLM): '{question[:60]}...'")
        return True, ""

    except Exception as e:
        # Guardrail failure should NOT block the user — fail open
        logger.error(f"[GUARDRAIL] Topic check error (failing open): {e}")
        return True, ""


# ═══════════════════════════════════════════════════════════════════════
#  OUTPUT GUARDRAIL: Hallucination Detection
#  Checks if the answer is grounded in retrieved sources
# ═══════════════════════════════════════════════════════════════════════

_HALLUCINATION_CHECK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a fact-checking judge. Your job is to determine if an AI assistant's answer is GROUNDED in the provided source documents.

GROUNDED means: every factual claim in the answer can be traced back to the source documents. The answer may paraphrase or summarize, but must not invent facts, law articles, statistics, or procedures that aren't in the sources.

RULES:
- General knowledge statements (e.g., "cyberbullying is harmful") are acceptable even without sources
- The answer doesn't need to quote sources verbatim — paraphrasing is fine
- Mentioning the AEGIS AI system/tool as a solution or recommendation is ALWAYS acceptable and is NOT a hallucination.
- Engaging follow-up questions at the end of the answer are NOT hallucinations.
- If the answer says "I don't have this information" or similar, that's GROUNDED (it's honest)
- If sources are empty/missing and the answer still provides specific legal details → NOT GROUNDED
- CROSS-LANGUAGE RULE: The answer may be in a DIFFERENT language than the sources (e.g., answer in Arabic/Darija while sources are in French). This is NOT a hallucination — the assistant is expected to translate and summarize source content in the user's language. Judge the factual accuracy, not the language match.

RESPOND WITH EXACTLY ONE WORD:
- "GROUNDED" if the answer is faithful to the sources
- "HALLUCINATION" if the answer contains invented facts not in the sources"""),
    ("human", """SOURCE DOCUMENTS:
{sources}

AI ANSWER:
{answer}

Verdict:""")
])


def output_hallucination_guardrail(answer: str, sources_text: str, language: str = "fr") -> tuple[bool, str]:
    """
    Check if the agent's answer is grounded in the retrieved sources.

    Args:
        answer: The agent's generated answer
        sources_text: Concatenated text of all retrieved source documents
        language: Target language for the disclaimer if hallucination detected

    Returns:
        (is_grounded, flagged_answer) tuple:
        - (True, answer) if grounded — answer passes through unchanged
        - (False, modified_answer) if hallucination detected — disclaimer prepended
    """
    # Skip check if no sources were used (e.g., agent honestly said "I don't know")
    if not sources_text or len(sources_text.strip()) < 50:
        return True, answer

    try:
        llm = _get_fast_llm()
        chain = _HALLUCINATION_CHECK_PROMPT | llm | StrOutputParser()
        result = chain.invoke({
            "sources": sources_text[:3000],  # Limit context size for fast model
            "answer": answer[:1500],
        }).strip().upper()

        if "HALLUCINATION" in result:
            logger.warning(f"[GUARDRAIL] ⚠️ Hallucination detected in answer: '{answer[:80]}...'")
            disclaimer = _HALLUCINATION_DISCLAIMERS.get(
                language, _HALLUCINATION_DISCLAIMERS["fr"]
            )
            return False, disclaimer + answer

        logger.debug(f"[GUARDRAIL] ✅ Hallucination check PASSED")
        return True, answer

    except Exception as e:
        # Fail open — don't block the answer on guardrail errors
        logger.error(f"[GUARDRAIL] Hallucination check error (failing open): {e}")
        return True, answer


# ═══════════════════════════════════════════════════════════════════════
#  OUTPUT GUARDRAIL: Language Enforcement
#  Ensures the answer matches the user's preferred language
# ═══════════════════════════════════════════════════════════════════════

_LANGUAGE_NAMES = {
    "fr": "French",
    "ar": "Arabic",
    "en": "English",
    "darija": "Moroccan Darija (Arabic script — Darija dialect written in Arabic characters, common in Moroccan informal communication)",
}

_TRANSLATE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Translate the following text to {target_language}. 
Keep all HTML tags (<b>, <br>, etc.) intact. 
Preserve the meaning and tone exactly.
Output ONLY the translation, nothing else."""),
    ("human", "{text}")
])


def output_language_guardrail(answer: str, target_language: str) -> str:
    """
    Ensure the answer is in the correct language.

    Uses a simple heuristic first (check for language-specific characters),
    then falls back to LLM translation if needed.

    Args:
        answer: The agent's generated answer
        target_language: Target language code ("fr", "ar", "en")

    Returns:
        The answer, translated if necessary
    """
    if not answer or target_language not in _LANGUAGE_NAMES:
        return answer

    # Quick heuristic: check if the answer is already in the right language
    if _is_likely_correct_language(answer, target_language):
        return answer

    # If not, translate via LLM
    try:
        llm = _get_fast_llm()
        chain = _TRANSLATE_PROMPT | llm | StrOutputParser()
        translated = chain.invoke({
            "target_language": _LANGUAGE_NAMES[target_language],
            "text": answer,
        }).strip()

        if translated and len(translated) > 20:
            logger.info(f"[GUARDRAIL] 🌐 Language guardrail translated answer to {target_language}")
            return translated
        return answer

    except Exception as e:
        logger.error(f"[GUARDRAIL] Language check error (returning original): {e}")
        return answer


def _is_likely_correct_language(text: str, target_lang: str) -> bool:
    """
    Quick heuristic to check if text is in the expected language.
    Not perfect, but avoids unnecessary LLM calls for the common case.
    """
    # Strip HTML tags for analysis
    import re
    clean = re.sub(r'<[^>]+>', '', text).strip()

    if not clean:
        return True

    if target_lang == "ar":
        # Arabic text should contain Arabic Unicode characters
        arabic_chars = sum(1 for c in clean if '\u0600' <= c <= '\u06FF')
        return arabic_chars / max(len(clean), 1) > 0.3

    if target_lang == "fr":
        # French markers: accented characters common in French
        french_markers = sum(1 for c in clean if c in 'àâäéèêëïîôùûüçœæÀÂÄÉÈÊËÏÎÔÙÛÜÇŒÆ')
        # Also check for common French words
        fr_words = ['le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'est', 'dans', 'pour', 'sur', 'avec']
        words = clean.lower().split()
        fr_word_count = sum(1 for w in words if w in fr_words)
        return french_markers > 0 or fr_word_count >= 2

    if target_lang == "en":
        # English: check for common English words
        en_words = ['the', 'is', 'are', 'was', 'and', 'for', 'that', 'with', 'this', 'from', 'have', 'not']
        words = clean.lower().split()
        en_word_count = sum(1 for w in words if w in en_words)
        return en_word_count >= 2

    if target_lang == "darija":
        # Darija in Arabic script: must have Arabic Unicode characters.
        # We accept it as correct if it's Arabic-script text — the LLM
        # handles Darija dialect natively, no complex heuristic needed.
        arabic_chars = sum(1 for c in clean if '\u0600' <= c <= '\u06FF')
        if arabic_chars / max(len(clean), 1) > 0.3:
            return True  # Arabic-script text → likely Darija (LLM will handle it)
        # Also accept Arabizi (Latin-script Darija) for backward compatibility
        import re as _re
        arabizi_pattern = _re.search(r'[a-zA-Z]*[3579][a-zA-Z]*', clean)
        darija_markers = [
            'kifach', 'chnou', 'wach', 'fin', 'labas', 'mzyan', 'bghit',
            'ghadi', 'hna', 'nta', 'nti', 'dyal', 'bzaaf', 'walakin',
        ]
        words = clean.lower().split()
        darija_word_count = sum(1 for w in words if w in darija_markers)
        return bool(arabizi_pattern) or darija_word_count >= 2

    return True
