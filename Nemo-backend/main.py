"""
Jarvis Backend — Main FastAPI Application (Backend Agent)
Orchestrates all agents and exposes REST endpoints.
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import commands, health
from routers.apps import router as apps_router
from agents.ai_agent import get_ai_agent
from agents.conversation_agent import get_conversation_agent
from agents.app_discovery import get_app_discovery
from agents.language_agent import get_language_agent
from agents.debug_agent import get_debug_agent, AgentStatus

logger = logging.getLogger("backend_agent")


def _load_env():
    """Load .env file manually (avoids requiring python-dotenv)."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())
        logger.info(f"Loaded environment from {env_path}")
    else:
        logger.info("No .env file found — using system environment variables.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm all agents on startup."""
    _load_env()
    logger.info("🤖 Jarvis Backend starting up...")
    debug = get_debug_agent()
    debug.set_agent_status("Backend Agent", AgentStatus.PROCESSING)

    # Initialize agents
    get_ai_agent()
    get_language_agent()  # Initialize language detection
    conv = get_conversation_agent()

    # Pre-warm App Discovery in background (avoids slow first open-app command)
    import threading
    threading.Thread(target=get_app_discovery, daemon=True).start()

    debug.set_agent_status("AI Agent", AgentStatus.IDLE, 0)
    debug.set_agent_status("Automation Agent", AgentStatus.IDLE, 0)
    debug.set_agent_status("Backend Agent", AgentStatus.IDLE, 0)
    debug.set_agent_status("Debug Agent", AgentStatus.IDLE, 0)
    debug.set_agent_status("UI Agent", AgentStatus.IDLE, 0)

    mode = "OpenRouter LLM" if conv._has_api_key else "Rule-based fallback"
    logger.info(f"✅ All agents initialized — Conversation mode: {mode}")
    logger.info("🚀 Jarvis is ready!")
    yield
    logger.info("🛑 Jarvis Backend shutting down...")


app = FastAPI(
    title="Jarvis Multi-Agent API",
    description=(
        "A five-agent AI-powered personal assistant system. "
        "Agents: AI (NLP), UI (React), Automation, Backend (FastAPI), Debug & Dev.\n\n"
        "**Conversation Agent** powered by OpenRouter (Gemini 2.5 Pro) gives Jarvis "
        "a real JARVIS personality with session memory."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow React dev server + production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(commands.router)
app.include_router(health.router)
app.include_router(apps_router)


@app.get("/", tags=["Root"])
async def root():
    conv = get_conversation_agent()
    return {
        "name": "Jarvis Multi-Agent System",
        "version": "2.1.0",
        "agents": ["Language Agent", "AI Agent", "UI Agent", "Automation Agent",
                   "Conversation Agent", "Backend Agent", "Debug Agent"],
        "conversation_mode": "OpenRouter LLM" if conv._has_api_key else "Rule-based fallback",
        "supported_languages": ["English", "हिंदी (Hindi)", "मराठी (Marathi)"],
        "docs": "/docs",
    }
