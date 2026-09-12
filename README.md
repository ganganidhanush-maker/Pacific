# Octopus AI — Hierarchical Multi-Agent Desktop Tool 🐙

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Selenium](https://img.shields.io/badge/Selenium-4.15%2B-43B02A.svg?logo=selenium&logoColor=white)](https://www.selenium.dev/)

An intelligent **Hierarchical Multi-Agent System** with an interactive **Desktop Video Avatar**, **Cloned Neural Voice**, and autonomous sub-agents designed for **students, teachers, and educators**.

---

## ⚡ 1-Minute Quickstart

Anyone who forks this repository can run the application seamlessly using either native Python or Docker.

### Option A: Run Natively with Python (Windows / macOS / Linux)

`ash
# 1. Clone your fork
git clone https://github.com/<your-username>/Pacific.git
cd Pacific

# 2. Create and activate virtual environment (optional but recommended)
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch Octopus AI!
python main.py
`
> *On desktop operating systems, a native frameless window opens automatically. On headless systems, it opens in your default browser at http://localhost:8000.*

---

### Option B: Run with Docker (Cross-Platform Container)

No local Python, Chrome, or virtual environment setup required:

`ash
# 1. Clone your fork
git clone https://github.com/<your-username>/Pacific.git
cd Pacific

# 2. Build and start container
docker compose up --build
`
> *Once started, open your browser and navigate to **[http://localhost:8000](http://localhost:8000)**.*

---

## 🧠 The 5 Official Agents

Select any agent from the **9-Dots Menu** in the top right, or switch dynamically using slash commands:

| Agent | Icon | Role & Scope | Slash Command |
|---|---|---|---|
| **Main Agent** | 🧠 | **Avatar Brain & Master Orchestrator** (Default)<br>Decomposes natural teacher/student requests into multi-agent plans. | /main |
| **Web Agent** | 🌐 | **Chrome Web Automations**<br>WhatsApp broadcasts, on-topic filtering, Canva slide generation, Instagram, and web search. | /web or /whatsapp or /canva |
| **Desktop Agent** | 💻 | **Local System & Filesystem Manager**<br>Finds local documents (.pdf, .py), touches/moves/organizes files, and launches native apps. | /desktop |
| **Research Agent** | 🔬 | **Academic Knowledge & Slide Outlines**<br>Synthesizes topics and generates complete slide-by-slide presentation decks. | /research |
| **Chatbot Agent** | 💬 | **Student & Teacher Assistant**<br>Interactive conversational tutor for concept explanation and lesson planning. | /chatbot |

---

## 🏗️ Architecture

`
User Input (Audio / Text)
         │
         ▼
┌────────────────────────────────────────┐
│   MAIN AGENT: Avatar Brain             │
│   • Frameless Video Avatar (3 Layers)  │
│   • AI Prompt Optimizer (Ollama/Groq)  │
│   • Neural Voice (Chatterbox/Edge-TTS) │
└───────────────────┬────────────────────┘
                    │  Orchestration Plan
         ┌──────────┼──────────┬──────────┐
         ▼          ▼          ▼          ▼
     🌐 Web     💻 Desktop  🔬 Research 💬 Chatbot
     Agent       Agent      Agent       Agent
     (Chrome)    (Local OS) (Knowledge) (Tutor)
`

---

## 🛠️ Configuration & Optional Features

Octopus AI is built to work out of the box with zero required configuration. To unlock additional capabilities:

- **Local LLM GPU Acceleration**: Install [Ollama](https://ollama.com) and run ollama pull llama3.2. Octopus AI automatically connects to Ollama on http://127.0.0.1:11434.
- **Cloud LLM Fallback (Groq)**: Create a .env file and specify GROQ_API_KEY=your_key_here.
- **Hardware Acceleration**: If an NVIDIA GPU is detected, PyTorch with CUDA will automatically accelerate neural voice synthesis.

---

## 📂 Project Structure

`
Pacific/
├── main.py                     # Root entry point
├── Dockerfile                  # Production container definition
├── docker-compose.yml          # Container orchestration
├── requirements.txt            # Python dependencies
└── octopus_ai/
    ├── main.py                 # Core tool launcher
    ├── orb-ui.html             # Video Avatar & 9-Dots UI
    ├── agent/
    │   ├── orchestrator.py     # Master Orchestrator & Prompt Optimizer
    │   └── subagents/          # Web, Desktop, Research, Chatbot agents
    ├── automations/            # WhatsApp, Canva, Instagram, Desktop tasks
    ├── server/                 # FastAPI server, local LLM, and voice services
    └── assets/
        ├── videos/             # Studio seamless avatar layers (idle, thinking, speaking)
        ├── voice_reference/    # Reference voice embeddings
        └── audio_cache/        # Cached neural speech files
`

---

## 📄 License
MIT License. Created with ❤️ by Dhanush.
