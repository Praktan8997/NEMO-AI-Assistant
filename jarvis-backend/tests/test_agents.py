"""
Tests — Debug & Dev Agent
Covers AI, Automation, and API endpoint correctness.
"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

# Ensure the backend root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app
from models.nlp_model import NLPModel
from models.schemas import IntentType

client = TestClient(app)


# ── NLP Model Tests ─────────────────────────────────────────────────────────

class TestNLPModel:
    def setup_method(self):
        self.model = NLPModel()

    def test_open_app_intent(self):
        result = self.model.predict("Open Chrome")
        assert result.intent == IntentType.OPEN_APP
        assert result.confidence > 0.1
        assert result.entities.get("app") == "chrome"

    def test_search_web_intent(self):
        result = self.model.predict("Search for Python tutorials")
        assert result.intent == IntentType.SEARCH_WEB
        assert "query" in result.entities

    def test_system_info_intent(self):
        result = self.model.predict("Show CPU and memory stats")
        assert result.intent == IntentType.SYSTEM_INFO

    def test_calculate_intent(self):
        result = self.model.predict("Calculate 42 + 58")
        assert result.intent == IntentType.CALCULATE
        assert "expression" in result.entities

    def test_close_app_intent(self):
        result = self.model.predict("Close Notepad")
        assert result.intent == IntentType.CLOSE_APP

    def test_unknown_intent(self):
        result = self.model.predict("xyzzy foo baz quux")
        # Low confidence inputs should not crash
        assert result.intent is not None

    def test_confidence_range(self):
        result = self.model.predict("Open Excel")
        assert 0.0 <= result.confidence <= 1.0


# ── API Endpoint Tests ───────────────────────────────────────────────────────

class TestCommandsAPI:
    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "Jarvis" in data["name"]

    def test_health_endpoint(self):
        response = client.get("/api/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert isinstance(data["agents"], list)
        assert len(data["agents"]) == 5

    def test_process_command_structure(self):
        response = client.post(
            "/api/commands/",
            json={"text": "Show system status", "session_id": "test_session"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "command_id" in data
        assert "nlp_result" in data
        assert "automation_result" in data
        assert "response_text" in data

    def test_process_open_chrome(self):
        response = client.post(
            "/api/commands/",
            json={"text": "Open Chrome", "session_id": "test"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["nlp_result"]["intent"] == "open_app"

    def test_command_history(self):
        # Process a command first
        client.post("/api/commands/", json={"text": "Search for news"})
        response = client.get("/api/health/history?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_invalid_empty_command(self):
        response = client.post(
            "/api/commands/",
            json={"text": ""},
        )
        assert response.status_code == 422  # Pydantic validation error
