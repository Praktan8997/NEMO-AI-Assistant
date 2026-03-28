# 🤖 NEMO — Multi-Agent AI Assistant

> **N**eural **E**ngine for **M**ulti-agent **O**rchestration  
> A powerful, multi-lingual AI personal assistant powered by FastAPI, React, and OpenRouter LLMs.

---

## ✨ Features

- 🧠 **Multi-Agent Architecture** — Dedicated agents for AI, Automation, Conversation, Language detection, and Debugging
- 💬 **Conversational AI** — Powered by OpenRouter (Gemini 2.5 Pro) with persistent session memory
- 🌐 **Multilingual Support** — English, हिंदी (Hindi), and मराठी (Marathi)
- 🎙️ **Voice Input & TTS** — Speak commands and hear NEMO respond
- 🖥️ **System Automation** — Open apps, search the web, run system commands
- 📊 **Live System Metrics** — Real-time CPU, memory, and agent status monitoring
- ⚡ **Quick Actions** — Pre-built language-aware command shortcuts
- 🗂️ **Command History** — Browse and re-run past commands
- 🌙 **Dark Glassmorphism UI** — Stunning futuristic React interface

---

## 🏗️ Project Structure

```
NEMO-AI-Assistant/
├── Nemo-backend/          # FastAPI backend (Python)
│   ├── agents/            # Multi-agent system
│   │   ├── ai_agent.py           # Core NLP / AI agent
│   │   ├── automation_agent.py   # System automation (open apps, etc.)
│   │   ├── conversation_agent.py # LLM-powered conversation (OpenRouter)
│   │   ├── language_agent.py     # Language detection (EN / HI / MR)
│   │   ├── app_discovery.py      # Installed app discovery
│   │   └── debug_agent.py        # Agent status & debug tracking
│   ├── routers/           # API route handlers
│   │   ├── commands.py    # POST /api/commands/
│   │   ├── health.py      # GET /api/health/
│   │   └── apps.py        # GET /api/apps/
│   ├── models/            # Pydantic data models
│   ├── tests/             # Pytest test suite
│   ├── main.py            # FastAPI app entry point
│   ├── requirements.txt   # Python dependencies
│   └── .env.example       # Environment variable template
│
├── Nemo-ui/               # React frontend (Vite)
│   ├── src/
│   │   ├── components/
│   │   │   ├── AgentStatus.jsx    # Live agent status panel
│   │   │   ├── ChatWindow.jsx     # Conversation display + TTS
│   │   │   ├── CommandHistory.jsx # Past command log
│   │   │   ├── ResponsePanel.jsx  # Structured response renderer
│   │   │   ├── SystemStats.jsx    # CPU / memory metrics
│   │   │   └── VoiceInput.jsx     # Voice + text input component
│   │   ├── App.jsx        # Root application component
│   │   ├── index.css      # Global styles & design tokens
│   │   └── main.jsx       # React entry point
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
└── README.md
```

---

## 🤖 Agent Overview

| Agent | Role |
|---|---|
| **AI Agent** | Core NLP processing and intent classification |
| **Conversation Agent** | LLM chat via OpenRouter (Gemini 2.5 Pro) with session memory |
| **Automation Agent** | Opens apps, types text, controls the system via PyAutoGUI |
| **Language Agent** | Detects and routes commands in EN / HI / MR |
| **App Discovery** | Scans installed applications for fuzzy-match launching |
| **Debug Agent** | Tracks and exposes agent health statuses |

---

## 🚀 Getting Started

### Prerequisites

- **Python** 3.10+
- **Node.js** 18+ and **npm**
- An **OpenRouter API key** — [Get one free at openrouter.ai](https://openrouter.ai)

---

### 1. Clone the Repository

```bash
git clone https://github.com/Praktan8997/NEMO-AI-Assistant.git
cd NEMO-AI-Assistant
```

---

### 2. Set Up the Backend

```bash
cd Nemo-backend

# Create and activate a virtual environment
python -m venv .venv

# On Windows
.venv\Scripts\activate

# On macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Configure Environment Variables

```bash
# Copy the example env file
copy .env.example .env   # Windows
cp .env.example .env     # macOS/Linux
```

Edit `.env` and add your OpenRouter API key:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=google/gemini-2.5-pro-preview
MAX_HISTORY_TURNS=10
```

#### Start the Backend Server

```bash
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.  
Interactive API docs: `http://localhost:8000/docs`

---

### 3. Set Up the Frontend

```bash
cd Nemo-ui

# Install dependencies
npm install

# Start the development server
npm run dev
```

The UI will be available at `http://localhost:5173`.

---

## 🎮 Usage

Once both servers are running:

1. Open `http://localhost:5173` in your browser
2. **Type or speak** a command (click the mic icon for voice input)
3. Switch languages using the **EN / हि / मर** buttons in the header
4. Use **Quick Actions** shortcuts in the right panel for common tasks
5. View live agent statuses and system metrics in the left sidebar
6. Browse your **Command History** to re-run past commands

### Example Commands

| Language | Command Example |
|---|---|
| English | `Open Chrome`, `Search for AI news`, `Show system stats`, `Hello NEMO` |
| हिंदी | `Chrome खोलो`, `Discord लॉन्च करो`, `नमस्ते NEMO` |
| मराठी | `Chrome उघड`, `Discord सुरू कर`, `नमस्कार NEMO` |

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | System info and active agents |
| `POST` | `/api/commands/` | Submit a command to NEMO |
| `GET` | `/api/health/` | Backend health & agent statuses |
| `GET` | `/api/health/history` | Recent command history |
| `DELETE` | `/api/commands/session/{id}` | Clear session memory |
| `GET` | `/api/apps/` | List discovered applications |
| `GET` | `/docs` | Interactive Swagger UI |

---

## 🛠️ Tech Stack

### Backend
- **[FastAPI](https://fastapi.tiangolo.com/)** — High-performance async Python API framework
- **[Uvicorn](https://www.uvicorn.org/)** — ASGI server
- **[Pydantic](https://docs.pydantic.dev/)** — Data validation and settings management
- **[PyAutoGUI](https://pyautogui.readthedocs.io/)** — Desktop automation
- **[psutil](https://psutil.readthedocs.io/)** — System metrics
- **[Transformers](https://huggingface.co/docs/transformers/)** — NLP model support
- **[OpenRouter](https://openrouter.ai/)** — LLM API gateway (Gemini 2.5 Pro)

### Frontend
- **[React 18](https://react.dev/)** — UI component library
- **[Vite](https://vitejs.dev/)** — Lightning-fast build tool
- **Web Speech API** — Browser-native voice input & TTS

---

## 🧪 Running Tests

```bash
cd Nemo-backend

# Activate your virtual environment first
.venv\Scripts\activate   # Windows

# Run the test suite
pytest tests/ -v
```

---

## 🌐 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | *(required)* | Your OpenRouter API key |
| `OPENROUTER_MODEL` | `google/gemini-2.5-pro-preview` | LLM model to use |
| `MAX_HISTORY_TURNS` | `10` | Conversation memory depth per session |

> **Note:** If no API key is provided, NEMO falls back to a rule-based response engine.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

This project is open source. Feel free to use, modify, and distribute.

---

<div align="center">
  <sub>NEMO — Neural Engine for Multi-agent Orchestration</sub>
</div>
