"""
Language Agent — Multilingual support for JARVIS
Detects Hindi / Marathi / English from input text,
maps native-language command keywords to English intents,
and provides translated response templates for fallback mode.
"""
import re
import logging
from typing import Optional
from models.schemas import IntentType

logger = logging.getLogger("language_agent")

# ─────────────────────────────────────────────────────────────────────────────
# Language codes
# ─────────────────────────────────────────────────────────────────────────────
LANG_EN = "en"
LANG_HI = "hi"   # Hindi
LANG_MR = "mr"   # Marathi

# ─────────────────────────────────────────────────────────────────────────────
# Devanagari Unicode block: U+0900–U+097F
# Both Hindi and Marathi use the same Devanagari script.
# We differentiate by Marathi-specific vocabulary.
# ─────────────────────────────────────────────────────────────────────────────
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")

# Marathi-specific vocabulary (absent in Hindi)
MARATHI_MARKERS = {
    "आहे", "आहेत", "आहेस", "नाही", "नाहीत",
    "उघड", "उघडा", "सुरू", "करा", "सांग", "सांगा",
    "दाखव", "दाखवा", "शोध", "शोधा", "बंद कर",
    "हवामान", "मोजा", "कसे", "काय", "इथे", "तिथे",
    "मराठी", "महाराष्ट्र",
}

# Hindi-specific vocabulary
HINDI_MARKERS = {
    "खोलो", "खोलें", "बताओ", "दिखाओ", "करो", "कीजिए",
    "चलाओ", "बंद", "सर्च", "ढूंढो", "मौसम", "गणना",
    "हिंदी", "क्या", "कैसे", "यहाँ", "वहाँ", "नमस्ते",
    "हाँ", "नहीं", "ठीक", "अच्छा",
}

# ─────────────────────────────────────────────────────────────────────────────
# Native-language command → (intent, extracted_entity) patterns
# Order matters: more specific patterns first.
# ─────────────────────────────────────────────────────────────────────────────

# Regex: capture the app name after the open/close/search verb
# Hindi open patterns: "X खोलो", "X लॉन्च करो", "X चलाओ", "X खोलें"
HINDI_OPEN_RE = re.compile(
    r"(.+?)\s+(?:खोलो|खोलें|लॉन्च करो|चलाओ|स्टार्ट करो|शुरू करो|ओपन करो)$|"
    r"(?:खोलो|खोलें|लॉन्च करो|चलाओ)\s+(.+)",
    re.IGNORECASE,
)
HINDI_CLOSE_RE = re.compile(
    r"(.+?)\s+(?:बंद करो|बंद कीजिए|क्लोज करो|बंद करें)$|"
    r"(?:बंद करो|बंद करें)\s+(.+)",
    re.IGNORECASE,
)
HINDI_SEARCH_RE = re.compile(
    r"(?:सर्च करो|खोजो|ढूंढो|गूगल करो)\s+(?:के लिए\s+)?(.+)|"
    r"(.+?)\s+(?:सर्च करो|खोजो|ढूंढो)",
    re.IGNORECASE,
)
HINDI_CALCULATE_RE = re.compile(
    r"(?:गणना करो|कैलकुलेट करो|हिसाब लगाओ)\s+(.+)|"
    r"(.+?)\s+(?:का हिसाब|का जोड़|का गुणा)",
    re.IGNORECASE,
)

# Marathi open patterns
MARATHI_OPEN_RE = re.compile(
    r"(.+?)\s+(?:उघड|उघडा|सुरू कर|सुरू करा|लॉन्च कर|चालू कर|ओपन कर)$|"
    r"(?:उघड|सुरू कर|लॉन्च कर)\s+(.+)",
    re.IGNORECASE,
)
MARATHI_CLOSE_RE = re.compile(
    r"(.+?)\s+(?:बंद कर|बंद करा|क्लोज कर)$|"
    r"(?:बंद कर|बंद करा)\s+(.+)",
    re.IGNORECASE,
)
MARATHI_SEARCH_RE = re.compile(
    r"(?:शोध|शोधा|गूगल कर)\s+(.+)|"
    r"(.+?)\s+(?:शोध|शोधा)",
    re.IGNORECASE,
)

# ─────────────────────────────────────────────────────────────────────────────
# Simple keyword lists for intent detection (both languages)
# ─────────────────────────────────────────────────────────────────────────────

HINDI_INTENT_KEYWORDS: dict[IntentType, list[str]] = {
    IntentType.OPEN_APP:  ["खोलो", "खोलें", "लॉन्च", "चलाओ", "स्टार्ट", "शुरू", "ओपन"],
    IntentType.CLOSE_APP: ["बंद करो", "बंद करें", "बंद", "क्लोज"],
    IntentType.SEARCH_WEB:["सर्च", "खोजो", "ढूंढो", "गूगल"],
    IntentType.SYSTEM_INFO:["सिस्टम", "cpu", "ram", "मेमोरी", "स्टेटस", "जानकारी"],
    IntentType.CALCULATE: ["गणना", "कैलकुलेट", "हिसाब", "जोड़", "गुणा", "भाग"],
    IntentType.WEATHER:   ["मौसम", "तापमान", "बारिश"],
    IntentType.PLAY_MEDIA:["बजाओ", "म्यूजिक", "गाना"],
    IntentType.GENERAL_QUERY:["क्या", "कैसे", "बताओ", "नमस्ते", "हाल", "ठीक", "हाँ", "नहीं"],
}

MARATHI_INTENT_KEYWORDS: dict[IntentType, list[str]] = {
    IntentType.OPEN_APP:  ["उघड", "सुरू कर", "लॉन्च", "चालू कर", "ओपन"],
    IntentType.CLOSE_APP: ["बंद कर", "बंद करा", "क्लोज"],
    IntentType.SEARCH_WEB:["शोध", "शोधा", "गूगल"],
    IntentType.SYSTEM_INFO:["सिस्टम", "cpu", "ram", "माहिती", "स्टेटस"],
    IntentType.CALCULATE: ["मोजा", "कॅलक्युलेट", "हिशोब", "बेरीज"],
    IntentType.WEATHER:   ["हवामान", "तापमान", "पाऊस"],
    IntentType.PLAY_MEDIA:["वाजव", "संगीत", "गाणे"],
    IntentType.GENERAL_QUERY:["काय", "कसे", "नमस्कार", "सांग", "आहे", "ठीक"],
}

# ─────────────────────────────────────────────────────────────────────────────
# Response templates in Hindi and Marathi
# ─────────────────────────────────────────────────────────────────────────────

HINDI_RESPONSES: dict[IntentType, str] = {
    IntentType.OPEN_APP:      "ठीक है, {app} खोल रहा हूं सर।",
    IntentType.CLOSE_APP:     "{app} बंद कर रहा हूं।",
    IntentType.SEARCH_WEB:    "'{query}' के लिए इंटरनेट पर खोज रहा हूं।",
    IntentType.SYSTEM_INFO:   "सिस्टम जांच पूरी। सब कुछ सामान्य है।",
    IntentType.CALCULATE:     "गणना पूरी हो गई।",
    IntentType.WEATHER:       "मौसम की जानकारी खोल रहा हूं।",
    IntentType.PLAY_MEDIA:    "मीडिया चला रहा हूं।",
    IntentType.SET_REMINDER:  "रिमाइंडर सेट करने की सुविधा जल्द आएगी।",
    IntentType.SEND_MESSAGE:  "मैसेजिंग सेवा जल्द उपलब्ध होगी।",
    IntentType.GENERAL_QUERY: "जी सर, मैं आपकी सेवा में हाजिर हूं।",
    IntentType.UNKNOWN:       "माफ़ करें सर, मैं समझ नहीं पाया। कृपया दोबारा कहें।",
}

MARATHI_RESPONSES: dict[IntentType, str] = {
    IntentType.OPEN_APP:      "ठीक आहे, {app} उघडत आहे सर।",
    IntentType.CLOSE_APP:     "{app} बंद करत आहे।",
    IntentType.SEARCH_WEB:    "'{query}' शोधत आहे इंटरनेटवर।",
    IntentType.SYSTEM_INFO:   "सिस्टम तपासणी पूर्ण. सर्व काही सामान्य आहे।",
    IntentType.CALCULATE:     "गणना पूर्ण झाली।",
    IntentType.WEATHER:       "हवामान माहिती उघडत आहे।",
    IntentType.PLAY_MEDIA:    "मीडिया सुरू करत आहे।",
    IntentType.SET_REMINDER:  "रिमाइंडर सेट करण्याची सुविधा लवकरच येईल।",
    IntentType.SEND_MESSAGE:  "मेसेजिंग सेवा लवकरच उपलब्ध होईल।",
    IntentType.GENERAL_QUERY: "होय सर, मी आपल्या सेवेत आहे।",
    IntentType.UNKNOWN:       "माफ करा सर, मला समजले नाही। कृपया पुन्हा सांगा।",
}

# Success/failure suffixes
HINDI_SUCCESS_SUFFIX  = " ✓ काम पूरा हो गया।"
HINDI_FAILURE_SUFFIX  = " ✗ काम पूरा नहीं हो सका।"
MARATHI_SUCCESS_SUFFIX = " ✓ काम पूर्ण झाले।"
MARATHI_FAILURE_SUFFIX = " ✗ काम पूर्ण होऊ शकले नाही।"

# ─────────────────────────────────────────────────────────────────────────────
# Language Agent class
# ─────────────────────────────────────────────────────────────────────────────

class LanguageAgent:
    """
    Detects the language of user input and provides:
    1. Language code (en / hi / mr)
    2. Normalized English text for the NLP pipeline
    3. Extracted entities from native-language patterns
    4. Localized response template
    """

    def detect_language(self, text: str) -> str:
        """Return 'hi', 'mr', or 'en' based on script and vocabulary."""
        if not DEVANAGARI_RE.search(text):
            return LANG_EN

        # Check for Marathi markers first (since Hindi has broader overlap)
        for word in MARATHI_MARKERS:
            if word in text:
                logger.info(f"Language Agent: detected Marathi (marker='{word}')")
                return LANG_MR

        # Default Devanagari → Hindi
        logger.info("Language Agent: detected Hindi")
        return LANG_HI

    def extract_intent_and_entities(
        self, text: str, lang: str
    ) -> tuple[Optional[IntentType], dict, str]:
        """
        Try to extract intent + entities from native-language text.
        Returns (intent, entities, normalized_english_hint).
        All three may be None/empty if detection fails — NLP model takes over.
        """
        if lang == LANG_EN:
            return None, {}, text

        keywords = HINDI_INTENT_KEYWORDS if lang == LANG_HI else MARATHI_INTENT_KEYWORDS
        open_re  = HINDI_OPEN_RE  if lang == LANG_HI else MARATHI_OPEN_RE
        close_re = HINDI_CLOSE_RE if lang == LANG_HI else MARATHI_CLOSE_RE
        search_re = HINDI_SEARCH_RE if lang == LANG_HI else MARATHI_SEARCH_RE

        # ── Try regex-based extraction (most precise) ──────────────────────
        m = open_re.search(text)
        if m:
            app = (m.group(1) or m.group(2) or "").strip()
            entity = {"app": app.lower()} if app else {}
            hint = f"open {app}" if app else "open app"
            return IntentType.OPEN_APP, entity, hint

        m = close_re.search(text)
        if m:
            app = (m.group(1) or m.group(2) or "").strip()
            entity = {"app": app.lower()} if app else {}
            hint = f"close {app}" if app else "close app"
            return IntentType.CLOSE_APP, entity, hint

        m = search_re.search(text)
        if m:
            query = (m.group(1) or m.group(2) or "").strip()
            entity = {"query": query} if query else {}
            hint = f"search for {query}" if query else "search web"
            return IntentType.SEARCH_WEB, entity, hint

        m = HINDI_CALCULATE_RE.search(text) if lang == LANG_HI else None
        if m:
            expr = (m.group(1) or m.group(2) or "").strip()
            # Extract any embedded math expression
            math = re.search(r"[\d\s\+\-\*\/\.]+", expr)
            entity = {"expression": math.group(0).strip()} if math else {}
            return IntentType.CALCULATE, entity, f"calculate {expr}"

        # ── Keyword fallback ───────────────────────────────────────────────
        for intent, kw_list in keywords.items():
            for kw in kw_list:
                if kw in text:
                    # Try to extract an app name / query from adjacent English words
                    english_words = re.findall(r"[A-Za-z][A-Za-z0-9\s]*", text)
                    entity: dict = {}
                    if english_words:
                        val = english_words[0].strip().lower()
                        if intent in (IntentType.OPEN_APP, IntentType.CLOSE_APP):
                            entity = {"app": val}
                        elif intent == IntentType.SEARCH_WEB:
                            entity = {"query": val}
                    hint = f"{intent.value.replace('_', ' ')} {entity.get('app', entity.get('query', ''))}"
                    return intent, entity, hint.strip()

        return None, {}, text

    def localized_response(
        self,
        lang: str,
        intent: IntentType,
        entities: dict,
        automation_output: Optional[str],
        success: bool,
    ) -> Optional[str]:
        """
        Build a response in the user's language.
        Returns None for English (let Conversation Agent handle it normally).
        """
        if lang == LANG_EN:
            return None

        templates = HINDI_RESPONSES if lang == LANG_HI else MARATHI_RESPONSES
        success_sfx = HINDI_SUCCESS_SUFFIX if lang == LANG_HI else MARATHI_SUCCESS_SUFFIX
        failure_sfx = HINDI_FAILURE_SUFFIX if lang == LANG_HI else MARATHI_FAILURE_SUFFIX

        # If automation produced real output (e.g. system stats), include it
        if automation_output and intent == IntentType.SYSTEM_INFO:
            prefix = "सिस्टम स्थिति —" if lang == LANG_HI else "सिस्टम स्थिती —"
            return f"{prefix} {automation_output}"

        if automation_output and intent == IntentType.CALCULATE:
            prefix = "उत्तर:" if lang == LANG_HI else "उत्तर:"
            return f"{prefix} {automation_output}"

        tmpl = templates.get(intent, templates[IntentType.GENERAL_QUERY])
        response = tmpl.format(
            app=entities.get("app", "ऐप").title(),
            query=entities.get("query", ""),
            expression=entities.get("expression", ""),
        )

        # automation_output already incorporated above for SYSTEM_INFO/CALCULATE;
        # for other intents with output (e.g. close success), append it cleanly.
        if automation_output and automation_output.strip() and automation_output.strip() != response.strip():
            return automation_output  # Already clean English; just return it as-is

        suffix = success_sfx if success else failure_sfx
        return response + suffix


# ─────────────────────────────────────────────────────────────────────────────
# Pure helper — Translate simple English response to Hindi or Marathi
# (used for LLM responses when we detect non-English input)
# ─────────────────────────────────────────────────────────────────────────────

LANGUAGE_LABEL = {LANG_EN: "English", LANG_HI: "हिंदी", LANG_MR: "मराठी"}
VOICE_LANG_CODE = {LANG_EN: "en-US", LANG_HI: "hi-IN", LANG_MR: "mr-IN"}
SPEECH_LANG_CODE = {LANG_EN: "en-IN", LANG_HI: "hi-IN", LANG_MR: "mr-IN"}

# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────
_language_instance: Optional[LanguageAgent] = None


def get_language_agent() -> LanguageAgent:
    global _language_instance
    if _language_instance is None:
        _language_instance = LanguageAgent()
    return _language_instance
