"""
Octopus AI - Desktop Agent Backend Server

Provides APIs for:
- Serving Desktop UI & Frameless Video Avatar Assets
- 9-Dots Multi-Agent Selection (Web, WhatsApp, Canva, Instagram)
- Live Browser Automation in Real Visible Chrome
- Natural Human Male Neural Voice Generation (edge-tts PrabhatNeural)
- Deterministic State Transitions (Idle -> Thinking -> Speaking -> Idle)
"""

import os
import sys
import json
import asyncio
import hashlib
import uuid
import re
import time
import concurrent.futures
from pathlib import Path
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import edge_tts

# Ensure repo directory and parent directory are on sys.path
repo_dir = Path(__file__).resolve().parent.parent
parent_dir = repo_dir.parent
for p in [str(parent_dir), str(repo_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from octopus_ai.automations import create_default_registry, PreviewManager
from octopus_ai.agent.agent import OctopusAgent
from octopus_ai.engine.selenium_engine import BrowserEngine
from server.local_llm_service import local_llm_instance, sanitize_speech_response
from octopus_ai.agent.subagents.desktop_agent import desktop_agent_instance
from octopus_ai.agent.subagents.research_agent import research_agent_instance
from octopus_ai.agent.subagents.chatbot_agent import chatbot_agent_instance
from octopus_ai.agent.subagents.web_agent import web_agent_instance

app = FastAPI(title="Octopus AI Desktop Tool")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_cors_and_cache_headers(request: Request, call_next):
    """
    Ensure robust CORS and cache headers across all responses including 304 and 206,
    preventing Web Audio API media muting and browser caching issues.
    """
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Expose-Headers"] = "*"

    path = request.url.path
    if path.startswith("/assets/audio_cache/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        response.headers["Accept-Ranges"] = "bytes"
    elif path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    return response

# Assets and audio cache directory
assets_dir = repo_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

AUDIO_CACHE_DIR = assets_dir / "audio_cache"
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Default Natural Male Voice (Indian English matching user)
DEFAULT_VOICE = "en-IN-PrabhatNeural"

# Global instances
engine_instance: Optional[BrowserEngine] = None
agent_instance: Optional[OctopusAgent] = None
registry_instance = None
preview_manager = PreviewManager()

# Active selected agent state: Default is Main Agent (General AI Chat & Orchestration)
CURRENT_AGENT = os.environ.get("OCTOPUS_INITIAL_AGENT", "main").strip().lower()

# Dedicated single-thread worker for serialized WhatsApp / WebDriver operations
whatsapp_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="WhatsAppWorker")

# Per-client conversational session state with time-based expiry
SESSION_STORAGE: Dict[str, Dict[str, Any]] = {}
SESSION_EXPIRY_SEC = 300  # 5 minutes

# Backward compatibility alias for tests directly accessing PENDING_SESSION_STATE
PENDING_SESSION_STATE: Dict[str, Any] = {}

def get_session_state(session_id: str) -> Dict[str, Any]:
    now = time.time()
    # Prune expired sessions
    stale = [sid for sid, data in SESSION_STORAGE.items() if now - data.get("timestamp", 0) > SESSION_EXPIRY_SEC]
    for sid in stale:
        SESSION_STORAGE.pop(sid, None)
        if sid == "default":
            PENDING_SESSION_STATE.clear()

    sess = SESSION_STORAGE.get(session_id)
    if sess and now - sess.get("timestamp", 0) <= SESSION_EXPIRY_SEC:
        return sess.get("state", {})
    if session_id == "default" and PENDING_SESSION_STATE:
        return PENDING_SESSION_STATE
    return {}

def set_session_state(session_id: str, state: Dict[str, Any]):
    SESSION_STORAGE[session_id] = {
        "state": state,
        "timestamp": time.time()
    }
    if session_id == "default":
        PENDING_SESSION_STATE.clear()
        PENDING_SESSION_STATE.update(state)

def clear_session_state(session_id: str):
    SESSION_STORAGE.pop(session_id, None)
    if session_id == "default":
        PENDING_SESSION_STATE.clear()

AVAILABLE_AGENTS = [
    {
        "id": "main",
        "name": "Main Agent",
        "icon": "🧠",
        "description": "Avatar Brain & Multi-Agent Orchestrator",
        "placeholder": "Explain your goal (e.g. 'I am Saiteja, send PTM notice to groups')...",
        "greeting": "Main Agent online. I am ready to coordinate all sub-agents for you."
    },
    {
        "id": "web",
        "name": "Web Agent",
        "icon": "🌐",
        "description": "WhatsApp Web, Canva presentations, Instagram, Google Search",
        "placeholder": "Enter web task or WhatsApp broadcast (e.g. 'Send PTM update')...",
        "greeting": "Web Agent activated. Ready for WhatsApp, Canva, Instagram, and web automations."
    },
    {
        "id": "desktop",
        "name": "Desktop Agent",
        "icon": "💻",
        "description": "Find local files, organize/touch/move documents, system tasks",
        "placeholder": "Search local files (e.g. 'Find all PDF files on my computer')...",
        "greeting": "Desktop Agent activated. Ready to search, move, and organize your local files."
    },
    {
        "id": "research",
        "name": "Research Agent",
        "icon": "🔬",
        "description": "Academic research, knowledge synthesis, slide outlines",
        "placeholder": "Enter research topic (e.g. 'Python PDF operations outline')...",
        "greeting": "Research Agent activated. What topic would you like me to analyze or outline?"
    },
    {
        "id": "chatbot",
        "name": "Chatbot Agent",
        "icon": "💬",
        "description": "Student tutoring, teacher advisory, and educational Q&A",
        "placeholder": "Ask any question, discuss concepts, or brainstorm lesson plans...",
        "greeting": "Chatbot Agent ready. How can I help with your studies or teaching today?"
    },
    {
        "id": "computer",
        "name": "Computer Use",
        "icon": "🖥️",
        "description": "Autonomous Windows 11 control: UI Automation, Apps, Mouse/Keyboard, Shell, Pointing",
        "placeholder": "Enter desktop goal (e.g. 'Open Notepad, type meeting notes', or 'Highlight search bar')...",
        "greeting": "Computer Use Agent active. Full Windows control, UI automation, and companion pointing ready."
    }
]



def is_whatsapp_open_request(msg: str) -> bool:
    """
    Check if the user is asking to open / launch WhatsApp Web without sending a specific message.
    Handles conversational questions, polite requests, and multilingual commands.
    """
    m = msg.lower().strip()
    if m in ['whatsapp', 'whatsapp web', 'web whatsapp', 'wa', '/whatsapp', '/wa']:
        return True
    if any(k in m for k in [' saying ', ' send message to', ' message to ', ' text to ', ' pampu ', ' broadcast ']):
        return False
    open_keywords = [
        'open whatsapp', 'launch whatsapp', 'start whatsapp', 'activate whatsapp',
        'open wa', 'open whatsapp web', 'whatsapp open', 'whatsapp kholo',
        'whatsapp open cheyi', 'whatsapp open cheyyi', 'whatsapp chupinchu', 'whatsapp start cheyi',
        'open my whatsapp', 'bring up whatsapp', 'whatsapp web open'
    ]
    if any(k in m for k in open_keywords):
        return True
    tokens = re.findall(r'[a-zA-Z0-9]+', m)
    if 'whatsapp' in tokens:
        open_verbs = {'open', 'launch', 'start', 'bring', 'navigate', 'kholo', 'cheyi'}
        if any(v in tokens for v in open_verbs):
            if 'to' in tokens:
                to_idx = tokens.index('to')
                if to_idx + 1 < len(tokens) and tokens[to_idx + 1] not in {'whatsapp', 'web', 'chrome', 'the'}:
                    return False
            return True
    return False


def _clean_contact_name(contact: str) -> str:
    for junk in [' on whatsapp', ' in whatsapp', ' via whatsapp', ' on web', ' in web', ' please', ' urgent', ' urgently']:
        if contact.lower().endswith(junk):
            contact = contact[:-len(junk)].strip()
    return contact.strip()


def parse_whatsapp_request(user_msg: str) -> tuple[str, str]:
    """
    Extract contact name and message body from natural conversational WhatsApp commands.
    """
    msg_clean = user_msg.strip()
    # Pattern 1: to <contact> saying <message>
    m = re.search(r'\bto\s+([a-zA-Z0-9\s_\.\-\+]+?)\s+saying\s+(.+)$', msg_clean, re.IGNORECASE)
    if m:
        return _clean_contact_name(m.group(1)), m.group(2).strip()
    # Pattern 2: to <contact>\s*:\s*<message>
    m = re.search(r'\bto\s+([a-zA-Z0-9\s_\.\-\+]+?)\s*:\s*(.+)$', msg_clean, re.IGNORECASE)
    if m:
        return _clean_contact_name(m.group(1)), m.group(2).strip()
    # Pattern 3: to <contact> that <message>
    m = re.search(r'\bto\s+([a-zA-Z0-9\s_\.\-\+]+?)\s+that\s+(.+)$', msg_clean, re.IGNORECASE)
    if m:
        return _clean_contact_name(m.group(1)), m.group(2).strip()
    # Pattern 4: send <message> to <contact>
    m = re.search(r'\bsend\s+(.+?)\s+to\s+([a-zA-Z0-9\s_\.\-\+]+?)(?:\s+on\s+whatsapp|\s+in\s+whatsapp|\s+via\s+whatsapp|$)', msg_clean, re.IGNORECASE)
    if m:
        msg_body, contact = m.group(1).strip(), m.group(2).strip()
        msg_body = re.sub(r'^(?:a\s+)?whatsapp\s+message\s+(?:saying\s+)?', '', msg_body, flags=re.IGNORECASE)
        msg_body = re.sub(r'^(?:a\s+)?message\s+(?:saying\s+)?', '', msg_body, flags=re.IGNORECASE)
        if msg_body.lower() in {'message', 'whatsapp message', 'a message', 'a whatsapp message', ''}:
            msg_body = 'Hello!'
        return _clean_contact_name(contact), msg_body.strip()
    # Pattern 5: send message to <contact>
    m = re.search(r'\bto\s+([a-zA-Z0-9\s_\.\-\+]+?)(?:\s+on\s+whatsapp|\s+in\s+whatsapp|\s+via\s+whatsapp|$)', msg_clean, re.IGNORECASE)
    if m:
        return _clean_contact_name(m.group(1)), 'Hello!'
    return '', ''


def classify_intent(user_msg: str, current_agent: str = "main") -> str:
    """
    Intelligent Intent Classifier:
    Accurately distinguishes between conversational chatter/questions and
    concrete imperative automation commands.
    """
    msg_lower = user_msg.lower().strip()

    # 1. Explicit slash / switch commands
    if any(w in msg_lower for w in ["/desktop", "desktop agent", "switch to desktop"]):
        return "desktop"
    if any(w in msg_lower for w in ["/web", "/browser", "web agent", "switch to web"]):
        return "web"
    if any(w in msg_lower for w in ["/research", "research agent", "switch to research"]):
        return "research"
    if any(w in msg_lower for w in ["/chat", "/chatbot", "chatbot agent", "switch to chatbot"]):
        return "chatbot"
    if any(w in msg_lower for w in ["/computer", "computer agent", "switch to computer", "computer use"]):
        return "computer"
    if any(w in msg_lower for w in ["/main", "/orchestrator", "main agent", "switch to main"]):
        return "main"

    # 2. Check for Web actions FIRST (including Telugu & polite requests)
    web_actions = [
        "whatsapp", "canva", "instagram", "activate auto", "start auto",
        "stop auto", "auto responder", "auto chat", "send message to", "message to",
        "search google", "browse to"
    ]
    if any(k in msg_lower for k in web_actions):
        return "web"

    # 3. Check for Desktop actions (calc, notepad, files, lock, mute)
    desktop_targets = [
        "calculator", "calc", "notepad", "assignment", "paint", "mspaint",
        "task manager", "taskmgr", "command prompt", "powershell", "terminal",
        "file explorer", "explorer", "local file", "python assignment", "system info",
        "screenshot", "screen capture", "capture screen", "volume", "lock screen", "lock workstation",
        "lock pc", "camera", "settings"
    ]
    if any(target in msg_lower for target in desktop_targets):
        return "desktop"

    # 4. Research triggers
    research_triggers = [
        "presentation outline", "slide outline", "synthesize topic",
        "academic research outline", "syllabus research", "research paper", "deep research"
    ]
    if any(k in msg_lower for k in research_triggers):
        return "research"

    # 5. Conversational & Question Filter for chatbot
    if current_agent == "chatbot":
        return "chatbot"

    return current_agent


def detect_language_and_voice(text: str) -> str:
    """
    Intelligently detect language and script from text to select the best neural voice.
    Supports Telugu (te-IN-MohanNeural), Hindi (hi-IN-MadhurNeural), Tamil, Kannada,
    Malayalam, Bengali, Gujarati, Asian, and European languages, defaulting to en-IN-PrabhatNeural.
    """
    if not text:
        return DEFAULT_VOICE

    cleaned = text.strip()
    cleaned_lower = cleaned.lower()

    # 1. Unicode Script Range Detection
    # Telugu: U+0C00 - U+0C7F
    if any('\u0c00' <= ch <= '\u0c7f' for ch in cleaned):
        return "te-IN-MohanNeural"

    # Devanagari / Hindi: U+0900 - U+097F
    if any('\u0900' <= ch <= '\u097f' for ch in cleaned):
        return "hi-IN-MadhurNeural"

    # Tamil: U+0B80 - U+0BFF
    if any('\u0b80' <= ch <= '\u0bff' for ch in cleaned):
        return "ta-IN-ValluvarNeural"

    # Kannada: U+0C80 - U+0CFF
    if any('\u0c80' <= ch <= '\u0cff' for ch in cleaned):
        return "kn-IN-GaganNeural"

    # Malayalam: U+0D00 - U+0D7F
    if any('\u0d00' <= ch <= '\u0d7f' for ch in cleaned):
        return "ml-IN-MidhunNeural"

    # Bengali: U+0980 - U+09FF
    if any('\u0980' <= ch <= '\u09ff' for ch in cleaned):
        return "bn-IN-BashkarNeural"

    # Gujarati: U+0A80 - U+0AFF
    if any('\u0a80' <= ch <= '\u0aff' for ch in cleaned):
        return "gu-IN-NiranjanNeural"

    # Japanese: Hiragana/Katakana U+3040 - U+30FF
    if any('\u3040' <= ch <= '\u30ff' for ch in cleaned):
        return "ja-JP-KeitaNeural"

    # Chinese: U+4E00 - U+9FFF
    if any('\u4e00' <= ch <= '\u9fff' for ch in cleaned):
        return "zh-CN-YunxiNeural"

    # Arabic / Urdu: U+0600 - U+06FF
    if any('\u0600' <= ch <= '\u06ff' for ch in cleaned):
        return "ur-IN-SalmanNeural"

    # Russian / Cyrillic: U+0400 - U+04FF
    if any('\u0400' <= ch <= '\u04ff' for ch in cleaned):
        return "ru-RU-DmitryNeural"

    # 2. Romanized Telugu / Tanglish Keyword Detection
    tanglish_patterns = [
        r'\b(namaskaram|namaste|bagunara|bagunnara|bagunnam|ela unnav|ela unnaru)\b',
        r'\b(enti bro|emiti|cheppandi|cheppu|pampandi|pampinchu|chudandi|chudu)\b',
        r'\b(telugulo|telugu lo|matladu|matladandi|avunu|ledu|kadhu|kadu|babu|anna)\b',
        r'\b(em chestunnav|eppudu|ekkada|enduku|nenu|meeru|manaki)\b'
    ]
    if any(re.search(pat, cleaned_lower) for pat in tanglish_patterns):
        return "te-IN-MohanNeural"

    return DEFAULT_VOICE


async def generate_speech_file(text: str, voice: Optional[str] = None) -> Optional[str]:
    """
    Generate speech matching Dhanush's voice or target language voice.
    Supports native Telugu (te-IN-MohanNeural), Hindi, English, and all world languages.
    Automatically detects language when voice is omitted.
    Returns relative URL path: /assets/audio_cache/<hash>.[wav|mp3]
    """
    cleaned_text = text.strip()
    if not cleaned_text:
        return None

    target_voice = voice or detect_language_and_voice(cleaned_text)

    try:
        from server.voice_service import synthesize_dhanush_voice
        cloned_audio_url = await synthesize_dhanush_voice(cleaned_text, voice=target_voice)
        if cloned_audio_url:
            return cloned_audio_url
    except Exception as voice_err:
        print(f"⚠️ Neural voice clone fallback: {voice_err}")

    # Fallback to Edge-TTS with target voice at maximum volume
    try:
        text_hash = hashlib.md5(f"maxvol_{target_voice}:{cleaned_text}".encode("utf-8")).hexdigest()
        filename = f"{text_hash}.mp3"
        filepath = AUDIO_CACHE_DIR / filename

        if not filepath.exists() or filepath.stat().st_size == 0:
            communicate = edge_tts.Communicate(cleaned_text, voice=target_voice, volume="+100%")
            await communicate.save(str(filepath))

        return f"/assets/audio_cache/{filename}"
    except Exception as e:
        print(f"⚠️ TTS generation warning ({target_voice}): {e}")
        return None


def get_or_create_visible_engine() -> BrowserEngine:
    """
    Launch or return the real visible Chrome browser with Dhanush's saved profile.
    Automations run in real Chrome as requested by the user.
    """
    global engine_instance, registry_instance
    if engine_instance is None or not engine_instance.is_ready():
        if engine_instance is not None:
            try:
                engine_instance.close()
            except Exception:
                pass
            engine_instance = None

        from octopus_ai.main import prepare_main_profile
        user_data_dir, profile_label = prepare_main_profile()
        print(f"🚀 Launching Real Visible Chrome (Profile: {profile_label})...")
        engine_instance = BrowserEngine(
            headless=False,
            user_data_dir=user_data_dir,
            profile_directory="Default"
        )
        res = engine_instance.initialize()
        if res.get("success"):
            driver = engine_instance.get_driver()
            preview_manager.set_driver(driver)
            registry_instance = create_default_registry(driver=driver)
        else:
            print(f"⚠️ Chrome launch error: {res.get('error')}")
            try:
                engine_instance.close()
            except Exception:
                pass
            engine_instance = None
    return engine_instance


# Background WhatsApp Auto-Responder State
whatsapp_auto_responder_instance: Optional[Any] = None
whatsapp_auto_responder_thread: Optional[Any] = None


def start_whatsapp_auto_responder() -> tuple[bool, str]:
    """
    Launch WhatsApp Web in visible Chrome and start the WhatsAppAutoResponder loop
    in a dedicated background daemon thread.
    """
    global whatsapp_auto_responder_instance, whatsapp_auto_responder_thread
    if whatsapp_auto_responder_thread and whatsapp_auto_responder_thread.is_alive():
        if whatsapp_auto_responder_instance and whatsapp_auto_responder_instance.is_running:
            return True, "WhatsApp Auto-Responder is already running."

    try:
        eng = get_or_create_visible_engine()
        if not eng or not eng.get_driver():
            return False, "Could not launch visible Chrome browser."

        driver = eng.get_driver()
        curr_url = (driver.current_url or "").lower()
        if "web.whatsapp.com" not in curr_url:
            driver.get("https://web.whatsapp.com")
            time.sleep(2)

        from octopus_ai.agent.whatsapp_responder import WhatsAppAutoResponder
        if whatsapp_auto_responder_instance is None:
            whatsapp_auto_responder_instance = WhatsAppAutoResponder(
                driver=driver, 
                user_name="Dhanush",
                allow_group_replies=True
            )
        else:
            whatsapp_auto_responder_instance.set_driver(driver)
            whatsapp_auto_responder_instance.allow_group_replies = True

        whatsapp_auto_responder_instance.is_running = True

        def _responder_worker():
            import logging
            log = logging.getLogger("WhatsAppAutoResponderThread")
            log.info("WhatsApp Auto-Responder background thread started.")
            try:
                if not whatsapp_auto_responder_instance.is_authenticated:
                    whatsapp_auto_responder_instance.wait_for_login(timeout=60)
                
                while whatsapp_auto_responder_instance.is_running:
                    try:
                        whatsapp_auto_responder_instance.poll_once()
                        time.sleep(1.5)
                    except Exception as cycle_e:
                        err_str = str(cycle_e).lower()
                        if any(x in err_str for x in ["refused", "disconnected", "closed", "invalid session", "target machine", "connection reset"]):
                            log.info("WhatsApp browser closed or disconnected. Terminating auto-responder.")
                            whatsapp_auto_responder_instance.is_running = False
                            break
                        time.sleep(2.0)
            except Exception as outer_e:
                log.warning(f"Auto-responder worker encountered an error: {outer_e}")
            finally:
                log.info("WhatsApp Auto-Responder thread stopped.")

        import threading
        whatsapp_auto_responder_thread = threading.Thread(
            target=_responder_worker,
            daemon=True,
            name="WhatsAppAutoResponderThread"
        )
        whatsapp_auto_responder_thread.start()
        return True, "WhatsApp Auto-Responder started successfully."
    except Exception as e:
        print(f"⚠️ start_whatsapp_auto_responder notice: {e}")
        return False, str(e)


def stop_whatsapp_auto_responder() -> tuple[bool, str]:
    """Stop the background WhatsApp Auto-Responder."""
    global whatsapp_auto_responder_instance
    if whatsapp_auto_responder_instance and whatsapp_auto_responder_instance.is_running:
        whatsapp_auto_responder_instance.stop()
        return True, "WhatsApp Auto-Responder stopped."
    return False, "WhatsApp Auto-Responder was not running."


class ChatRequest(BaseModel):
    message: str
    agent: Optional[str] = None
    session_id: Optional[str] = "default"


class SelectAgentRequest(BaseModel):
    agent_id: str


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = DEFAULT_VOICE


@app.on_event("startup")
async def startup_event():
    global agent_instance, registry_instance
    try:
        agent_instance = OctopusAgent()
    except Exception as e:
        print(f"OctopusAgent init note: {e}")
    registry_instance = create_default_registry()

    # Pre-warm VoiceService (Chatterbox on GPU) and pre-generate greeting audios
    async def _prewarm_voice_and_cache():
        try:
            from server.voice_service import voice_service_instance
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, voice_service_instance.initialize)
        except Exception as e:
            print(f"[VoicePrewarm] Notice: {e}")

        for ag in AVAILABLE_AGENTS:
            await generate_speech_file(ag["greeting"])
    asyncio.create_task(_prewarm_voice_and_cache())


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    ui_path = repo_dir / "orb-ui.html"
    if ui_path.exists():
        with open(ui_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>orb-ui.html not found</h1>", status_code=404)


@app.get("/api/agents")
async def get_agents():
    """Return list of available agents for the 9-dots menu."""
    global CURRENT_AGENT
    return {
        "success": True,
        "agents": AVAILABLE_AGENTS,
        "current_agent": CURRENT_AGENT
    }


SERVER_BOOT_ID = str(uuid.uuid4())[:8]


@app.get("/api/live-status")
async def get_live_status():
    """
    Returns live server status, boot ID, and UI file modification time.
    Used by client for automatic live synchronization when code updates.
    """
    ui_path = repo_dir / "orb-ui.html"
    ui_mtime = ui_path.stat().st_mtime if ui_path.exists() else 0
    return {
        "status": "online",
        "boot_id": SERVER_BOOT_ID,
        "ui_mtime": ui_mtime,
        "current_agent": CURRENT_AGENT
    }


@app.get("/api/avatar/manifest")
async def get_avatar_manifest():
    """
    Returns available video clip libraries, durations, and tempo metadata
    for seamless, non-repeating shuffle and speech-synchronized lip movement.
    Dynamically verifies that every referenced video file exists on disk.
    """
    manifest_path = assets_dir / "videos" / "video_manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                raw_manifest = json.load(f)

            validated = {}
            for state, clips in raw_manifest.items():
                valid_clips = []
                for clip in clips:
                    file_str = clip.get("file", "")
                    # Strip leading /assets/ or assets/
                    rel_part = file_str
                    if rel_part.startswith("/assets/"):
                        rel_part = rel_part[len("/assets/"):]
                    elif rel_part.startswith("assets/"):
                        rel_part = rel_part[len("assets/"):]
                    disk_path = assets_dir / rel_part
                    if disk_path.exists() and disk_path.stat().st_size > 1000:
                        valid_clips.append(clip)
                validated[state] = valid_clips

            return {"success": True, "manifest": validated}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return {"success": False, "error": "Manifest not found"}


@app.post("/api/tts")
async def tts_endpoint(req: TTSRequest):
    """Generate or retrieve cached natural male speech audio."""
    audio_url = await generate_speech_file(req.text, req.voice or DEFAULT_VOICE)
    return {
        "success": audio_url is not None,
        "audio_url": audio_url
    }


@app.post("/api/voice/transcribe")
async def api_voice_transcribe(
    request: Request,
    file: Optional[UploadFile] = File(None),
):
    """
    Transcribe incoming voice audio using Groq Whisper model (whisper-large-v3-turbo).
    Supports multipart/form-data upload (audio/webm, audio/wav, audio/mp4, etc.)
    as well as JSON payloads containing base64 audio strings.
    """
    audio_bytes = None
    filename = "audio.webm"
    language = None

    if file is not None:
        audio_bytes = await file.read()
        filename = file.filename or "audio.webm"
    else:
        try:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                body = await request.json()
                b64 = body.get("audio_base64") or body.get("audio") or ""
                filename = body.get("filename") or "audio.webm"
                language = body.get("language")
                if b64:
                    import base64
                    if "," in b64:
                        b64 = b64.split(",", 1)[1]
                    audio_bytes = base64.b64decode(b64)
            else:
                raw = await request.body()
                if raw:
                    audio_bytes = raw
        except Exception as e:
            return {"success": False, "error": f"Audio payload parse failed: {e}", "text": ""}

    if not audio_bytes or len(audio_bytes) < 100:
        return {"success": False, "error": "No valid audio received", "text": ""}

    try:
        from octopus_ai.agent.groq_llm import GroqLLM
        llm = GroqLLM()
        text = llm.transcribe_audio(audio_bytes=audio_bytes, filename=filename, language=language)
        return {"success": bool(text and text.strip()), "text": text.strip() if text else ""}
    except Exception as err:
        return {"success": False, "error": str(err), "text": ""}



@app.post("/api/whatsapp/auto-responder/start")
async def start_auto_responder_endpoint():
    """Start WhatsApp Auto-Responder background daemon."""
    success, msg = start_whatsapp_auto_responder()
    return {"success": success, "message": msg}


@app.post("/api/whatsapp/auto-responder/stop")
async def stop_auto_responder_endpoint():
    """Stop WhatsApp Auto-Responder background daemon."""
    success, msg = stop_whatsapp_auto_responder()
    return {"success": success, "message": msg}


@app.get("/api/whatsapp/auto-responder/status")
async def auto_responder_status_endpoint():
    """Get status of WhatsApp Auto-Responder."""
    global whatsapp_auto_responder_instance, whatsapp_auto_responder_thread
    is_running = (
        whatsapp_auto_responder_instance is not None
        and getattr(whatsapp_auto_responder_instance, "is_running", False)
        and whatsapp_auto_responder_thread is not None
        and whatsapp_auto_responder_thread.is_alive()
    )
    res = {
        "success": True,
        "is_running": is_running,
        "active_contact": getattr(whatsapp_auto_responder_instance, "active_chat_contact", None) if whatsapp_auto_responder_instance else None,
        "inactivity_limit_seconds": 25.0
    }
    if whatsapp_auto_responder_instance:
        res["fingerprints_count"] = len(whatsapp_auto_responder_instance.replied_fingerprints)
        res["fingerprints"] = list(whatsapp_auto_responder_instance.replied_fingerprints)[-10:]
        res["sent_history"] = list(whatsapp_auto_responder_instance.sent_replies_history)[-5:]
        res["is_group"] = whatsapp_auto_responder_instance.is_group_chat()
        res["allow_group"] = whatsapp_auto_responder_instance.allow_group_replies
        try:
            res["js_inspect"] = whatsapp_auto_responder_instance._inspect_conversation_js()
        except Exception as e:
            res["js_inspect_error"] = str(e)
    return res


@app.post("/api/agent/select")
async def select_agent(req: SelectAgentRequest):
    """Set the active agent from the 9-dots menu."""
    global CURRENT_AGENT
    agent = next((a for a in AVAILABLE_AGENTS if a["id"] == req.agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    CURRENT_AGENT = req.agent_id
    greeting = agent.get("greeting", f"Activated {agent['name']}")
    audio_url = await generate_speech_file(greeting)

    return {
        "success": True,
        "current_agent": CURRENT_AGENT,
        "agent": agent,
        "message": greeting,
        "audio_url": audio_url
    }


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, background_tasks: BackgroundTasks):
    """
    User command intake with Universal Intent Classification and Multi-Agent Auto-Switching.
    Handles WhatsApp contact disambiguation multi-turn sessions.
    Executes Windows desktop commands (calc, notepad, python assignment, file management).
    Automates Chrome actions (WhatsApp, Canva, Instagram, Google).
    Synthesizes answers in Dhanush's cloned voice.
    """
    global CURRENT_AGENT, registry_instance, PENDING_SESSION_STATE
    user_msg = req.message.strip()
    active_agent = req.agent or CURRENT_AGENT
    user_lower = user_msg.lower()

    response_text = ""
    summary_text = ""
    triggered_action = None

    session_id = req.session_id or "default"
    session_state = get_session_state(session_id)

    # 1. MULTI-TURN PENDING STATE (e.g. WhatsApp contact disambiguation)
    if session_state.get("type") == "whatsapp_disambiguation":
        matches = session_state.get("matches", [])
        pending_msg = session_state.get("pending_message", "Hello!")
        selected_contact = None

        user_clean = user_lower.strip()
        for idx, match_name in enumerate(matches):
            num_str = str(idx + 1)
            parts_longer_than_2 = [part.lower() for part in match_name.split() if len(part) > 2]
            if (user_clean == num_str or
                user_clean == f"number {num_str}" or
                user_clean == f"option {num_str}" or
                (idx == 0 and "first" in user_clean) or
                (idx == 1 and "second" in user_clean) or
                (idx == 2 and "third" in user_clean) or
                match_name.lower() in user_clean or
                (parts_longer_than_2 and all(part in user_clean for part in parts_longer_than_2))):
                selected_contact = match_name
                break

        if selected_contact:
            clear_session_state(session_id)
            CURRENT_AGENT = "web"
            res = await run_whatsapp_task(contact="", message=pending_msg, selected_contact=selected_contact)
            response_text = f"Selected {selected_contact}. Message sent on WhatsApp: '{pending_msg}'"
            triggered_action = {"agent": "web", "subsystem": "whatsapp", "action": "sent", "recipient": selected_contact}
            audio_url = await generate_speech_file(response_text)
            return {
                "success": True,
                "response": response_text,
                "audio_url": audio_url,
                "current_agent": "web",
                "action": triggered_action
            }
        elif re.search(r'\b(cancel|stop|nevermind|abort|no)\b', user_clean):
            clear_session_state(session_id)
            response_text = "Cancelled WhatsApp message."
            audio_url = await generate_speech_file(response_text)
            return {
                "success": True,
                "response": response_text,
                "audio_url": audio_url,
                "current_agent": CURRENT_AGENT,
                "action": {"action": "cancelled"}
            }
        else:
            # Did not match selection, clear state and proceed to classify as new command
            clear_session_state(session_id)

    # 2. UNIVERSAL INTENT CLASSIFICATION & AGENT AUTO-SWITCHING
    target_agent = classify_intent(user_msg, active_agent)
    CURRENT_AGENT = target_agent
    active_agent = target_agent

    # 3. DIRECT AGENT SWITCH COMMANDS
    is_explicit_switch = user_lower in [
        "/main", "/orchestrator", "main agent", "switch to main",
        "/web", "/browser", "web agent", "switch to web",
        "/desktop", "desktop agent", "switch to desktop",
        "/research", "research agent", "switch to research",
        "/chat", "/chatbot", "chatbot agent", "switch to chatbot"
    ]

    if is_explicit_switch:
        greetings = {
            "main": "Main Agent active. What goal would you like me to coordinate for you?",
            "web": "Web Agent activated. Ready for WhatsApp, Canva, Instagram, and web automations.",
            "desktop": "Desktop Agent activated. Ready to control Windows apps, assignments, and files.",
            "research": "Research Agent activated. What topic would you like me to analyze or outline?",
            "chatbot": "Chatbot Agent ready. How can I help with your studies or teaching today?"
        }
        response_text = greetings.get(CURRENT_AGENT, f"{CURRENT_AGENT.capitalize()} agent ready.")
        audio_url = await generate_speech_file(response_text)
        return {
            "success": True,
            "response": response_text,
            "audio_url": audio_url,
            "current_agent": CURRENT_AGENT,
            "action": {"agent": CURRENT_AGENT, "action": "switch"}
        }

    # 4. ROUTING BASED ON CLASSIFIED AGENT
    if active_agent == "desktop":
        # Local Desktop Apps, Python Assignment in Notepad & File Operations
        try:
            d_res = await desktop_agent_instance.execute_task(user_msg)
            action_type = d_res.get("action")
            if action_type == "find_files":
                count = d_res.get("count", 0)
                response_text = f"Found {count} matching files on your computer."
                if count > 0:
                    summary_text = "\n".join(f"• {f['name']} ({f['size_kb']} KB)" for f in d_res.get("files", [])[:8])
            elif action_type == "open_notepad_with_content":
                response_text = d_res.get("message", "Created Python assignment on your Desktop and opened it in Notepad.")
            elif action_type == "launch_app":
                response_text = d_res.get("message", "Opened application on your desktop.")
            else:
                response_text = d_res.get("summary") or d_res.get("message") or "Desktop operation complete."
            triggered_action = {"agent": "desktop", "result": d_res}
        except Exception as desk_err:
            response_text = f"Desktop agent encountered a notice: {desk_err}"

    elif active_agent == "web":
        # Web Agent: WhatsApp with disambiguation, Canva, Instagram, Google Search
        if "whatsapp" in user_lower or "message" in user_lower or "broadcast" in user_lower or "ptm" in user_lower or "auto responder" in user_lower or "auto chat" in user_lower:
            is_activate_auto = any(kw in user_lower for kw in [
                "activate whatsapp", "start whatsapp auto", "activate auto responder",
                "start auto responder", "auto chat on whatsapp", "auto-chat on whatsapp",
                "auto chat whatsapp", "whatsapp auto responder", "turn on whatsapp auto",
                "whatsapp activate", "whatsapp auto chat", "whatsapp on cheyi", "whatsapp activate cheyi",
                "/activate whatsapp", "/autoresponder", "/whatsapp auto"
            ])
            is_stop_auto = any(kw in user_lower for kw in [
                "stop whatsapp auto", "deactivate whatsapp", "stop auto responder",
                "turn off whatsapp auto", "disable whatsapp auto", "stop auto chat",
                "stop whatsapp"
            ])

            if is_activate_auto:
                start_whatsapp_auto_responder()
                response_text = "WhatsApp Web activated in auto-responder mode. I will automatically chat with incoming messages using conversation context and stay on each chat until 25 seconds of silence."
                triggered_action = {"agent": "web", "subsystem": "whatsapp", "action": "auto_responder_activated"}
            elif is_stop_auto:
                stop_whatsapp_auto_responder()
                response_text = "WhatsApp Auto-Responder has been stopped."
                triggered_action = {"agent": "web", "subsystem": "whatsapp", "action": "auto_responder_stopped"}
            elif "broadcast" in user_lower or "ptm" in user_lower or "groups" in user_lower:
                try:
                    plan = await master_orchestrator_instance.optimize_and_decompose(user_msg)
                    exec_res = await master_orchestrator_instance.execute_plan(plan, user_msg)
                    response_text = sanitize_speech_response(exec_res.get("spoken_response") or "Broadcast sent on WhatsApp.")
                    triggered_action = {"agent": "web", "subsystem": "whatsapp", "action": "broadcast"}
                except Exception:
                    response_text = "Opening WhatsApp to send broadcast update."
                    background_tasks.add_task(run_whatsapp_task, "", "")
            elif is_whatsapp_open_request(user_msg):
                response_text = "Opening WhatsApp Web in Chrome."
                triggered_action = {"agent": "web", "subsystem": "whatsapp", "action": "open"}
                background_tasks.add_task(run_whatsapp_task, "", "")
            else:
                contact, message = parse_whatsapp_request(user_msg)
                if not contact:
                    response_text = "Who would you like to message on WhatsApp? Please provide the contact or group name."
                    audio_url = await generate_speech_file(response_text)
                    return {
                        "success": True,
                        "response": response_text,
                        "audio_url": audio_url,
                        "current_agent": "web",
                        "action": {"agent": "web", "subsystem": "whatsapp", "action": "ask_contact"}
                    }

                try:
                    wa_res = await run_whatsapp_task(contact=contact, message=message)
                    if wa_res and wa_res.data and wa_res.data.get("disambiguation_required"):
                        matches = wa_res.data.get("matches", [])
                        set_session_state(session_id, {
                            "type": "whatsapp_disambiguation",
                            "matches": matches,
                            "pending_message": message,
                            "contact": contact
                        })
                        options_str = "\n".join(f"{i+1}. {m}" for i, m in enumerate(matches))
                        response_text = f"I found {len(matches)} contacts matching '{contact}':\n{options_str}\nWhich one would you like to message?"
                        triggered_action = {
                            "agent": "web",
                            "subsystem": "whatsapp",
                            "action": "disambiguate",
                            "matches": matches,
                            "choices": matches
                        }
                    elif wa_res and wa_res.success:
                        response_text = wa_res.message
                        triggered_action = {"agent": "web", "subsystem": "whatsapp", "action": "sent", "contact": contact}
                    else:
                        response_text = f"Opening WhatsApp in Chrome to message {contact}."
                        triggered_action = {"agent": "web", "subsystem": "whatsapp", "contact": contact}
                        background_tasks.add_task(run_whatsapp_task, contact, message)
                except Exception:
                    response_text = f"Opening WhatsApp in Chrome for {contact}."
                    background_tasks.add_task(run_whatsapp_task, contact, message)

        elif "canva" in user_lower or "design" in user_lower or "presentation" in user_lower:
            topic = user_msg
            for w in ["create", "design", "search", "template", "presentation", "for", "in canva", "canva"]:
                topic = topic.replace(w, "").replace(w.capitalize(), "")
            topic = topic.strip() or "presentation"
            response_text = f"Opening Canva in Chrome for '{topic}' templates."
            triggered_action = {"agent": "web", "subsystem": "canva", "query": topic}
            background_tasks.add_task(run_canva_task, topic)

        elif "instagram" in user_lower or "@" in user_msg:
            action = "profile" if "@" in user_msg else "feed"
            username = user_msg.split("@", 1)[1].split()[0].strip() if "@" in user_msg else ""
            response_text = "Opening Instagram in Chrome."
            triggered_action = {"agent": "web", "subsystem": "instagram", "username": username}
            background_tasks.add_task(run_instagram_task, action, username)

        else:
            query = user_msg
            for w in ["search", "find", "google", "look up", "browse"]:
                query = query.replace(w, "").replace(w.capitalize(), "")
            query = query.strip() or user_msg
            response_text = f"Opening Google Chrome to search for '{query}'."
            triggered_action = {"agent": "web", "query": query}
            background_tasks.add_task(run_web_task, query)

    elif active_agent == "research":
        # Topic Research & Slide Outline Generation
        try:
            if any(w in user_lower for w in ["outline", "slide", "ppt", "presentation"]):
                r_res = await research_agent_instance.generate_presentation_outline(user_msg)
                response_text = f"Generated presentation outline on {user_msg}."
                summary_text = r_res.get("outline", "")
            else:
                r_res = await research_agent_instance.research_topic(user_msg)
                response_text = f"Synthesized research for {user_msg}."
                summary_text = r_res.get("synthesis", "")
            triggered_action = {"agent": "research", "result": r_res}
        except Exception as res_err:
            response_text = f"Research agent notice: {res_err}"

    elif active_agent == "chatbot":
        # Conversational Chatbot Agent (Dhanush Persona)
        try:
            from agent.subagents.chatbot_agent import chatbot_agent_instance
            c_res = await chatbot_agent_instance.chat(user_msg)
            response_text = c_res.get("response") or "Hey! How can I help you today?"
            response_text = sanitize_speech_response(response_text)
            triggered_action = {"agent": "chatbot", "result": c_res}
        except Exception as chat_err:
            response_text = await local_llm_instance.generate_response(user_msg)
            response_text = sanitize_speech_response(response_text)
            triggered_action = {"agent": "chatbot", "fallback": True}

    elif active_agent == "computer":
        # Autonomous Computer Use (Windows-Use + Clacky)
        try:
            from computer_use import computer_agent_instance
            c_res = await computer_agent_instance.run_task(user_msg)
            response_text = c_res.get("spoken_summary") or "Computer action finished."
            logs = c_res.get("step_logs", [])
            if logs:
                summary_text = "\n".join(f"• Step {s['step']}: {s['description']} ({'OK' if s['success'] else 'Failed'})" for s in logs)
            triggered_action = {"agent": "computer", "result": c_res}
        except Exception as cu_err:
            response_text = f"Computer agent notice: {cu_err}"

    else:
        # Main Agent Orchestrator & Conversational AI
        is_question_or_chat = (
            user_lower.endswith("?") or
            any(user_lower.startswith(q) for q in [
                "why", "how", "what", "who", "where", "when", "can you tell", "can you explain",
                "explain", "tell me", "is it", "are you", "do you", "why did", "why is",
                "why does", "what is", "how do", "how does", "what are", "who is"
            ]) or
            any(w in user_lower for w in [
                "chating", "chatting", "speaking", "talking", "sending terminal", "commands not the user",
                "instead of speaking", "don't reply", "dont reply", "group chat", "multi message",
                "tell a joke", "who are you", "what's up", "whats up", "how are you",
                "good morning", "good evening", "hi bro", "hey bro", "ela unnav", "cheppu bro"
            ])
        )

        is_actionable = False
        if not is_question_or_chat:
            is_actionable = any(kw in user_lower for kw in [
                "open whatsapp", "send whatsapp", "whatsapp broadcast", "open canva", "open instagram",
                "ptm update", "find file", "local file", "organize file", "move file", "touch file",
                "search google", "presentation deck", "create presentation",
                "open notepad", "open calculator", "open calc", "launch app", "open app",
                "run powershell", "execute terminal", "take screenshot", "lock workstation", "lock pc",
                "bring to front", "switch to", "inspect ui"
            ])

        if is_actionable:
            try:
                from octopus_ai.agent.orchestrator import master_orchestrator_instance
                plan = await master_orchestrator_instance.optimize_and_decompose(user_msg)
                exec_res = await master_orchestrator_instance.execute_plan(plan, user_msg)
                raw_spoken = exec_res.get("spoken_response") or "I've organized the task across your sub-agents."
                response_text = sanitize_speech_response(raw_spoken)
                bullets = exec_res.get("summary_bullets", [])
                if bullets:
                    summary_text = "\n".join(f"• {b}" for b in bullets)
                triggered_action = {"agent": "main", "plan": plan, "results": exec_res.get("subagent_results")}
            except Exception:
                response_text = await local_llm_instance.generate_response(user_msg)
                response_text = sanitize_speech_response(response_text)
                triggered_action = {"agent": "main", "action": "fallback_chat"}
        else:
            response_text = await local_llm_instance.generate_response(user_msg)
            response_text = sanitize_speech_response(response_text)
            triggered_action = {"agent": "main", "action": "chat"}

    # 5. SYNTHESIZE SPEECH USING DHANUSH'S CLONED VOICE
    response_text = sanitize_speech_response(response_text)
    audio_url = await generate_speech_file(response_text)

    choices = None
    if isinstance(triggered_action, dict):
        choices = triggered_action.get("choices") or triggered_action.get("matches")

    return {
        "success": True,
        "response": response_text,
        "summary": summary_text,
        "audio_url": audio_url,
        "current_agent": CURRENT_AGENT,
        "action": triggered_action,
        "choices": choices
    }


# =============================================================================
# STUDIO VIDEO AVATAR CONFIGURATION
# =============================================================================
@app.get("/api/avatar/mode")
async def get_avatar_mode():
    """Return avatar mode (Studio Video)."""
    return {"mode": "video", "available_modes": ["video"]}



# Background tasks that launch the real Chrome browser:
def _sync_run_whatsapp(contact: str, message: str, selected_contact: str = ""):
    eng = get_or_create_visible_engine()
    if eng and eng.get_driver():
        from octopus_ai.automations.web.whatsapp import WhatsAppAutomation
        auto = WhatsAppAutomation(driver=eng.get_driver())
        return asyncio.run(auto.run({
            "action": "send" if ((contact or selected_contact) and message) else "open",
            "contact": contact,
            "message": message,
            "selected_contact": selected_contact
        }))
    return None


async def run_whatsapp_task(contact: str, message: str, selected_contact: str = ""):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        whatsapp_executor,
        _sync_run_whatsapp,
        contact,
        message,
        selected_contact
    )


async def run_canva_task(query: str):
    eng = get_or_create_visible_engine()
    if eng and eng.get_driver():
        from octopus_ai.automations.web.canva import CanvaAutomation
        auto = CanvaAutomation(driver=eng.get_driver())
        await auto.run({"query": query})


async def run_instagram_task(action: str, username: str):
    eng = get_or_create_visible_engine()
    if eng and eng.get_driver():
        from octopus_ai.automations.web.instagram import InstagramAutomation
        auto = InstagramAutomation(driver=eng.get_driver())
        await auto.run({"action": action, "username": username})


async def run_web_task(query: str):
    eng = get_or_create_visible_engine()
    if eng and eng.get_driver():
        if not query or query.strip() == "":
            eng.get_driver().get("https://www.google.com")
            return
        from octopus_ai.automations.web.browser_task import BrowserTaskAutomation
        auto = BrowserTaskAutomation(driver=eng.get_driver())
        await auto.run({"query": query})


# =============================================================================
# PACIFIC COMPUTER USE APIS (Windows-Use + Clacky Integration)
# =============================================================================

class ComputerExecuteRequest(BaseModel):
    task: Optional[str] = None
    tool: Optional[str] = None
    params: Optional[Dict[str, Any]] = None


class ComputerConfirmRequest(BaseModel):
    confirmation_id: str
    approved: bool


@app.post("/api/computer/execute")
async def api_computer_execute(req: ComputerExecuteRequest):
    """Execute a multi-step task or an atomic computer-use tool."""
    from computer_use import computer_agent_instance
    if req.tool:
        res = computer_agent_instance.execute_action(req.tool, req.params or {})
        return res.to_dict()
    elif req.task:
        return await computer_agent_instance.run_task(req.task)
    raise HTTPException(status_code=400, detail="Must provide 'task' or 'tool'")


@app.get("/api/computer/observe")
async def api_computer_observe(include_elements: bool = True):
    """Capture live observation of active window, open windows, and accessibility tree."""
    from computer_use import computer_agent_instance
    obs = computer_agent_instance.observe(include_elements=include_elements)
    return obs.to_dict(include_elements=include_elements)


@app.get("/api/computer/status")
async def api_computer_status():
    """Get active computer task, emergency stop status, and execution history."""
    from computer_use.bridge import bridge_client
    return bridge_client.get_status()


@app.post("/api/computer/stop")
async def api_computer_stop():
    """Trigger emergency stop (ESC) immediately halting all computer use activity."""
    from computer_use.bridge import bridge_client
    return bridge_client.emergency_stop("API / UI Emergency Stop")


@app.post("/api/computer/reset")
async def api_computer_reset():
    """Reset abort state to allow new computer tasks."""
    from computer_use.bridge import bridge_client
    return bridge_client.reset_state()


@app.post("/api/computer/confirm")
async def api_computer_confirm(req: ComputerConfirmRequest):
    """Approve or reject an action requiring user confirmation."""
    from computer_use import policy_engine
    act = policy_engine.resolve_confirmation(req.confirmation_id, req.approved)
    if act:
        from computer_use import computer_router
        res = computer_router.execute(act)
        return {"confirmed": True, "result": res.to_dict()}
    return {"confirmed": False, "message": "Confirmation not found or rejected"}


@app.get("/api/computer/routines")
async def api_computer_routines():
    """List saved Clacky automation routines."""
    from computer_use import clacky_adapter
    return {"routines": clacky_adapter.list_routines()}


@app.get("/api/computer/events")
async def api_computer_events(request: Request):
    """Server-Sent Events (SSE) streaming real-time computer events, visual pointing, and status."""
    from computer_use.events import event_bus

    async def event_generator():
        queue = asyncio.Queue()

        def on_event(evt):
            try:
                queue.put_nowait(evt)
            except Exception:
                pass

        event_bus.subscribe(None, on_event)
        try:
            while not await request.is_disconnected():
                try:
                    evt = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(evt.to_dict())}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            event_bus.unsubscribe(None, on_event)

    return StreamingResponse(event_generator(), media_type="text/event-stream")