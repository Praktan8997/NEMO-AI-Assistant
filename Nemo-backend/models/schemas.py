"""
Pydantic schemas for the Jarvis API — Backend Agent
Defines all request/response models for robust API validation.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class IntentType(str, Enum):
    OPEN_APP           = "open_app"
    CLOSE_APP          = "close_app"
    SEARCH_WEB         = "search_web"
    SYSTEM_INFO        = "system_info"
    PLAY_MEDIA         = "play_media"
    SET_REMINDER       = "set_reminder"
    SEND_MESSAGE       = "send_message"
    WEATHER            = "weather"
    CALCULATE          = "calculate"
    VOLUME_CONTROL     = "volume_control"
    BRIGHTNESS_CONTROL = "brightness_control"
    KEYBOARD_CONTROL   = "keyboard_control"
    GENERAL_QUERY      = "general_query"
    UNKNOWN            = "unknown"


class AgentStatus(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"


# --- Request Models ---

class CommandRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500, description="Raw command from user")
    session_id: Optional[str] = Field(default="default", description="Session identifier")
    source: Optional[str] = Field(default="text", description="Input source: text | voice")
    language: Optional[str] = Field(default=None, description="Language hint from frontend: en | hi | mr (auto-detected if not set)")

    model_config = {"json_schema_extra": {"example": {"text": "Chrome खोलो", "session_id": "user_1", "source": "voice", "language": "hi"}}}


# --- Response Models ---

class NLPResult(BaseModel):
    intent: IntentType
    confidence: float = Field(..., ge=0.0, le=1.0)
    entities: Dict[str, Any] = Field(default_factory=dict)
    raw_text: str


class AutomationResult(BaseModel):
    success: bool
    action_taken: str
    output: Optional[str] = None
    error: Optional[str] = None


class AgentInfo(BaseModel):
    name: str
    status: AgentStatus
    last_active: Optional[datetime] = None
    tasks_completed: int = 0


class CommandResponse(BaseModel):
    command_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_input: str
    nlp_result: NLPResult
    automation_result: AutomationResult
    response_text: str
    agents_involved: List[str] = Field(default_factory=list)
    language: str = Field(default="en", description="Detected language code: en | hi | mr")


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agents: List[AgentInfo]
    system_uptime: float
    total_commands_processed: int


class CommandHistoryItem(BaseModel):
    command_id: str
    timestamp: datetime
    user_input: str
    intent: str
    success: bool
    response_text: str


class CommandHistoryResponse(BaseModel):
    items: List[CommandHistoryItem]
    total: int
