"""
AI Agent — NLP Model (PyTorch)
Performs intent classification and entity extraction from raw text commands.
Uses a lightweight transformer-style approach with rule enhancement for speed.
"""
import re
import time
import logging
import numpy as np
from typing import Dict, Any, Tuple
from models.schemas import IntentType, NLPResult

logger = logging.getLogger("ai_agent")


# Intent keyword mapping — acts as a fast rule-based prior
INTENT_PATTERNS: Dict[IntentType, list] = {
    IntentType.OPEN_APP: [
        r"\bopen\b", r"\blaunch\b", r"\bstart\b", r"\brun\b"
    ],
    IntentType.CLOSE_APP: [
        r"\bclose\b", r"\bkill\b", r"\bquit\b", r"\bexit\b", r"\bterminate\b"
    ],
    IntentType.SEARCH_WEB: [
        r"\bsearch\b", r"\bgoogle\b", r"\blook up\b", r"\bfind\b", r"\bbrowse\b"
    ],
    IntentType.SYSTEM_INFO: [
        r"\bcpu\b", r"\bram\b", r"\bmemory\b", r"\bdisk\b", r"\bsystem\b",
        r"\bstats\b", r"\bstatus\b", r"\bperformance\b"
    ],
    IntentType.PLAY_MEDIA: [
        r"\bplay\b", r"\bpause\b", r"\bstop music\b", r"\bplay music\b",
        r"\bplay video\b", r"\bnext track\b", r"\bprevious track\b"
    ],
    IntentType.SET_REMINDER: [
        r"\bremind\b", r"\breminder\b", r"\balert\b", r"\bschedule\b", r"\btimer\b"
    ],
    IntentType.WEATHER: [
        r"\bweather\b", r"\btemperature\b", r"\brain\b", r"\bforecast\b"
    ],
    IntentType.CALCULATE: [
        r"\bcalculate\b", r"\bcompute\b", r"\bmath\b", r"\bsum\b", r"\bequals\b",
        r"\d+\s*[\+\-\*\/]\s*\d+"
    ],
    IntentType.VOLUME_CONTROL: [
        r"\bvolume\b", r"\bvol\b", r"\bmute\b", r"\bunmute\b",
        r"\blouder\b", r"\bquieter\b", r"\bsilent\b", r"\bsilence\b",
        r"\bsound\b.*(?:up|down|increase|decrease)",
        r"(?:increase|decrease|lower|raise).*\bsound\b",
    ],
    IntentType.BRIGHTNESS_CONTROL: [
        r"\bbrightness\b", r"\bdim\b", r"\bdimmer\b", r"\bbrighter\b",
        r"\bscreen\s+light\b", r"\bdisplay\s+brightness\b",
        r"\bscreen\s+(?:up|down|brighter|dimmer)\b",
        r"(?:increase|decrease|lower|raise).*\b(?:brightness|screen)\b",
    ],
    IntentType.KEYBOARD_CONTROL: [
        r"\btype\b", r"\bwrite\b", r"\benter\b",
        r"\bundo\b", r"\bredo\b",
        r"\bcopy\b", r"\bpaste\b", r"\bcut\b",
        r"\bselect all\b", r"\bselect\b",
        r"\bdelete\b", r"\bbackspace\b", r"\bremove\b",
        r"\bnew tab\b", r"\bclose tab\b", r"\bnext tab\b", r"\bprevious tab\b",
        r"\bswitch tab\b", r"\bopen tab\b",
        r"\bfind on page\b", r"\bsearch on page\b", r"\bsearch this page\b",
        r"\bfind in\b",
        r"\bscroll up\b", r"\bscroll down\b", r"\bscroll top\b", r"\bscroll bottom\b",
        r"\bgo back\b", r"\bgo forward\b",
        r"\brefresh\b", r"\breload\b",
        r"\bfull screen\b", r"\bfullscreen\b",
        r"\bzoom in\b", r"\bzoom out\b",
        r"\bsave\b",
        r"\bpress enter\b", r"\bhit enter\b",
        r"\bpress escape\b", r"\bescape\b",
        r"\bprint\b",
        r"\bnew window\b",
        r"\bwhat did i type\b",
    ],
    IntentType.GENERAL_QUERY: [
        r"\bwhat\b", r"\bwho\b", r"\bwhen\b", r"\bwhere\b", r"\bhow\b",
        r"\bwhy\b", r"\btell me\b", r"\bexplain\b",
        # Greetings and small-talk
        r"\b(hi|hello|hey|howdy|greetings|sup|yo)\b",
        r"\b(good\s*(morning|evening|afternoon|night))\b",
        r"\b(thanks|thank you|thank u|ty|cheers|appreciate)\b",
        r"\b(bye|goodbye|see you|later|ciao|goodnight)\b",
        r"\b(how are you|how\'re you|how do you do|how is it going)\b",
        r"\b(what can you do|help me|who are you|your name)\b",
        r"\b(joke|funny|laugh)\b",
        r"\b(yes|no|ok|okay|sure|alright|nope|nah|yep)\b",
        r"\b(test|ping|check|hello world)\b",
    ],
}

# App name entity patterns
# IMPORTANT: multi-word keys like "youtube music" must appear BEFORE single-word
# keys, and per-key alias lists are checked longest-first so the most specific
# alias always wins (e.g. "youtube music" before "music")
APP_PATTERNS = {
    # ── Specific multi-word apps first (prevents substring aliasing) ──────
    "youtube music":  ["youtube music", "yt music"],
    "google chrome":  ["google chrome"],
    "visual studio code": ["visual studio code", "vs code"],
    "file explorer":  ["file explorer", "file manager", "windows explorer"],
    "task manager":   ["task manager", "taskmgr"],
    "command prompt": ["command prompt"],
    # ── Single-word / short apps ──────────────────────────────────────────
    "chrome":      ["chrome", "browser"],
    "notepad":     ["notepad", "text editor", "note"],
    "calculator":  ["calculator", "calc"],
    "explorer":    ["explorer", "files"],
    "cmd":         ["cmd", "terminal", "powershell"],
    "spotify":     ["spotify"],      # removed 'music' — it stole 'youtube music'
    "vscode":      ["vscode", "code editor"],
    "paint":       ["paint", "mspaint"],
    "wordpad":     ["wordpad"],
}


class NLPModel:
    """
    Lightweight PyTorch-enhanced NLP model for intent classification.
    Uses NumPy-backed TF-IDF vectors + cosine similarity as a fast baseline,
    with room to plug in a full transformer (e.g., DistilBERT) for production.
    """

    def __init__(self):
        self._ready = False
        self._intent_vectors: Dict[IntentType, np.ndarray] = {}
        self.vocab: Dict[str, int] = {}
        self._load_model()

    def _load_model(self):
        """Build vocabulary and intent vectors from pattern keywords."""
        logger.info("AI Agent: Initializing NLP model...")
        start = time.time()

        all_keywords = []
        for pattern_list in INTENT_PATTERNS.values():
            for pattern in pattern_list:
                # Extract plain keyword from regex pattern
                kw = re.sub(r'\\b|[^a-z\s]', '', pattern).strip()
                if kw:
                    all_keywords.append(kw)

        # Build vocab
        unique_words = sorted(set(" ".join(all_keywords).split()))
        self.vocab = {w: i for i, w in enumerate(unique_words)}
        vocab_size = len(self.vocab)

        # Build per-intent vectors
        for intent, patterns in INTENT_PATTERNS.items():
            vec = np.zeros(vocab_size)
            for pattern in patterns:
                kw = re.sub(r'\\b|[^a-z\s]', '', pattern).strip()
                for word in kw.split():
                    if word in self.vocab:
                        vec[self.vocab[word]] += 1.0
            norm = np.linalg.norm(vec)
            self._intent_vectors[intent] = vec / norm if norm > 0 else vec

        self._ready = True
        elapsed = time.time() - start
        logger.info(f"AI Agent: NLP model ready in {elapsed:.3f}s | vocab_size={vocab_size}")

    def _vectorize(self, text: str) -> np.ndarray:
        """Convert input text into a vocabulary-aligned TF vector."""
        vec = np.zeros(len(self.vocab))
        for word in text.lower().split():
            if word in self.vocab:
                vec[self.vocab[word]] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def _extract_entities(self, text: str, intent: IntentType) -> Dict[str, Any]:
        """
        Extract named entities — app names, queries, expressions.
        For OPEN_APP / CLOSE_APP, captures ANY app name after the trigger verb
        (not limited to hardcoded list) so App Discovery can fuzzy-match it.
        """
        entities: Dict[str, Any] = {}
        text_lower = text.lower().strip()

        if intent in (IntentType.OPEN_APP, IntentType.CLOSE_APP):
            # Build a flat (alias, app_key) list sorted LONGEST alias first.
            # This ensures "youtube music" is matched before "music",
            # preventing Spotify from stealing YouTube Music commands.
            all_aliases: list[tuple[str, str]] = []
            for app_key, aliases in APP_PATTERNS.items():
                for alias in aliases:
                    all_aliases.append((alias, app_key))
            all_aliases.sort(key=lambda x: -len(x[0]))  # longest first

            for alias, app_key in all_aliases:
                if alias in text_lower:
                    entities["app"] = app_key
                    break

            # If no hardcoded match, extract whatever follows the trigger verb.
            if "app" not in entities:
                match = re.search(
                    r'\b(?:open|launch|start|run|execute|load|close|kill|quit|exit|terminate)\b'
                    r'\s+(?:up\s+|the\s+|my\s+)?(.+)',
                    text_lower,
                )
                if match:
                    raw_app = match.group(1).strip()
                    raw_app = re.sub(r'\s+(for me|please|now|app|application)$', '', raw_app).strip()
                    if raw_app:
                        entities["app"] = raw_app

        if intent == IntentType.SEARCH_WEB:
            match = re.search(
                r'(?:search|google|look up|find|browse)\s+(?:for\s+)?(.+)',
                text_lower,
            )
            if match:
                entities["query"] = match.group(1).strip()
            else:
                cleaned = re.sub(r'\b(?:search|google|look up|find|browse)\b', '', text_lower).strip()
                if cleaned:
                    entities["query"] = cleaned

        if intent == IntentType.CALCULATE:
            match = re.search(r'(\d+\s*[\+\-\*\/]\s*\d+(?:\s*[\+\-\*\/]\s*\d+)*)', text)
            if match:
                entities["expression"] = match.group(1).strip()

        if intent == IntentType.VOLUME_CONTROL:
            # Direction
            if re.search(r'\b(up|increase|raise|higher|louder|more)\b', text_lower):
                entities["direction"] = "up"
            elif re.search(r'\b(down|decrease|lower|quieter|less|reduce)\b', text_lower):
                entities["direction"] = "down"
            elif re.search(r'\b(mute|silent|silence|quiet)\b', text_lower):
                entities["direction"] = "mute"
            elif re.search(r'\bunmute\b', text_lower):
                entities["direction"] = "unmute"
            # Amount / level
            amt = re.search(r'(\d+)\s*(?:percent|%|steps?|levels?)?', text_lower)
            if amt:
                val = int(amt.group(1))
                if val <= 100:   # treat as % target
                    entities["amount"] = str(max(1, val // 2))  # convert % to keypresses

        if intent == IntentType.BRIGHTNESS_CONTROL:
            if re.search(r'\b(up|increase|raise|higher|brighter|more)\b', text_lower):
                entities["direction"] = "up"
            elif re.search(r'\b(down|decrease|lower|dim|dimmer|less|reduce)\b', text_lower):
                entities["direction"] = "down"
            lvl = re.search(r'(\d+)\s*(?:percent|%)?', text_lower)
            if lvl:
                entities["level"] = lvl.group(1)
        if intent == IntentType.KEYBOARD_CONTROL:
            txt = text_lower

            # ── Extract target app if given: "type hello in notepad",
            # "select all in chrome", "undo on word", "paste in discord" ────────
            # Pattern: ... in <app> / on <app> / for <app> / on <app> window
            app_match = re.search(
                r'\b(?:in|on|for|inside|within|on the)\s+([a-z][a-z0-9 _-]{1,30}?)'
                r'(?:\s+(?:app|window|tab|browser))?\s*$',
                txt, re.IGNORECASE
            )
            if app_match:
                target_app = app_match.group(1).strip()
                # Filter out generic words that aren't app names
                _NOT_APPS = {"page", "tab", "bar", "window", "screen", "this", "the",
                             "me", "it", "here", "browser", "all", "that"}
                if target_app not in _NOT_APPS and len(target_app) > 1:
                    entities["target_app"] = target_app
                    # Remove the 'in <app>' phrase from txt so type/find won't pick it up
                    txt = txt[:app_match.start()].strip()

            # Extract text to type: "type hello world" or "write hello world" ──
            type_match = re.search(
                r'\b(?:type|write|type out|type in)\s+["\']?(.+?)["\']?$',
                txt, re.IGNORECASE
            )
            if type_match:
                entities["action"] = "type"
                entities["text"]   = type_match.group(1).strip()
            # Find on page: "find X" / "search for X on page"
            elif re.search(r'\bfind\b|\bsearch on page\b|\bsearch this page\b|\bfind on page\b|\bfind in\b', txt):
                entities["action"] = "find"
                q = re.search(r'(?:find|search)\s+(?:for\s+)?(?:on page\s+)?["\']?(.+?)["\']?$', txt)
                if q:
                    entities["text"] = q.group(1).strip()
            # Tab management
            elif re.search(r'\bnew tab\b', txt):          entities["action"] = "new_tab"
            elif re.search(r'\bclose tab\b', txt):        entities["action"] = "close_tab"
            elif re.search(r'\bnext tab\b', txt):         entities["action"] = "next_tab"
            elif re.search(r'\bprevious tab\b|\bprev tab\b', txt): entities["action"] = "prev_tab"
            elif re.search(r'\bswitch tab\b', txt):       entities["action"] = "next_tab"
            # Editing shortcuts
            elif re.search(r'\bundo\b', txt):             entities["action"] = "undo"
            elif re.search(r'\bredo\b', txt):             entities["action"] = "redo"
            elif re.search(r'\bcopy\b', txt):             entities["action"] = "copy"
            elif re.search(r'\bpaste\b', txt):            entities["action"] = "paste"
            elif re.search(r'\bcut\b', txt):              entities["action"] = "cut"
            elif re.search(r'\bselect all\b', txt):       entities["action"] = "select_all"
            elif re.search(r'\bdelete\b|\bbackspace\b', txt): entities["action"] = "backspace"
            # Navigation
            elif re.search(r'\bscroll up\b', txt):        entities["action"] = "scroll_up"
            elif re.search(r'\bscroll down\b', txt):      entities["action"] = "scroll_down"
            elif re.search(r'\bscroll top\b|\bscroll to top\b', txt): entities["action"] = "scroll_top"
            elif re.search(r'\bscroll bottom\b|\bscroll to bottom\b', txt): entities["action"] = "scroll_bottom"
            elif re.search(r'\bgo back\b', txt):          entities["action"] = "back"
            elif re.search(r'\bgo forward\b', txt):       entities["action"] = "forward"
            elif re.search(r'\brefresh\b|\breload\b', txt): entities["action"] = "refresh"
            elif re.search(r'\bfull.?screen\b', txt):     entities["action"] = "fullscreen"
            elif re.search(r'\bzoom in\b', txt):          entities["action"] = "zoom_in"
            elif re.search(r'\bzoom out\b', txt):         entities["action"] = "zoom_out"
            elif re.search(r'\bsave\b', txt):             entities["action"] = "save"
            elif re.search(r'\bpress enter\b|\bhit enter\b', txt): entities["action"] = "enter"
            elif re.search(r'\bpress escape\b|\bescape\b', txt): entities["action"] = "escape"
            elif re.search(r'\bprint\b', txt):            entities["action"] = "print"
            elif re.search(r'\bnew window\b', txt):       entities["action"] = "new_window"

        return entities

    def _rule_based_boost(self, text: str) -> Dict[IntentType, float]:
        """Apply regex pattern matching to generate confidence boosts."""
        scores: Dict[IntentType, float] = {intent: 0.0 for intent in IntentType}
        text_lower = text.lower()
        for intent, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    scores[intent] += 0.3

        # ── Critical overrides ─────────────────────────────────────────────
        # Explicit open/launch → always OPEN_APP
        OPEN_VERBS = r'\b(open|launch|start|run|execute|load)\b'
        if re.search(OPEN_VERBS, text_lower):
            scores[IntentType.OPEN_APP] += 1.5
            scores[IntentType.PLAY_MEDIA] -= 0.5
            scores[IntentType.SEARCH_WEB] -= 0.3

        CLOSE_VERBS = r'\b(close|kill|quit|exit|terminate)\b'
        if re.search(CLOSE_VERBS, text_lower):
            scores[IntentType.CLOSE_APP] += 1.5

        # Volume keywords → always VOLUME_CONTROL (not SYSTEM_INFO)
        VOLUME_KW = r'\b(volume|mute|unmute|louder|quieter|sound level)\b'
        if re.search(VOLUME_KW, text_lower):
            scores[IntentType.VOLUME_CONTROL] += 2.0
            scores[IntentType.SYSTEM_INFO] -= 0.5
            scores[IntentType.GENERAL_QUERY] -= 0.3

        # Brightness keywords → always BRIGHTNESS_CONTROL
        BRIGHT_KW = r'\b(brightness|dim|dimmer|brighter|screen light)\b'
        if re.search(BRIGHT_KW, text_lower):
            scores[IntentType.BRIGHTNESS_CONTROL] += 2.0
            scores[IntentType.SYSTEM_INFO] -= 0.5

        # Greetings / small-talk → always GENERAL_QUERY (never UNKNOWN)
        GREETING_KW = (
            r'\b(hi|hello|hey|howdy|greetings|yo|sup|'  
            r'good\s*(morning|evening|afternoon|night)|'  
            r'how are you|how\'?re you|how do you do|how is it going|'  
            r'thanks|thank you|thank u|ty|cheers|appreciate|'  
            r'bye|goodbye|see you|later|goodnight|ciao|'  
            r'what can you do|help me|who are you|your name|'  
            r'joke|funny|tell me a joke|are you real|are you an ai|'  
            r'what\'?s up|nice|great|awesome|you\'?re (great|amazing|cool|smart)'  
            r')\b'
        )
        if re.search(GREETING_KW, text_lower, re.IGNORECASE):
            scores[IntentType.GENERAL_QUERY] += 2.0
            scores[IntentType.UNKNOWN] -= 1.0
        # Keyboard control keywords — strong boost, do not confuse with OPEN_APP or GENERAL_QUERY
        KB_KW = (
            r'\b(type|write|undo|redo|copy|paste|cut|select all|backspace|delete text|'
            r'new tab|close tab|next tab|previous tab|switch tab|'
            r'find on page|search on page|search this page|find in|'
            r'scroll up|scroll down|scroll top|scroll bottom|'
            r'go back|go forward|refresh|reload|fullscreen|full screen|'
            r'zoom in|zoom out|save file|press enter|hit enter|press escape|'
            r'print page|new window)\b'
        )
        if re.search(KB_KW, text_lower, re.IGNORECASE):
            scores[IntentType.KEYBOARD_CONTROL] += 2.5
            scores[IntentType.OPEN_APP]         -= 0.5
            scores[IntentType.SEARCH_WEB]       -= 0.5
            scores[IntentType.GENERAL_QUERY]    -= 0.3

        # "type X" — very strong specifically
        if re.search(r'^(type|write)\s+.+', text_lower):
            scores[IntentType.KEYBOARD_CONTROL] += 3.0

        return scores

    def predict(self, text: str) -> NLPResult:
        """
        Main inference method: combines vector similarity + rule boosts.
        Returns structured NLPResult.
        """
        if not self._ready:
            raise RuntimeError("NLP model not initialized")

        query_vec = self._vectorize(text)
        rule_boosts = self._rule_based_boost(text)

        # Cosine similarity scores
        scores: Dict[IntentType, float] = {}
        for intent, intent_vec in self._intent_vectors.items():
            cosine_sim = float(np.dot(query_vec, intent_vec))
            scores[intent] = cosine_sim + rule_boosts.get(intent, 0.0)

        # Remove UNKNOWN from competition initially
        scores.pop(IntentType.UNKNOWN, None)

        best_intent = max(scores, key=lambda k: scores[k])
        best_score = scores[best_intent]

        # Fallback to UNKNOWN if confidence is too low
        if best_score < 0.1:
            best_intent = IntentType.UNKNOWN
            confidence = 0.05
        else:
            # Normalize to [0, 1] using softmax-like scaling
            total = sum(max(s, 0) for s in scores.values()) or 1.0
            confidence = min(scores[best_intent] / total, 0.99)

        entities = self._extract_entities(text, best_intent)

        logger.info(
            f"AI Agent: '{text}' → intent={best_intent} "
            f"confidence={confidence:.3f} entities={entities}"
        )

        return NLPResult(
            intent=best_intent,
            confidence=round(confidence, 4),
            entities=entities,
            raw_text=text,
        )


# Singleton instance
_model_instance: NLPModel | None = None


def get_nlp_model() -> NLPModel:
    global _model_instance
    if _model_instance is None:
        _model_instance = NLPModel()
    return _model_instance
