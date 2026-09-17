# Octopus AI — Universal Desktop & Web Multi-Agent Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Support](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)

**Octopus AI** is a Comet-class multi-agent desktop orchestrator featuring a frameless studio video avatar, real visible Chrome automation, native Windows computer-use, and dual-engine voice commands in English and Telugu.

For full, in-depth operator instructions, see the **[Operator & User Manual (MANUAL.md)](MANUAL.md)**.

---

## 🌟 Core Capabilities

### 1. 🧠 Multi-Agent Orchestration (9-Dots Selector)
- **Main Agent (🧠)**: Universal brain and orchestrator. Automatically classifies user intents and delegates across sub-agents.
- **Web Agent (🌐)**: Automates WhatsApp Web, Canva presentation design, Instagram, and web search in real visible Google Chrome with persistent sessions.
- **Desktop Agent (💻)**: Controls native Windows desktop applications (Notepad, Calculator, Paint, Task Manager, Camera), generates Python assignments directly to your Desktop, and replayed routines.
- **Research Agent (🔬)**: Generates academic research syntheses, slide outlines, and structured fact summaries.
- **Chatbot Agent (💬)**: High-speed conversational tutoring persona powered by local LLM and Dhanush's cloned neural voice.

### 2. 🎙️ High-Precision Dual-Engine Voice Command
- **Real-Time Live Typing**: Web Speech API provides instant visual feedback in the search bar as you speak.
- **Groq Whisper STT Fallback**: Simultaneous recording via `MediaRecorder` sent to Groq's ultra-low latency `whisper-large-v3-turbo` model via `/api/voice/transcribe`.
- **Multilingual Support**: Switch seamlessly between **English (`EN`)** and **Telugu (`TE`)** using the language toggle.
- **Visual Waveform**: Real-time audio waveform activity indicator below the search bar.

### 3. 💬 WhatsApp Web Automation & Disambiguation
- **Conversational Queries**: Recognizes `"open whatsapp"`, `"whatsapp web"`, `"can you open whatsapp"`, `"whatsapp open cheyi"`, etc.
- **Natural Message Sending**: `"Send message to Rahul saying I will be there in 10 minutes"`.
- **Interactive Disambiguation Chips**: When multiple contacts match, clickable chip buttons (`[ 1. Rahul Sharma ]`, `[ 2. Rahul Tech ]`) appear in the response drawer.
- **Background Auto-Responder**: Background daemon that automatically converses with incoming WhatsApp chats and monitors for 25 seconds of silence.
- **Self-Healing Chrome**: Automatically cleans up orphaned process locks (`DevToolsActivePort`) and recovers closed sessions.

### 4. 💻 Computer Mode & Windows Automation
- **App Launching**: Launch Calculator, Notepad, Camera, Paint, Task Manager with simple natural language.
- **Automated Assignment Generator**: `"Create a python assignment on my desktop and open it in Notepad"`.
- **Safety First**: Physical **`ESC`** key Emergency Stop Watchdog halts automation immediately.

---

## 🚀 Quick Start

### 1. Windows Local Setup (Recommended)

1. Clone and navigate to the project:
   ```powershell
   git clone https://github.com/ganganidhanush-maker/Pacific.git
   cd Pacific/octopus_ai
   ```

2. Start the platform:
   ```powershell
   python main.py
   ```
   > **Note**: `main.py` features automatic dependency self-healing. Any missing packages are automatically installed on launch.

3. The application will launch at:
   ```
   http://localhost:8000
   ```

---

### 2. Docker Setup

Octopus AI is fully containerized with headless Google Chrome, Xvfb virtual display, and Playwright:

```bash
# Build and run the container
docker compose up --build
```

Access the UI at `http://localhost:8000`. WhatsApp session and audio caches are persisted via Docker volumes.

---

### 3. Quick Demo Mode

Test multi-agent reasoning and tool execution without launching browser windows:

```bash
python main.py --demo
```

---

## 🛠️ CLI Options

```bash
# Start with a specific sub-agent (main, web, desktop, research, chatbot)
python main.py --agent web

# Run on a different port if 8000 is occupied
python main.py --port 8080

# Bind host to 0.0.0.0 (LAN or remote access)
python main.py --host 0.0.0.0 --port 8000

# Disable hot reload
python main.py --no-reload

# Run headless browser mode
python main.py --headless
```

---

## 📁 Repository Structure

```
octopus_ai/
├── agent/                  # Multi-agent implementations (Web, Desktop, Research, Chatbot)
│   ├── agent.py            # Universal Octopus agent
│   ├── groq_llm.py         # Groq LLM & Whisper STT integration
│   ├── orchestrator.py     # Master multi-agent orchestrator
│   └── whatsapp_responder.py # 24/7 background WhatsApp responder
├── assets/                 # Studio video avatar clips and audio cache
├── computer_use/           # Windows UI Automation, Clacky visual pointer, watchdog
├── engine/                 # Browser automation engines
│   ├── selenium_engine.py  # Real visible Chrome engine with profile persistence
│   └── playwright_engine.py# High-performance Playwright engine
├── interface/              # Standalone pywebview window runner
├── server/                 # FastAPI backend server
│   ├── app.py              # REST API & WebSocket endpoints
│   └── voice_service.py    # Neural TTS voice service
├── tests/                  # Automated verification test suites
├── orb-ui.html             # Sleek frontend UI with frameless video avatar
├── main.py                 # Cross-platform entry point with dependency self-healing
├── Dockerfile              # Production Dockerfile
├── docker-compose.yml      # Docker Compose configuration
├── requirements.txt        # Python package requirements
├── MANUAL.md               # Comprehensive Operator & User Manual
└── README.md               # Platform overview
```

---

## 🧪 Testing

Run the automated test suites:

```powershell
# Platform commands & computer use test suite
python -m unittest tests/test_all_commands.py

# Server endpoints & WhatsApp routing test suite
python -m unittest tests/test_server_endpoints.py
```

---

## 📄 Documentation

For full step-by-step configuration, WhatsApp profile setup, voice tuning, and troubleshooting, read the **[MANUAL.md](MANUAL.md)**.
