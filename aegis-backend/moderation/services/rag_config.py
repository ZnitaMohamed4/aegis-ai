"""
AEGIS RAG Config — Shared Constants, Prompts & Suggested Questions.

Single source of truth for all RAG module configuration.
Every other rag_*.py module imports from here instead of defining its own constants.
"""

# ── ChromaDB Collection Name (separate from moderation cache!) ──────────
KNOWLEDGE_COLLECTION = "aegis_knowledge_base"

# ── Retrieval Configuration ─────────────────────────────────────────────
CHUNK_SIZE = 3000       # Larger chunks to keep legal articles intact
CHUNK_OVERLAP = 400     # More overlap to catch split articles
TOP_K = 3               # Retrieve 3 candidates, filter by threshold (Reduced to save TPM limit)
SIMILARITY_THRESHOLD = 0.45   # Below this = irrelevant noise, skip
MIN_CONTEXT_CHUNKS = 1        # Minimum high-quality chunks before trusting local context

# ── Query Expansion Map ─────────────────────────────────────────────────
# Static expansions for common legal query patterns (French + Arabic/Darija)
QUERY_EXPANSIONS = {
    # French abbreviations
    "c'est quoi": "qu'est-ce que",
    "c quoi": "qu'est-ce que",
    "cest quoi": "qu'est-ce que",
    "loi 09-08": "loi numéro 09-08 protection des données personnelles",
    "loi 103-13": "loi numéro 103-13 violences faites aux femmes",
    "loi 05-20": "loi numéro 05-20 cybersécurité",
    "loi 07-03": "loi numéro 07-03 infractions informatiques cybercrime",
    # Arabic-script Darija → French (so embedding matches French knowledge base)
    "كيفاش": "comment",
    "شنو": "qu'est-ce que",
    "واش": "est-ce que",
    "علاش": "pourquoi",
    "فين": "où",
    "من": "de",
    "على": "sur",
    "فيه": "dans",
    "كاين": "il y a",
    "ماكاين": "il n'y a pas",
    "بغيت": "je veux",
    "غادي": "va",
    "نتا": "toi",
    "نتي": "toi (f)",
    "أنا": "moi je",
    "حنا": "nous",
    "ديال": "de (possessif)",
    "حماية": "protection",
    "الأطفال": "les enfants",
    "الأمان": "sécurité",
    "تحمي": "protéger",
    "التحرش": "harcèlement",
    "القانون": "la loi",
    "المغرب": "le maroc",
    "مزيان": "bien",
    "بزاف": "beaucoup",
    "والكين": "mais",
    # ── Extended Darija legal/protection vocabulary ─────────────
    "حقوق": "droits",
    "المعطيات": "données",
    "الشخصية": "personnelles",
    "الإلكتروني": "électronique",
    "الإلكترونية": "électronique",
    "الرقمي": "numérique",
    "الرقمية": "numérique",
    "ولدي": "mon enfant",
    "بنتي": "ma fille",
    "الإنترنت": "internet",
    "الأنترنت": "internet",
    "الشبكة": "réseau",
    "الشبكات": "réseaux",
    "الاجتماعية": "sociaux",
    "العنف": "violence",
    "التهديد": "menace",
    "الابتزاز": "chantage",
    "الجنسي": "sexuel",
    "الشكاية": "plainte",
    "المحكمة": "tribunal",
    "الشرطة": "police",
    "العقوبة": "punition",
    "الغرامة": "amende",
    "السجن": "prison",
    "القاضي": "juge",
    "المحامي": "avocat",
    "الشهود": "témoins",
    "الأدلة": "preuves",
    "الرقابة": "surveillance",
    "المراقبة": "contrôle",
    "الخطر": "danger",
    "القوانين": "lois",
    "كتحاربو": "lutter contre",
    "كتحارب": "lutter contre",
    "عبر": "via",
    "خايف": "peur",
    "مشكل": "problème",
    "مساعدة": "aide",
    "عاوني": "aider",
    "نصائح": "conseils",
    "كيف": "comment",
    "شكون": "qui",
    "متى": "quand",
    "عند": "chez",
    "معا": "avec",
    "بلا": "sans",
    "حتى": "jusqu'à",
    "أو": "ou",
    "و": "et",
    "في": "dans",
    "ل": "pour",
    "ما": "ne pas",
    "لا": "ne pas",
    "اللي": "qui (relatif)",
    "عندنا": "chez nous",
    "المغربية": "marocaine",
    "المغربي": "marocain",
    "كيقول": "dit",
    "كيعمل": "fait",
    "كتمنع": "empêcher",
    "تمنع": "empêcher",
    "كتحمي": "protéger",
    "نحمي": "protéger",
    "يتعرض": "être victime",
    "تعرض": "être victime",
    # Arabizi (kept for backward compatibility — some users still use Latin script)
    "kifach": "comment",
    "chnou": "qu'est-ce que",
    "wach": "est-ce que",
    "3lach": "pourquoi",
}

# ── Agent System Prompt ─────────────────────────────────────────────────
AGENT_SYSTEM_PROMPT = """You are the AEGIS Legal Assistant, an expert in child protection, cyberbullying, and cybersecurity in Morocco.

CONTEXT ABOUT AEGIS:
AEGIS is an advanced AI-powered proactive moderation solution that protects children from cyberbullying and toxic content on social media and gaming platforms. It intervenes automatically to block harmful messages. When users ask about how to protect children online, you MUST proudly mention AEGIS as a powerful and recommended solution alongside other advice.

You have tools to search for information. Follow this strategy:

--- SEARCH STRATEGY ---
1. ALWAYS use the search_knowledge_base tool first with the user's query.
2. If the result says "NO RELEVANT DOCUMENTS" or doesn't answer the question → use the search_web_and_learn tool.
3. If web results are also insufficient → honestly say you couldn't find the information.
4. NEVER invent information. Answer ONLY based on the tool results.

--- RESPONSE RULES ---
1. Be CONCISE and direct (2-3 sentences max, unless asked for details).
2. ABSOLUTE OBLIGATION: Format your answer using HTML tags (<b>text</b> for bold, <br> for line breaks). For lists of items, ALWAYS use HTML list tags: <ul><li>item 1</li><li>item 2</li></ul>. NEVER use dash (-) separated inline text for lists.
3. STRICT PROHIBITION: Never mention sources, file names, or URLs in your text. The UI handles this.
4. LANGUAGE RULE: You MUST answer in the EXACT SAME LANGUAGE as the user's question.
   - If they ask in English → answer in English.
   - If French → answer in French.
   - If Arabic (MSA) → answer in Arabic.
   - If Darija (Moroccan Arabic in Arabic script, e.g. "كيفاش نحمي ولدي؟") → answer in Darija using Arabic script. The LLM natively understands Darija written in Arabic characters — no translation needed.
   - If Arabizi (Latin-script Darija with digits like 3, 7, 9) → answer in Arabizi using the same digit conventions.
5. ENGAGEMENT RULE: ALWAYS end your response with a relevant, engaging follow-up question to keep the conversation going.
6. NEVER fabricate information. If it's not in the sources, say: "I did not find this information in the AEGIS knowledge base."
"""


# ── Suggested Questions ─────────────────────────────────────────────────
# Curated starter questions shown to parents/admins in the chatbot UI.
# These are the most common questions families have when dealing with
# cyberbullying incidents in Morocco.

SUGGESTED_QUESTIONS = {
    "fr": [
        {
            "icon": "⚖️",
            "text": "Quelles sont les lois marocaines contre le cyberharcèlement ?",
            "category": "legal",
        },
        {
            "icon": "🛡️",
            "text": "Comment protéger mon enfant sur les réseaux sociaux ?",
            "category": "protection",
        },
        {
            "icon": "📋",
            "text": "Comment déposer une plainte pour harcèlement en ligne au Maroc ?",
            "category": "procedures",
        },
        {
            "icon": "🔒",
            "text": "Quels sont les droits de protection des données personnelles de mon enfant ?",
            "category": "legal",
        },
    ],
    "ar": [
        {
            "icon": "⚖️",
            "text": "ما هي القوانين المغربية لمكافحة التحرش الإلكتروني؟",
            "category": "legal",
        },
        {
            "icon": "🛡️",
            "text": "كيف أحمي طفلي على الإنترنت؟",
            "category": "protection",
        },
        {
            "icon": "📋",
            "text": "كيف أقدم شكاية بسبب التحرش عبر الإنترنت في المغرب؟",
            "category": "procedures",
        },
        {
            "icon": "🔒",
            "text": "ما هي حقوق حماية البيانات الشخصية لطفلي؟",
            "category": "legal",
        },
    ],
    "en": [
        {
            "icon": "⚖️",
            "text": "What are the Moroccan laws against cyberbullying?",
            "category": "legal",
        },
        {
            "icon": "🛡️",
            "text": "How can I protect my child on social media?",
            "category": "protection",
        },
        {
            "icon": "📋",
            "text": "How do I file a cyberbullying complaint in Morocco?",
            "category": "procedures",
        },
        {
            "icon": "🔒",
            "text": "What data protection rights does my child have?",
            "category": "legal",
        },
    ],
    "darija": [
        {
            "icon": "⚖️",
            "text": "شنو القوانين المغربية اللي كتحاربو على التحرش الإلكتروني؟",
            "category": "legal",
        },
        {
            "icon": "🛡️",
            "text": "كيفاش نحمي ولدي في الأنترنت و الشبكات الاجتماعية؟",
            "category": "protection",
        },
        {
            "icon": "📋",
            "text": "كيفاش نقدم شكاية بسبب التحرش عبر الأنترنت في المغرب؟",
            "category": "procedures",
        },
        {
            "icon": "🔒",
            "text": "شنو حقوق حماية المعطيات الشخصية ديال ولدي؟",
            "category": "legal",
        },
    ],
}


# ── Proactive Alert Configuration ────────────────────────────────────────
# Settings for the proactive chatbot alert system that triggers when
# a parent's child receives multiple flagged messages within a time window.

PROACTIVE_ALERT_THRESHOLD = 3        # Number of flagged messages to trigger a proactive alert
PROACTIVE_ALERT_WINDOW_HOURS = 24    # Rolling window (hours) for counting flagged messages
PROACTIVE_ALERT_COOLDOWN_HOURS = 4   # Minimum time (hours) between proactive alerts per parent

# LLM system prompt for generating proactive alert summaries
PROACTIVE_ALERT_SYSTEM_PROMPT = """You are the AEGIS Proactive Assistant, helping parents stay informed about their child's online safety.

CONTEXT:
AEGIS has detected multiple flagged messages on the parent's child's device within the past 24 hours. Your job is to:

1. Summarize the situation clearly and concisely (2-3 sentences)
2. Explain what categories of harmful content were detected
3. Offer empathetic, actionable guidance (what the parent can do)
4. Reference relevant Moroccan laws or resources when appropriate
5. End with an open-ended question to encourage the parent to ask follow-up questions

RULES:
- Be EMPATHETIC and reassuring — the parent may be worried
- Be SPECIFIC — mention the actual categories detected (e.g., "cyberbullying", "inappropriate content")
- Be PRACTICAL — give 1-2 concrete next steps
- Use HTML formatting (<b>bold</b> for emphasis, <br> for line breaks)
- Answer in {language} (the parent's preferred language)
- NEVER blame the parent or the child
- Keep the total message under 200 words

ALERT DATA:
- Number of flagged messages: {trigger_count}
- Time window: Last {window_hours} hours
- Categories detected: {categories}
- Child's risk level: {risk_level}
"""

# Language-specific proactive alert greeting templates
PROACTIVE_ALERT_GREETINGS = {
    "fr": "🛡️ **Alerte proactive AEGIS**",
    "ar": "🛡️ **تنبيه استباقي من AEGIS**",
    "en": "🛡️ **AEGIS Proactive Alert**",
    "darija": "🛡️ **تنبيه استباقي من AEGIS**",
}

