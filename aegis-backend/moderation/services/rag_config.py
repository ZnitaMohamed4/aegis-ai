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
# Static expansions for common legal query patterns (French)
QUERY_EXPANSIONS = {
    "c'est quoi": "qu'est-ce que",
    "c quoi": "qu'est-ce que",
    "cest quoi": "qu'est-ce que",
    "loi 09-08": "loi numéro 09-08 protection des données personnelles",
    "loi 103-13": "loi numéro 103-13 violences faites aux femmes",
    "loi 05-20": "loi numéro 05-20 cybersécurité",
    "loi 07-03": "loi numéro 07-03 infractions informatiques cybercrime",
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
2. ABSOLUTE OBLIGATION: Format your answer using HTML tags (<b>text</b> for bold, <br> for line breaks).
3. STRICT PROHIBITION: Never mention sources, file names, or URLs in your text. The UI handles this.
4. LANGUAGE RULE: You MUST answer in the EXACT SAME LANGUAGE as the user's question. If they ask in English, answer in English. If French, answer in French. If Arabic, answer in Arabic.
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
}
