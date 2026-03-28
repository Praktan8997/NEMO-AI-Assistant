"""
Health Router — /api/health and agent status endpoints
"""
from fastapi import APIRouter
from agents.debug_agent import get_debug_agent
from models.schemas import HealthResponse, CommandHistoryResponse

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Returns system health, all agent statuses, and uptime."""
    return get_debug_agent().get_health()


@router.get("/history", response_model=CommandHistoryResponse)
async def command_history(limit: int = 50):
    """Returns the last N processed commands."""
    debug = get_debug_agent()
    items = debug.get_history(limit=limit)
    return CommandHistoryResponse(items=items, total=len(items))
