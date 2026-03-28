"""
Commands Router — handles /api/commands/* endpoints
Integrates: Language Agent → AI Agent → Automation Agent → Conversation Agent → Debug Agent
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from models.schemas import CommandRequest, CommandResponse, NLPResult, AutomationResult, AgentStatus
from agents.ai_agent import get_ai_agent
from agents.automation_agent import get_automation_agent
from agents.conversation_agent import get_conversation_agent
from agents.language_agent import get_language_agent, LANG_EN
from agents.debug_agent import get_debug_agent
from datetime import datetime, timezone
import logging

router = APIRouter(prefix="/api/commands", tags=["Commands"])
logger = logging.getLogger("backend_agent.commands")


# ── Chat-only request (no automation) ────────────────────────────────────────

class ChatRequest(BaseModel):
    text: str
    session_id: str = "default"
    language: str = "en"


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    language: str
    timestamp: datetime


# ── Full command pipeline ─────────────────────────────────────────────────────

@router.post("/", response_model=CommandResponse)
async def process_command(request: CommandRequest):
    """
    Main pipeline:
      1. Language Agent   — detect language, extract native-language intent hint
      2. AI Agent         — NLP intent classification (with language hint)
      3. Automation       — execute system action
      4. Language Agent   — generate localized response (hi/mr) OR
         Conversation     — generate English JARVIS reply
      5. Debug            — log everything
    """
    debug        = get_debug_agent()
    ai           = get_ai_agent()
    automation   = get_automation_agent()
    conversation = get_conversation_agent()
    lang_agent   = get_language_agent()

    command_id = debug.generate_command_id()
    logger.info(f"Backend Agent: Processing '{request.text[:60]}' [{command_id}]")

    # ── Step 1: Language Detection ────────────────────────────────────────
    # Use frontend hint if provided, otherwise auto-detect
    detected_lang = request.language or lang_agent.detect_language(request.text)
    lang_intent, lang_entities, english_hint = lang_agent.extract_intent_and_entities(
        request.text, detected_lang
    )
    logger.info(f"Language Agent: lang={detected_lang} hint_intent={lang_intent}")

    # ── Step 2: AI Agent ──────────────────────────────────────────────────
    debug.set_agent_status("AI Agent", AgentStatus.PROCESSING)
    try:
        # Use the English hint text for NLP if we extracted one
        nlp_input = english_hint if detected_lang != LANG_EN else request.text
        nlp_result = ai.recognize(nlp_input)

        # If Language Agent extracted entities, merge them (overrides NLP if richer)
        if lang_entities:
            nlp_result.entities.update(lang_entities)

        # If Language Agent detected a confident intent, trust it (NLP on hint may differ)
        if lang_intent is not None and detected_lang != LANG_EN:
            nlp_result.intent = lang_intent

        debug.set_agent_status("AI Agent", AgentStatus.SUCCESS, ai.tasks_completed)
    except Exception as e:
        debug.set_agent_status("AI Agent", AgentStatus.ERROR)
        raise HTTPException(status_code=500, detail=f"AI Agent error: {e}")

    # ── Step 3: Automation Agent ──────────────────────────────────────────
    debug.set_agent_status("Automation Agent", AgentStatus.PROCESSING)
    automation_result = automation.execute(nlp_result)
    debug.set_agent_status(
        "Automation Agent",
        AgentStatus.SUCCESS if automation_result.success else AgentStatus.ERROR,
        automation.tasks_completed,
    )

    # ── Step 4: Response generation ───────────────────────────────────────
    debug.set_agent_status("Backend Agent", AgentStatus.PROCESSING)

    # For Hindi/Marathi: generate localized response directly
    if detected_lang != LANG_EN:
        response_text = lang_agent.localized_response(
            lang=detected_lang,
            intent=nlp_result.intent,
            entities=nlp_result.entities,
            automation_output=automation_result.output,
            success=automation_result.success,
        )
        # Fallback: if localization returned None (shouldn't), use English
        if not response_text:
            response_text = await conversation.generate_response(
                session_id=request.session_id or "default",
                user_input=request.text,
                nlp=nlp_result,
                automation=automation_result,
            )
    else:
        # English: use Conversation Agent (LLM or fallback)
        response_text = await conversation.generate_response(
            session_id=request.session_id or "default",
            user_input=request.text,
            nlp=nlp_result,
            automation=automation_result,
        )

    # ── Step 5: Debug Agent ───────────────────────────────────────────────
    debug.record_command(
        command_id=command_id,
        user_input=request.text,
        intent=nlp_result.intent.value,
        success=automation_result.success,
        response_text=response_text,
    )
    debug.set_agent_status("Backend Agent", AgentStatus.SUCCESS)

    return CommandResponse(
        command_id=command_id,
        timestamp=datetime.now(timezone.utc),
        user_input=request.text,
        nlp_result=nlp_result,
        automation_result=automation_result,
        response_text=response_text,
        agents_involved=["Language Agent", "AI Agent", "Automation Agent",
                         "Conversation Agent", "Backend Agent"],
        language=detected_lang,
    )


# ── Pure chat endpoint ────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """Pure conversational endpoint — no automation, just JARVIS talking."""
    debug        = get_debug_agent()
    ai           = get_ai_agent()
    conversation = get_conversation_agent()
    lang_agent   = get_language_agent()

    detected_lang = request.language or lang_agent.detect_language(request.text)
    _, lang_entities, english_hint = lang_agent.extract_intent_and_entities(request.text, detected_lang)

    nlp_result = ai.recognize(english_hint if detected_lang != LANG_EN else request.text)
    if lang_entities:
        nlp_result.entities.update(lang_entities)

    dummy_automation = AutomationResult(success=True, action_taken="chat", output=None)

    if detected_lang != LANG_EN:
        reply = lang_agent.localized_response(
            lang=detected_lang,
            intent=nlp_result.intent,
            entities=nlp_result.entities,
            automation_output=None,
            success=True,
        ) or "I'm here to help."
    else:
        reply = await conversation.generate_response(
            session_id=request.session_id,
            user_input=request.text,
            nlp=nlp_result,
            automation=dummy_automation,
        )

    debug.record_command(
        command_id=debug.generate_command_id(),
        user_input=request.text,
        intent=nlp_result.intent.value,
        success=True,
        response_text=reply,
    )

    return ChatResponse(
        reply=reply,
        session_id=request.session_id,
        language=detected_lang,
        timestamp=datetime.now(timezone.utc),
    )


# ── Clear session / language info endpoints ───────────────────────────────────

@router.delete("/session/{session_id}", tags=["Chat"])
async def clear_session(session_id: str):
    """Clear conversation history for a given session."""
    get_conversation_agent().clear_history(session_id)
    return {"message": f"Session '{session_id}' history cleared.", "session_id": session_id}


@router.get("/languages", tags=["Languages"])
async def get_supported_languages():
    """Return list of supported languages."""
    return {
        "languages": [
            {"code": "en", "name": "English",    "voice_code": "en-US", "flag": "🇺🇸"},
            {"code": "hi", "name": "हिंदी",       "voice_code": "hi-IN", "flag": "🇮🇳"},
            {"code": "mr", "name": "मराठी",       "voice_code": "mr-IN", "flag": "🇮🇳"},
        ]
    }
