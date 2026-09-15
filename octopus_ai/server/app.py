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

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
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
from octopus_ai.main import prepare_main_profile
from server.local_llm_service import local_llm_instance, sanitize_speech_response
from octopus_ai.agent.orchestrator import master_orchestrator_instance
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
    }
]



def classify_intent(user_msg: str, current_agent: str = "main") -> str:
    """
    Intelligent Intent Classifier:
    Detects target agent from natural language keywords and commands.
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
    if any(w in msg_lower for w in ["/main", "/orchestrator", "main agent", "switch to main"]):
        return "main"

    # 2. Desktop actions: Calculator, Notepad, assignment, Paint, Task Manager, file commands
    desktop_triggers = [
        "calculator", "calc", "notepad", "assignment", "paint", "mspaint",
        "task manager", "taskmgr", "command prompt", "powershell", "terminal",
        "file explorer", "explorer", "find file", "search file", "organize file",
        "move file", "touch file", "local file", "open new notepad", "write the python assignment",
        "python assignment", "system info", "tasklist", "pdf", "documents", "downloads",
        "screenshot", "screen capture", "capture screen", "snip", "battery",
        "mute", "unmute", "volume", "lock screen", "lock computer", "lock workstation",
        "lock pc", "lock windows", "camera", "settings"
    ]
    if (any(k in msg_lower for k in desktop_triggers) or
        ("find" in msg_lower and ("file" in msg_lower or "doc" in msg_lower or "pdf" in msg_lower)) or
        ("search" in msg_lower and ("file" in msg_lower or "doc" in msg_lower or "pdf" in msg_lower))):
        return "desktop"


    # 3. Web actions: WhatsApp, Canva, Instagram, Google, browser
    web_triggers = [
        "whatsapp", "canva", "instagram", "send message to", "message to",
        "search google", "google search", "browse to", "open url", "youtube",
        "open browser", "open chrome", "launch chrome", "broadcast", "ptm",
        "open whatsapp", "open canva", "open instagram"
    ]
    if any(k in msg_lower for k in web_triggers):
        return "web"

    # 4. Research actions: slide outline, literature, study research
    research_triggers = [
        "research", "slide outline", "presentation outline", "synthesize topic",
        "syllabus", "academic research", "literature"
    ]
    if any(k in msg_lower for k in research_triggers):
        return "research"

    # 5. Chatbot actions
    chatbot_triggers = [
        "explain", "teach me", "tutor", "quiz me", "lesson plan"
    ]
    if any(k in msg_lower for k in chatbot_triggers) and current_agent == "chatbot":
        return "chatbot"

    return current_agent


def parse_whatsapp_request(user_msg: str) -> tuple:
    """
    Extract contact name and message from commands while preserving original casing.
    """
    msg_lower = user_msg.lower()
    contact = ""
    message = ""

    to_idx = msg_lower.find("to ")
    if to_idx != -1:
        after_to = user_msg[to_idx + 3:]
        after_to_lower = msg_lower[to_idx + 3:]

        saying_idx = after_to_lower.find(" saying ")
        colon_idx = after_to.find(":")
        that_idx = after_to_lower.find(" that ")

        if saying_idx != -1:
            contact = after_to[:saying_idx]
            message = after_to[saying_idx + len(" saying "):]
        elif colon_idx != -1:
            contact = after_to[:colon_idx]
            message = after_to[colon_idx + 1:]
        elif that_idx != -1:
            contact = after_to[:that_idx]
            message = after_to[that_idx + len(" that "):]
        else:
            cleaned = after_to
            cleaned_lower = after_to_lower
            for kw in [" on whatsapp", " in whatsapp", " in web", " on web"]:
                kw_idx = cleaned_lower.find(kw)
                if kw_idx != -1:
                    cleaned = cleaned[:kw_idx] + cleaned[kw_idx + len(kw):]
                    cleaned_lower = cleaned.lower()
            and_idx = cleaned_lower.find(" and ")
            if and_idx != -1:
                cleaned = cleaned[:and_idx]
            contact = cleaned.strip()
            message = "Hello!"
    else:
        cleaned = user_msg
        cleaned_lower = msg_lower
        for kw in ["open whatsapp", "whatsapp web", "whatsapp", "in web", "send message", "message"]:
            while True:
                kw_idx = cleaned_lower.find(kw)
                if kw_idx != -1:
                    cleaned = cleaned[:kw_idx] + cleaned[kw_idx + len(kw):]
                    cleaned_lower = cleaned.lower()
                else:
                    break
        contact = cleaned.strip()
        message = "Hello!"

    return contact.strip(), message.strip()


async def generate_speech_file(text: str, voice: str = DEFAULT_VOICE) -> Optional[str]:
    """
    Generate speech matching Dhanush's voice using Chatterbox neural voice cloning.
    Falls back cleanly to edge-tts if neural engine is loading or busy.
    Cached by md5 hash to guarantee zero latency on repeated or common phrases.
    Returns relative URL path: /assets/audio_cache/<hash>.[wav|mp3]
    """
    cleaned_text = text.strip()
    if not cleaned_text:
        return None

    try:
        from server.voice_service import synthesize_dhanush_voice
        cloned_audio_url = await synthesize_dhanush_voice(cleaned_text)
        if cloned_audio_url:
            return cloned_audio_url
    except Exception as voice_err:
        print(f"⚠️ Neural voice clone fallback: {voice_err}")

    # Fallback to Edge-TTS if neural model is warming up
    try:
        text_hash = hashlib.md5(f"{voice}:{cleaned_text}".encode("utf-8")).hexdigest()
        filename = f"{text_hash}.mp3"
        filepath = AUDIO_CACHE_DIR / filename

        if not filepath.exists() or filepath.stat().st_size == 0:
            communicate = edge_tts.Communicate(cleaned_text, voice=voice)
            await communicate.save(str(filepath))

        return f"/assets/audio_cache/{filename}"
    except Exception as e:
        print(f"⚠️ TTS generation warning: {e}")
        return None


def get_or_create_visible_engine() -> BrowserEngine:
    """
    Launch or return the real visible Chrome browser with Dhanush's saved profile.
    Automations run in real Chrome as requested by the user.
    """
    global engine_instance, registry_instance
    if engine_instance is None or not engine_instance.is_ready():
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
    return engine_instance


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

    # Pre-generate greeting audios for instantaneous switching
    async def _precache():
        for ag in AVAILABLE_AGENTS:
            await generate_speech_file(ag["greeting"])
    asyncio.create_task(_precache())


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
    """
    manifest_path = assets_dir / "videos" / "video_manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return {"success": True, "manifest": json.load(f)}
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
        if "whatsapp" in user_lower or "message" in user_lower or "broadcast" in user_lower or "ptm" in user_lower:
            if "broadcast" in user_lower or "ptm" in user_lower or "groups" in user_lower:
                try:
                    plan = await master_orchestrator_instance.optimize_and_decompose(user_msg)
                    exec_res = await master_orchestrator_instance.execute_plan(plan, user_msg)
                    response_text = sanitize_speech_response(exec_res.get("spoken_response") or "Broadcast sent on WhatsApp.")
                    triggered_action = {"agent": "web", "subsystem": "whatsapp", "action": "broadcast"}
                except Exception:
                    response_text = "Opening WhatsApp to send broadcast update."
                    background_tasks.add_task(run_whatsapp_task, "", "")
            elif user_lower in ["open whatsapp", "open whatsapp web", "launch whatsapp", "/whatsapp", "/wa"]:
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
                        triggered_action = {"agent": "web", "subsystem": "whatsapp", "action": "disambiguate", "matches": matches}
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
        # Conversational Q&A / Tutoring
        try:
            c_res = await chatbot_agent_instance.chat(user_msg)
            response_text = c_res.get("response", "How can I help you today?")
            triggered_action = {"agent": "chatbot", "chat": True}
        except Exception:
            response_text = await local_llm_instance.generate_response(user_msg)

    else:
        # Main Agent Orchestrator & Conversational AI
        is_actionable = any(kw in user_lower for kw in [
            "whatsapp", "canva", "instagram", "broadcast", 
            "ptm", "find file", "local file", "organize file", 
            "move file", "touch file", "open canva", "open whatsapp", "open instagram",
            "search google", "presentation deck", "create presentation"
        ])

        if is_actionable:
            try:
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

    return {
        "success": True,
        "response": response_text,
        "summary": summary_text,
        "audio_url": audio_url,
        "current_agent": CURRENT_AGENT,
        "action": triggered_action
    }


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