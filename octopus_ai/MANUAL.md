# Octopus AI — Complete User & Operator Manual

**Version**: 2.0 (Comet-Class Multi-Agent Platform)  
**Author**: Pacific AI Team  

---

## Table of Contents

1. [System Overview & Architecture](#1-system-overview--architecture)
2. [Installation & Getting Started](#2-installation--getting-started)
   - [Windows Local Installation](#windows-local-installation)
   - [Docker & Containerized Deployment](#docker--containerized-deployment)
   - [Dependency Self-Healing](#dependency-self-healing)
3. [Voice Command System](#3-voice-command-system)
   - [Dual-Engine Architecture](#dual-engine-architecture)
   - [Microphone Permissions & Usage](#microphone-permissions--usage)
   - [English & Telugu Language Toggle](#english--telugu-language-toggle)
4. [WhatsApp Automation](#4-whatsapp-automation)
   - [Opening WhatsApp Web](#opening-whatsapp-web)
   - [Sending Messages & Natural Commands](#sending-messages--natural-commands)
   - [Interactive Contact Disambiguation Chips](#interactive-contact-disambiguation-chips)
   - [Background WhatsApp Auto-Responder](#background-whatsapp-auto-responder)
   - [Chrome Profile Persistence & Self-Healing](#chrome-profile-persistence--self-healing)
5. [Computer Mode & Desktop Automations](#5-computer-mode--desktop-automations)
   - [Desktop App Launching](#desktop-app-launching)
   - [Automated Python Assignment in Notepad](#automated-python-assignment-in-notepad)
   - [Routine Recording & Replay](#routine-recording--replay)
   - [Emergency Stop Watchdog (ESC Key)](#emergency-stop-watchdog-esc-key)
6. [Research & Creative Agents](#6-research--creative-agents)
   - [Canva Presentations & Instagram](#canva-presentations--instagram)
   - [Research Synthesis & Slide Outlines](#research-synthesis--slide-outlines)
   - [Chatbot Agent (Dhanush Persona)](#chatbot-agent-dhanush-persona)
7. [CLI Reference & Options](#7-cli-reference--options)
8. [API Reference](#8-api-reference)
9. [Troubleshooting & FAQ](#9-troubleshooting--faq)

---

## 1. System Overview & Architecture

Octopus AI is a multi-agent desktop and web automation orchestrator built around an interactive studio video avatar. It combines **Answer Mode** (deep reasoning, research, tutoring) and **Computer Mode** (real Chrome web automation and native Windows desktop control) under a single orchestrator.

```
                               ┌─────────────────────────┐
                               │   Octopus Orchestrator  │
                               └────────────┬────────────┘
                                            │
        ┌───────────────────┬───────────────┼───────────────┬───────────────────┐
        ▼                   ▼               ▼               ▼                   ▼
 ┌──────────────┐   ┌──────────────┐ ┌─────────────┐ ┌─────────────┐   ┌──────────────┐
 │  Main Agent  │   │  Web Agent   │ │Desktop Agent│ │Research Agt │   │ Chatbot Agt  │
 │(Orchestrator)│   │(Chrome/WA/IG)│ │(Windows Apps│ │(Synthesis / │   │ (Dhanush AI  │
 │              │   │              │ │ / Routines) │ │  Outlines)  │   │   Persona)   │
 └──────────────┘   └──────────────┘ └─────────────┘ └─────────────┘   └──────────────┘
```

### Key Sub-Agents:
- **Main Agent (🧠)**: Universal brain and coordinator. Decomposes multi-intent goals and routes to specialized agents.
- **Web Agent (🌐)**: Controls real visible Chrome for WhatsApp Web, Canva design automation, Instagram, and web searches.
- **Desktop Agent (💻)**: Native Windows automation via Windows UI Automation (`IUIAutomation`), launching apps (Calculator, Notepad, Camera), creating assignments, and managing files.
- **Research Agent (🔬)**: Generates structured presentation outlines, academic fact gathering, and topic research.
- **Chatbot Agent (💬)**: High-speed conversational persona for student tutoring and assistance.

---

## 2. Installation & Getting Started

### Prerequisites
- Windows 10/11 or modern Linux/macOS
- Python 3.10 to 3.14
- Google Chrome installed
- Groq API Key (free from [console.groq.com](https://console.groq.com))

---

### Windows Local Installation

1. **Clone or navigate to the repository**:
   ```powershell
   cd C:\path\to\octopus_ai
   ```

2. **Run Main Launcher**:
   ```powershell
   python main.py
   ```
   > **Note**: `main.py` automatically checks for any missing libraries and installs them into your Python environment.

3. **Open the Interface**:
   The launcher will automatically open your native desktop window or default browser at:
   ```
   http://localhost:8000
   ```

4. **Verify Systems with Demo Mode**:
   ```powershell
   python main.py --demo
   ```

---

### Docker & Containerized Deployment

Octopus AI includes a full Docker container with Xvfb, headless Google Chrome, and Playwright Chromium pre-installed.

1. **Build and Run with Docker Compose**:
   ```bash
   docker compose up --build
   ```

2. **Access the Application**:
   Navigate to `http://localhost:8000`.

3. **Configuration in `docker-compose.yml`**:
   - `GROQ_API_KEY`: Pass your key via environment or `.env`.
   - Volumes: Automatically mounts `chrome-data` and `.chrome_profile` to preserve your WhatsApp login session across container reboots.

---

### Dependency Self-Healing

If you reset your laptop or run on a clean environment, `main.py` detects missing packages and auto-installs them:
- `fastapi`, `uvicorn[standard]`, `pydantic`
- `python-multipart` (for voice uploads)
- `httpx` (for API calls and client testing)
- `groq` (ultra-fast LLM and Whisper STT)
- `edge-tts` (natural male neural speech synthesis)
- `selenium`, `webdriver-manager`, `playwright` (browser control)
- `pywin32`, `comtypes`, `pyautogui`, `keyboard` (Windows automation)

---

## 3. Voice Command System

### Dual-Engine Architecture

Octopus AI uses a dual-engine speech recognition pipeline to ensure **zero-latency live typing** while guaranteeing **100% reliable multi-lingual transcription**:

1. **Live Preview (Web Speech API)**: As you speak, transcribed words immediately appear inside the search bar.
2. **Groq Whisper Transcription (`/api/voice/transcribe`)**: High-fidelity audio is captured via `MediaRecorder` in WebM/WAV format. If the browser's speech engine cuts out, is blocked, or fails, the audio is sent to Groq's `whisper-large-v3-turbo` model.

### Microphone Permissions & Usage

1. Click the **Microphone icon (🎙️)** on the right side of the search bar.
2. If prompted by Chrome/Edge, click **Allow** for microphone access.
3. The microphone turns crimson and a **Voice Recording Waveform Pill** appears below the bar:
   ```
   [||||] Listening to voice command… Speak now
   ```
4. Speak your command naturally (e.g., *"Open WhatsApp and message Rahul that I am on my way"*).
5. Click the mic button again or pause; Octopus will process and execute your task.

### English & Telugu Language Toggle

Next to the microphone button is the **Language Chip (`EN` / `TE`)**:
- Click `EN` to toggle to `TE` (**Telugu / తెలుగు**).
- When set to `TE`, Groq Whisper and the speech engine are configured to transcribe spoken Telugu with native accuracy.

---

## 4. WhatsApp Automation

Automations run in **Real Visible Chrome** using your personal automation profile (`AutomationData` / `.chrome_profile`), ensuring you stay logged in without scanning the QR code every time.

### Opening WhatsApp Web
Simply speak or type any conversational variant:
- `"open whatsapp"`
- `"can you open whatsapp"`
- `"open whatsapp web"`
- `"whatsapp open cheyi"` (Telugu)
- `"open my whatsapp"`
- `"/whatsapp"`

Octopus AI will launch Chrome, navigate directly to WhatsApp Web, and notify you when ready.

### Sending Messages & Natural Commands
You can specify recipients and messages in natural conversational language:
- `"Send message to Rahul saying I will reach at 5pm"`
- `"Message to Mom that I reached home safely"`
- `"Tell Priya saying the documents are ready"`

### Interactive Contact Disambiguation Chips
If multiple contacts match your query (e.g. searching for *"Rahul"* returns *"Rahul Sharma"* and *"Rahul Tech"*):
1. Octopus AI pauses and presents interactive buttons in the **Response Drawer**:
   ```
   [ 1. Rahul Sharma ]   [ 2. Rahul Tech ]   [ Cancel ]
   ```
2. Click the chip corresponding to your recipient, or say *"number 1"* or *"second one"*.
3. The message will be dispatched immediately.

### Background WhatsApp Auto-Responder
Octopus includes a 24/7 background responder daemon that monitors incoming messages and replies using context:
- **Start**: Say `"activate whatsapp auto responder"` or `"/autoresponder"`.
- **Stop**: Say `"stop whatsapp auto responder"`.
- **Behavior**: Stays in the active conversation until 25 seconds of silence, then checks for other incoming messages.

### Chrome Profile Persistence & Self-Healing
- **No Zombie Locks**: When starting Chrome, Octopus AI automatically inspects and cleans up orphaned background processes holding locks on `AutomationData`.
- **Session Auto-Recovery**: If you manually close the Chrome automation window, `BrowserEngine.is_ready()` detects the closure and cleanly re-initializes upon your next command without throwing errors.

---

## 5. Computer Mode & Desktop Automations

### Desktop App Launching
Control native Windows software directly:
- `"Open Calculator"` or `"Launch calc"`
- `"Open Notepad"`
- `"Open Camera"`
- `"Open Paint"` or `"Launch mspaint"`
- `"Open Task Manager"`

### Automated Python Assignment in Notepad
Say:
```
"Create a Python assignment on my desktop and open it in Notepad"
```
The Desktop Agent will:
1. Synthesize a complete Python assignment (functions, loops, data structures, exercises).
2. Save it to `C:\Users\<User>\Desktop\python_assignment.py`.
3. Open it automatically in Microsoft Notepad.

### Routine Recording & Replay
Record repeated computer tasks and replay them on demand:
- **Start Recording**: Call `start_routine_recording` with a name.
- **Replay**: Say `"run routine <name>"`.

### Emergency Stop Watchdog (ESC Key)
At any point during a Computer Use automation, press the **`ESC`** key on your physical keyboard. The Emergency Stop Watchdog immediately halts all mouse, keyboard, and PowerShell actions.

---

## 6. Research & Creative Agents

### Canva Presentations & Instagram
- **Canva**: Say `"Create a presentation in Canva about Renewable Energy"`. Octopus opens Canva and navigates to presentation templates for the topic.
- **Instagram**: Say `"Open Instagram and search for @nasa"`.

### Research Synthesis & Slide Outlines
Switch to the Research Agent (`/research`) or ask:
- `"Create a presentation outline on quantum computing"`
- `"Synthesize research on autonomous vehicle safety"`

The complete structured outline is rendered directly into the **Response Drawer** with a 1-click `📋 Copy` button.

### Chatbot Agent (Dhanush Persona)
Switch to the Chatbot Agent (`/chat`) for study assistance, educational tutoring, or natural conversations powered by local LLM and Dhanush's neural male voice.

---

## 7. CLI Reference & Options

Launch `main.py` with custom flags:

```bash
# Standard launch (default: port 8000, reload enabled)
python main.py

# Specify initial active agent (main, web, desktop, research, chatbot)
python main.py --agent web

# Run on a different port if 8000 is occupied
python main.py --port 8080

# Bind to all network interfaces (for LAN or Docker access)
python main.py --host 0.0.0.0 --port 8000

# Disable auto-reload
python main.py --no-reload

# Run headless browser mode
python main.py --headless

# Provide Groq API key via CLI
python main.py --key gsk_your_key_here

# Run quick verification demo
python main.py --demo
```

---

## 8. API Reference

All endpoints are hosted on `http://localhost:8000`:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves `orb-ui.html` frontend interface |
| `POST` | `/api/chat` | Main command intake, intent routing, and execution |
| `POST` | `/api/voice/transcribe` | Transcribes audio via Groq Whisper (`multipart` or `base64`) |
| `POST` | `/api/tts` | Generates male neural speech audio URL |
| `GET` | `/api/agents` | Returns list of available 9-dots sub-agents |
| `POST` | `/api/agent/select` | Switches active agent and returns greeting |
| `GET` | `/api/live-status` | Server health check and UI auto-reload status |
| `POST` | `/api/computer/execute` | Executes atomic or multi-step Computer-Use tool |
| `POST` | `/api/whatsapp/auto-responder/start` | Starts background WhatsApp auto-responder |
| `POST` | `/api/whatsapp/auto-responder/stop` | Stops background WhatsApp auto-responder |
| `GET` | `/api/whatsapp/auto-responder/status` | Returns auto-responder running status |

---

## 9. Troubleshooting & FAQ

### Q1: Chrome says "session not created: DevToolsActivePort file doesn't exist"
- **Cause**: An earlier Chrome process crashed or was forcefully closed and left a lock on `AutomationData`.
- **Solution**: Octopus AI automatically clears these on startup. If this persists, close all Chrome automation windows and re-run `python main.py`. Your personal Chrome tabs will remain untouched.

### Q2: Server says "Server port 8000 failed to open within timeout"
- **Cause**: Another application is using port 8000.
- **Solution**: Launch on a custom port:
  ```powershell
  python main.py --port 8080
  ```

### Q3: Speech recognition does not pick up my voice
- **Cause**: Browser microphone permissions blocked.
- **Solution**: Click the padlock or site settings icon next to `localhost:8000` in your browser URL bar, set **Microphone** to **Allow**, and refresh. The fallback Groq Whisper engine will capture and transcribe your audio.

### Q4: WhatsApp requires scanning QR code again
- **Cause**: Running in a temporary directory instead of the persistent profile.
- **Solution**: Run via `python main.py`. Profile data is stored in `c:\Users\<user>\.chrome_profile\Default` and will remember your session permanently.

---
*Octopus AI Documentation — Maintained by Pacific AI*
