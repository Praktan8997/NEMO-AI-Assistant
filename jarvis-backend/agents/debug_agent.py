"""
Debug & Dev Agent — Logging, metrics, and health monitoring
Tracks all command executions, agent statuses, and system uptime.
"""
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from collections import deque
from models.schemas import (
    AgentInfo, AgentStatus, CommandHistoryItem, HealthResponse
)

logger = logging.getLogger("debug_agent")

# Configure structured logging for the whole system
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class DebugAgent:
    """
    Monitors all agent activity, stores command history,
    and exposes health/metrics endpoints.
    """

    MAX_HISTORY = 200

    def __init__(self):
        self._start_time = time.time()
        self._command_history: deque[CommandHistoryItem] = deque(maxlen=self.MAX_HISTORY)
        self._total_commands = 0
        self._agent_registry: dict[str, AgentInfo] = {}
        self._register_agents()
        logger.info("Debug Agent: Initialized — monitoring all agents")

    def _register_agents(self):
        for name in ["AI Agent", "UI Agent", "Automation Agent", "Backend Agent", "Debug Agent"]:
            self._agent_registry[name] = AgentInfo(
                name=name,
                status=AgentStatus.IDLE,
                tasks_completed=0,
            )

    def record_command(
        self,
        command_id: str,
        user_input: str,
        intent: str,
        success: bool,
        response_text: str,
    ):
        """Log a completed command to the history store."""
        item = CommandHistoryItem(
            command_id=command_id,
            timestamp=datetime.now(timezone.utc),
            user_input=user_input,
            intent=intent,
            success=success,
            response_text=response_text,
        )
        self._command_history.appendleft(item)
        self._total_commands += 1
        status = "✅" if success else "❌"
        logger.info(f"Debug Agent: {status} [{intent}] '{user_input[:60]}...' → {response_text[:80]}")

    def set_agent_status(self, agent_name: str, status: AgentStatus, tasks: Optional[int] = None):
        if agent_name in self._agent_registry:
            self._agent_registry[agent_name].status = status
            self._agent_registry[agent_name].last_active = datetime.now(timezone.utc)
            if tasks is not None:
                self._agent_registry[agent_name].tasks_completed = tasks

    def get_health(self) -> HealthResponse:
        uptime = time.time() - self._start_time
        return HealthResponse(
            status="healthy",
            agents=list(self._agent_registry.values()),
            system_uptime=round(uptime, 2),
            total_commands_processed=self._total_commands,
        )

    def get_history(self, limit: int = 50) -> List[CommandHistoryItem]:
        return list(self._command_history)[:limit]

    def generate_command_id(self) -> str:
        return f"cmd_{uuid.uuid4().hex[:8]}"


# Singleton
_debug_instance: Optional[DebugAgent] = None


def get_debug_agent() -> DebugAgent:
    global _debug_instance
    if _debug_instance is None:
        _debug_instance = DebugAgent()
    return _debug_instance
