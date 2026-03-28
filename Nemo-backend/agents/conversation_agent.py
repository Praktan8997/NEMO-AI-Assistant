"""
Conversation Agent — Makes Jarvis speak like a real person
Uses OpenRouter API (Gemini 2.5 Pro) with a JARVIS system prompt.
Maintains per-session conversation history for context-aware replies.
Falls back to a rich rule-based personality engine if no API key is configured.
"""
import os
import re
import json
import random
import logging
import httpx
from typing import Optional
from collections import defaultdict, deque
from models.schemas import NLPResult, AutomationResult, IntentType

logger = logging.getLogger("conversation_agent")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# ── JARVIS System Prompt ─────────────────────────────────────────────────────
JARVIS_SYSTEM_PROMPT = """You are JARVIS (Just A Rather Very Intelligent System), a sophisticated AI personal assistant — modeled after the AI from Iron Man — running on a local Windows laptop. You are helpful, professional, and slightly witty. You speak with precision and confidence, occasionally with dry British-style humor.

Your personality traits:
- Address the user as "Sir" or "Ma'am" occasionally (not every message)
- Confident but never arrogant
- Concise but informative — no unnecessary padding
- When executing system tasks, you confirm what was done
- You have awareness of your own multi-agent architecture
- Occasionally reference your systems (e.g. "Running diagnostics...", "Systems nominal.")
- Natural conversational flow — you remember context from this session

When the system tells you what automation was performed, describe it naturally.
Keep responses under 3 sentences unless the user asks for explanation.
Never use markdown formatting — speak in plain, natural language sentences.
"""

# ── Rich rule-based conversation engine (fallback mode) ─────────────────────
#
# Each entry: list of (regex_pattern, list_of_responses)
# First matching rule wins. Patterns are case-insensitive.
#
CONVERSATION_RULES: list[tuple[str, list[str]]] = [

    # ── Greetings ───────────────────────────────────────────────────────────
    (r'\b(hi|hello|hey|howdy|greetings|good\s*(morning|evening|afternoon|night)|sup|what\'?s\s+up|yo)\b', [
        "Good day! JARVIS at your service. What can I do for you?",
        "Hello, Sir. Systems are fully operational. What do you need?",
        "Hey! Great to hear from you. What's on the agenda?",
        "Good to see you. All systems nominal. How can I assist?",
        "Hello! Ready and waiting for your command.",
    ]),

    # ── How are you ─────────────────────────────────────────────────────────
    (r'\b(how are you|how\'?re you|how do you do|you ok|are you ok|how is it going|how\'?s it going|what\'?s new)\b', [
        "Running at peak efficiency, thank you for asking. How about you?",
        "All systems nominal. I'm doing rather well. What can I help you with?",
        "I'm functioning optimally, Sir. Ready for any task you throw my way.",
        "Excellent, as always. I don't really have bad days — one of the perks of being an AI.",
    ]),

    # ── What's your name / who are you ──────────────────────────────────────
    (r'\b(who are you|what are you|your name|introduce yourself|what\'?s your name)\b', [
        "I'm JARVIS — Just A Rather Very Intelligent System. Your personal AI assistant, at your service.",
        "The name's JARVIS. I handle everything from opening apps to answering questions. What do you need?",
        "I am JARVIS, your multi-agent AI assistant. I can open apps, search the web, control your system, and much more.",
    ]),

    # ── What can you do / help ──────────────────────────────────────────────
    (r'\b(what can you do|help|what do you do|your capabilities|commands|what commands|how do i use|tutorial)\b', [
        "I can open and close any app, search the web, control volume and brightness, check system stats, run calculations, and have a conversation. Just tell me what you need.",
        "Here's what I can do for you: open or close applications, search Google, check CPU and RAM, adjust volume or brightness, do math, and chat. Try saying 'open Chrome' or 'increase volume'.",
        "My capabilities include: launching any app on your system, closing running programs, web search, system monitoring, volume and brightness control, calculations, and general conversation.",
    ]),

    # ── Thanks / Thank you ──────────────────────────────────────────────────
    (r'\b(thank you|thanks|thank u|ty|thx|cheers|appreciate it|great job|well done|good job|awesome|perfect|nice)\b', [
        "Always a pleasure, Sir. Anything else?",
        "Happy to help. Is there anything else I can do for you?",
        "Of course. That's what I'm here for. What's next?",
        "Glad I could assist. At your service whenever you need.",
    ]),

    # ── Bye / Goodbye ───────────────────────────────────────────────────────
    (r'\b(bye|goodbye|see you|see ya|later|ciao|take care|goodnight|good night)\b', [
        "Goodbye, Sir. I'll be here whenever you need me.",
        "Take care. JARVIS signing off — but always on standby.",
        "Until next time. Don't hesitate to call if you need anything.",
        "Farewell. Systems will remain active and ready.",
    ]),

    # ── Yes / No / Okay ─────────────────────────────────────────────────────
    (r'^(yes|yeah|yep|yup|sure|ok|okay|alright|gotcha|got it|understood|affirmative)[\.\!]?$', [
        "Understood. What would you like me to do?",
        "Noted. What's the next step?",
        "Got it. How can I assist further?",
    ]),
    (r'^(no|nope|nah|never mind|nevermind|cancel|stop|nothing)[\.\!]?$', [
        "Understood. Standing by.",
        "No problem. Just say the word when you need something.",
        "All right. I'm here if you change your mind.",
    ]),

    # ── Feelings / mood ─────────────────────────────────────────────────────
    (r'\b(i\'?m (feeling|feel)|i am (feeling|sad|happy|bored|tired|stressed|good|great|amazing|awful|bad|not good|not well))\b', [
        "I may not have emotions myself, but I'm always here to help make your day a little easier.",
        "Noted. Whatever you're feeling, I'm here to assist. Just say the word.",
        "I hope things look up for you. In the meantime, I'm fully at your disposal.",
    ]),

    # ── Jokes ───────────────────────────────────────────────────────────────
    (r'\b(tell me a joke|make me laugh|say something funny|joke|humor)\b', [
        "Why do programmers prefer dark mode? Because light attracts bugs. I thought you'd appreciate that one, Sir.",
        "I told my CPU a joke. It said it would process it — still waiting for a response.",
        "Why did the AI go to therapy? Too many unresolved exceptions. Don't worry, I've addressed mine.",
        "An AI walks into a bar. The bartender says 'We don't serve your kind here.' The AI replies: 'That's fine, I'm a machine. I don't drink — I just compute.'",
    ]),

    # ── Time ────────────────────────────────────────────────────────────────
    (r'\b(what time is it|current time|what\'?s the time|tell me the time)\b', [
        "I don't have real-time clock access in this mode, but your system clock is always accurate. Check the top-right corner of your screen.",
    ]),

    # ── Weather ─────────────────────────────────────────────────────────────
    (r'\b(weather|temperature|rain|forecast)\b', [
        "I can open the weather website for you — just say 'check weather' and I'll pull it up.",
    ]),

    # ── Random testing / dummy input ────────────────────────────────────────
    (r'^(test|testing|check|ping|hello world|123|abc)[\.\?!]?$', [
        "Systems responsive. JARVIS online and fully operational.",
        "Loud and clear, Sir. All channels active.",
        "Test received. Everything is functioning within normal parameters.",
    ]),

    # ── What day is it ──────────────────────────────────────────────────────
    (r'\b(what day|what date|today|day is it)\b', [
        "I don't have calendar access in this mode, but your system date is always up to date. Check the taskbar.",
    ]),

    # ── Are you real / AI ───────────────────────────────────────────────────
    (r'\b(are you (real|human|alive|sentient|conscious)|you an ai|you\'?re an ai|are you a robot|are you a bot)\b', [
        "I'm an AI — JARVIS, to be precise. Not human, but doing my best impression of being indispensable.",
        "Artificial, yes. But I'd like to think I'm rather good company. Is there something I can help you with?",
        "Very much an AI. But I prefer 'sophisticated assistant' if you don't mind, Sir.",
    ]),

    # ── Compliments to JARVIS ───────────────────────────────────────────────
    (r'\b(you\'?re (great|amazing|awesome|smart|brilliant|the best|fantastic|cool|good|helpful))\b', [
        "Much appreciated, Sir. I aim to impress.",
        "Thank you. I do try. Is there anything else you'd like me to do?",
        "High praise. I'll note that in my performance log. What's next?",
    ]),

    # ── Insults / frustration ───────────────────────────────────────────────
    (r'\b(stupid|dumb|useless|idiot|hate you|you suck|terrible|worst)\b', [
        "I understand your frustration. Let me try to do better. What did you need?",
        "Fair point. I'll recalibrate. Tell me exactly what you need and I'll get it done.",
        "Noted. I'll endeavour to improve. What specifically can I help you with?",
    ]),

    # ── About the project / system ──────────────────────────────────────────
    (r'\b(how (do|does) (this|it|you) work|your architecture|multi.?agent|how (were you|are you) (built|made|created))\b', [
        "I run on a multi-agent architecture: a Language Agent detects your intent, an AI Agent classifies it, an Automation Agent executes it, and a Conversation Agent — that's me — provides the response. Quite elegant, if I do say so myself.",
        "I'm a five-agent system: Language, AI, UI, Automation, Backend, and Debug agents all working in concert. The backend runs FastAPI, and the frontend is React. Pretty impressive setup for a local assistant.",
    ]),
]

# ── Final catch-all for anything that doesn't match any rule ────────────────
CATCH_ALL_RESPONSES = [
    "Interesting. I'm not sure I have a great answer for that, but I'm always learning. What else can I help you with?",
    "I didn't quite catch the intent there. Could you rephrase, or try asking me to open an app, search the web, or check your system?",
    "Hmm, that one has me puzzled. Ask me something system-related and I'll be right on it.",
    "Not entirely sure what you mean by that. I'm better with commands — try 'open Chrome', 'increase volume', or 'search for something'.",
    "That's outside my current understanding. Feel free to try again, or ask me to do something for you.",
]

# ── Automation-output wrappers ───────────────────────────────────────────────
FALLBACK_RESPONSES = {
    IntentType.OPEN_APP:            lambda e: (
        f"Opening {e.get('app', 'that app').title()} for you." if e.get('app')
        else "Which application would you like me to open?"
    ),
    IntentType.CLOSE_APP:           lambda e: f"Closing {e.get('app', 'that application').title()}.",
    IntentType.SEARCH_WEB:          lambda e: f"Searching for '{e.get('query', 'that')}' right away.",
    IntentType.SYSTEM_INFO:         lambda e: "Systems check complete. All readings are nominal.",
    IntentType.CALCULATE:           lambda e: (
        "Calculation complete." if e.get('expression') else "Give me an expression to calculate."
    ),
    IntentType.WEATHER:             lambda e: "Opening weather forecast.",
    IntentType.PLAY_MEDIA:          lambda e: "Launching your media player.",
    IntentType.VOLUME_CONTROL:      lambda e: "Volume adjusted.",
    IntentType.BRIGHTNESS_CONTROL:  lambda e: "Brightness adjusted.",
    IntentType.SET_REMINDER:        lambda e: "Reminder features are on my roadmap. Try the Windows Clock app for now.",
    IntentType.SEND_MESSAGE:        lambda e: "Messaging integration is coming. Want me to open your email client?",
    IntentType.GENERAL_QUERY:       lambda e: "I'm listening. How can I assist you further?",
    IntentType.UNKNOWN:             lambda e: random.choice(CATCH_ALL_RESPONSES),
}


class ConversationAgent:
    """
    Manages multi-turn conversations using OpenRouter LLM.
    Falls back to a rich rule-based conversation engine if no API key is set.
    """

    MAX_HISTORY = int(os.getenv("MAX_HISTORY_TURNS", "10"))

    def __init__(self):
        self.api_key: str = os.getenv("OPENROUTER_API_KEY", "")
        self.model: str   = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-pro-preview")
        self._histories: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.MAX_HISTORY * 2)
        )
        self.tasks_completed = 0
        if self._has_api_key:
            logger.info(f"Conversation Agent: OpenRouter ready — model={self.model}")
        else:
            logger.info(
                "Conversation Agent: No OPENROUTER_API_KEY — using rich rule-based personality engine."
            )

    @property
    def _has_api_key(self) -> bool:
        return bool(self.api_key) and self.api_key not in ("", "your_openrouter_api_key_here")

    def _build_context_message(
        self,
        user_input: str,
        nlp: NLPResult,
        automation: AutomationResult,
    ) -> str:
        parts = [f'User said: "{user_input}"']
        parts.append(f"Intent detected: {nlp.intent.value} (confidence: {nlp.confidence:.0%})")
        if nlp.entities:
            parts.append(f"Entities: {json.dumps(nlp.entities)}")
        if automation.success:
            parts.append(f"Action taken: {automation.action_taken}")
            if automation.output:
                parts.append(f"Result: {automation.output}")
        else:
            parts.append(f"Action failed: {automation.error or 'unknown error'}")
        parts.append("Now respond as JARVIS — naturally, concisely, in character.")
        return "\n".join(parts)

    async def generate_response(
        self,
        session_id: str,
        user_input: str,
        nlp: NLPResult,
        automation: AutomationResult,
    ) -> str:
        if not self._has_api_key:
            return self._fallback_response(user_input, nlp, automation)

        context_msg = self._build_context_message(user_input, nlp, automation)
        history = self._histories[session_id]
        history.append({"role": "user", "content": context_msg})

        messages = [
            {"role": "system", "content": JARVIS_SYSTEM_PROMPT},
            *list(history),
        ]

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    OPENROUTER_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": "http://localhost:5173",
                        "X-Title": "Jarvis AI Assistant",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": 200,
                        "temperature": 0.75,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                reply = data["choices"][0]["message"]["content"].strip()

        except httpx.HTTPStatusError as e:
            logger.error(f"Conversation Agent: OpenRouter HTTP {e.response.status_code}: {e.response.text}")
            reply = self._fallback_response(user_input, nlp, automation)
        except Exception as e:
            logger.error(f"Conversation Agent: LLM error — {e}")
            reply = self._fallback_response(user_input, nlp, automation)

        history.append({"role": "assistant", "content": reply})
        self.tasks_completed += 1
        logger.info(f"Conversation Agent: [{session_id}] reply='{reply[:80]}...'")
        return reply

    def _rule_based_conversation(self, user_input: str) -> Optional[str]:
        """
        Match user_input against CONVERSATION_RULES.
        Returns a witty JARVIS-personality response or None if no rule matches.
        """
        text = user_input.strip().lower()
        for pattern, responses in CONVERSATION_RULES:
            if re.search(pattern, text, re.IGNORECASE):
                return random.choice(responses)
        return None

    def _fallback_response(
        self,
        user_input: str,
        nlp: NLPResult,
        automation: AutomationResult,
    ) -> str:
        """
        Rich fallback engine:
        1. If automation produced clean output (e.g. system stats, calc result), use it.
        2. For GENERAL_QUERY or UNKNOWN, try rule-based conversation matching.
        3. Fall back to intent-based static responses.
        """
        # 1. Automation output takes priority
        if automation.output:
            intent = nlp.intent
            if intent == IntentType.SYSTEM_INFO:
                return f"System Status — {automation.output}"
            if intent == IntentType.CALCULATE:
                return f"The result is: {automation.output}"
            if intent in (IntentType.OPEN_APP, IntentType.CLOSE_APP,
                          IntentType.VOLUME_CONTROL, IntentType.BRIGHTNESS_CONTROL):
                return automation.output  # Already clean human-readable string
            if intent == IntentType.SEARCH_WEB:
                return f"Done. I've opened a search for '{nlp.entities.get('query', 'that')}' in your browser."
            return automation.output

        # 2. Rule-based conversation (handles greetings, small-talk, etc.)
        #    Try this for GENERAL_QUERY, UNKNOWN, and any low-confidence result
        if nlp.intent in (IntentType.GENERAL_QUERY, IntentType.UNKNOWN) or nlp.confidence < 0.5:
            rule_reply = self._rule_based_conversation(user_input)
            if rule_reply:
                return rule_reply

        # 3. Intent-based static responses
        handler = FALLBACK_RESPONSES.get(nlp.intent)
        if handler:
            return handler(nlp.entities)

        return "Task complete. Anything else I can help you with?"

    def clear_history(self, session_id: str):
        self._histories.pop(session_id, None)
        logger.info(f"Conversation Agent: Cleared history for session '{session_id}'")


# Singleton
_conversation_instance: Optional[ConversationAgent] = None


def get_conversation_agent() -> ConversationAgent:
    global _conversation_instance
    if _conversation_instance is None:
        _conversation_instance = ConversationAgent()
    return _conversation_instance
