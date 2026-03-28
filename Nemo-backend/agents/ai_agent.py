"""
AI Agent wrapper — exposes the NLP model as an agent with status tracking.
"""
import time
import logging
from models.nlp_model import get_nlp_model, NLPModel
from models.schemas import NLPResult

logger = logging.getLogger("ai_agent")


class AIAgent:
    def __init__(self):
        self.tasks_completed = 0
        self.last_active: float | None = None
        self._model: NLPModel = get_nlp_model()
        logger.info("AI Agent: Ready")

    def recognize(self, text: str) -> NLPResult:
        self.last_active = time.time()
        result = self._model.predict(text)
        self.tasks_completed += 1
        return result


_ai_instance: AIAgent | None = None


def get_ai_agent() -> AIAgent:
    global _ai_instance
    if _ai_instance is None:
        _ai_instance = AIAgent()
    return _ai_instance
