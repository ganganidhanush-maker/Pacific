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

```bash
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
```
> *On desktop operating systems, a native frameless window opens automatically. On headless systems, it opens in your default browser at http://localhost:8000.*

---

### Option B: Run with Docker (Cross-Platform Container)

No local Python, Chrome, or virtual environment setup required:

```bash
# 1. Clone your fork
git clone https://github.com/<your-username>/Pacific.git
cd Pacific

# 2. Build and start container
docker compose up --build
```
> *Once started, open your browser and navigate to **[http://localhost:8000](http://localhost:8000)**.*

---

## 🧠 The 5 Official Agents

Select any agent from the **9-Dots Menu** in the top right, or switch dynamically using slash commands:

| Agent | Icon | Role & Scope | Slash Command |
|---|---|---|---|
| **Main Agent** | 🧠 | **Avatar Brain & Master Orchestrator** (Default)<br>Decomposes natural teacher/student requests into multi-agent plans. | `/main` |
| **Web Agent** | 🌐 | **Chrome Web Automations**<br>WhatsApp broadcasts (e.g. Teacher PTM updates), on-topic filtering, Canva slide generation, Instagram, and web search. | `/web` or `/whatsapp` or `/canva` |
| **Desktop Agent** | 💻 | **Open Interpreter Execution & Local Files**<br>Interactive Python sandbox, safe terminal execution, finding local documents (.pdf, .py), and launching native apps. | `/desktop` |
| **Research Agent** | 🔬 | **Academic Knowledge & Slide Outlines**<br>Synthesizes lecture topics and generates complete slide-by-slide presentation decks. | `/research` |
| **Chatbot Agent** | 💬 | **Student & Teacher Assistant**<br>Interactive conversational tutor with native multilingual Telugu & English reasoning. | `/chatbot` |

---

## 🚀 Open Interpreter & Kimi K3 ("Kiwi") Blueprint Integration

Octopus AI leverages core architectural patterns inspired by **Open Interpreter**:

1. **Kimi K3 ("Kiwi") Engine**: Support for Moonshot Platform API (`kimi-k3` model) providing 256K context window, 10x lower cost, and high-speed coding and academic reasoning.
2. **Interactive Code & Terminal Sandbox**: Desktop Agent can execute arbitrary Python scripts and PowerShell/bash commands safely with timeout and security guardrails.
3. **Modular Educational Skills (`skills/`)**:
   - `whatsapp_ptm_broadcast`: Automated teacher broadcasts and context-filtered replies.
   - `academic_study_deck`: Textbook chapter ingestion (256k context) and revision deck generation.
   - `python_code_sandbox`: Computer science lab exercises, execution, and instant error diagnosis.

---

## 🛠️ Configuration & LLM Providers

Octopus AI is built to work out of the box with zero required configuration, featuring an intelligent 4-tier model hierarchy:

1. **Tier 1: Kimi K3 ("Kiwi")**: Set `KIMI_API_KEY=your_key` or `MOONSHOT_API_KEY=your_key` in `.env` (256k context, ultra-fast).
2. **Tier 2: Groq Cloud LLM**: Set `GROQ_API_KEY=your_key` in `.env` (Qwen/Llama 70B, multilingual Telugu).
3. **Tier 3: Local GPU Ollama**: Install [Ollama](https://ollama.com) and run `ollama pull llama3.2` (100% offline, private).
4. **Tier 4: Offline Conversational Fallback**: Graceful heuristic responses even when completely offline.

---

## 📂 Project Structure

```
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
    │   ├── kimi_llm.py         # Kimi K3 ("Kiwi") Moonshot API Engine
    │   └── subagents/          # Web, Desktop, Research, Chatbot agents
    ├── skills/                 # Educational Skills (WhatsApp PTM, Study Decks, Code Tutor)
    ├── automations/            # WhatsApp, Canva, Instagram, Desktop tasks
    ├── server/                 # FastAPI server, local LLM, and voice services
    └── assets/
        ├── videos/             # Studio seamless avatar layers (idle, thinking, speaking)
        ├── voice_reference/    # Reference voice embeddings
        └── audio_cache/        # Cached neural speech files
```

---

## 📄 License
MIT License. Created with ❤️ by Dhanush.
