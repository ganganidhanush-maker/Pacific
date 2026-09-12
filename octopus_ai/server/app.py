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
CURRENT_AGENT = "main"

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
    User command intake.
    Handles slash commands (/main, /web, /whatsapp, /canva, /instagram) and natural phrases.
    Routes general conversation to the Local LLM in Main Agent mode.
    Automates Chrome actions in respective automation modes.
    Synthesizes answers in Dhanush's cloned voice.
    """
    global CURRENT_AGENT, registry_instance
    user_msg = req.message.strip()
    active_agent = req.agent or CURRENT_AGENT
    user_lower = user_msg.lower()

    response_text = ""
    triggered_action = None

    # 1. UNIVERSAL COMMAND / AGENT SWITCH DETECTION
    # Slash commands or explicit switch phrases
    is_main_cmd = user_lower in ["/main", "/orchestrator", "main agent", "open main agent", "switch to main agent", "switch to main"]
    is_web_cmd = user_lower in ["/web", "/browser", "web agent", "open web agent", "switch to web agent", "switch to web"]
    is_desktop_cmd = user_lower in ["/desktop", "desktop agent", "open desktop agent", "switch to desktop agent", "switch to desktop"]
    is_research_cmd = user_lower in ["/research", "research agent", "open research agent", "switch to research agent", "switch to research"]
    is_chatbot_cmd = user_lower in ["/chat", "/chatbot", "chatbot agent", "open chatbot agent", "switch to chatbot agent", "switch to chatbot"]

    # Shortcuts for web platforms
    is_wa_cmd = user_lower in ["/whatsapp", "/wa", "whatsapp agent", "switch to whatsapp"]
    is_wa_open = user_lower in ["open whatsapp", "open whatsapp web", "launch whatsapp"]
    is_canva_cmd = user_lower in ["/canva", "/design", "canva agent", "switch to canva"]
    is_canva_open = user_lower in ["open canva", "launch canva"]
    is_ig_cmd = user_lower in ["/instagram", "/ig", "/insta", "instagram agent", "switch to instagram"]
    is_ig_open = user_lower in ["open instagram", "launch instagram"]
    is_web_open = user_lower in ["open browser", "open web", "launch chrome", "open chrome"]

    if is_main_cmd:
        CURRENT_AGENT = "main"
        response_text = "Main Agent active. What goal would you like me to coordinate for you?"
        audio_url = await generate_speech_file(response_text)
        return {"success": True, "response": response_text, "audio_url": audio_url, "current_agent": "main", "action": {"agent": "main", "action": "switch"}}

    elif is_desktop_cmd:
        CURRENT_AGENT = "desktop"
        response_text = "Desktop Agent activated. Ready to search, move, and organize your local files."
        audio_url = await generate_speech_file(response_text)
        return {"success": True, "response": response_text, "audio_url": audio_url, "current_agent": "desktop", "action": {"agent": "desktop", "action": "switch"}}

    elif is_research_cmd:
        CURRENT_AGENT = "research"
        response_text = "Research Agent activated. What topic would you like me to analyze or outline?"
        audio_url = await generate_speech_file(response_text)
        return {"success": True, "response": response_text, "audio_url": audio_url, "current_agent": "research", "action": {"agent": "research", "action": "switch"}}

    elif is_chatbot_cmd:
        CURRENT_AGENT = "chatbot"
        response_text = "Chatbot Agent ready. How can I help with your studies or teaching today?"
        audio_url = await generate_speech_file(response_text)
        return {"success": True, "response": response_text, "audio_url": audio_url, "current_agent": "chatbot", "action": {"agent": "chatbot", "action": "switch"}}

    elif is_wa_open:
        CURRENT_AGENT = "web"
        response_text = "Opening WhatsApp Web in Chrome."
        triggered_action = {"agent": "web", "subsystem": "whatsapp", "action": "open"}
        background_tasks.add_task(run_whatsapp_task, "", "")
        audio_url = await generate_speech_file(response_text)
        return {"success": True, "response": response_text, "audio_url": audio_url, "current_agent": "web", "action": triggered_action}

    elif is_wa_cmd:
        CURRENT_AGENT = "web"
        response_text = "Web Agent active with WhatsApp focus. Tell me your message or groups to update."
        audio_url = await generate_speech_file(response_text)
        return {"success": True, "response": response_text, "audio_url": audio_url, "current_agent": "web", "action": {"agent": "web", "focus": "whatsapp"}}

    elif is_canva_open:
        CURRENT_AGENT = "web"
        response_text = "Opening Canva in Chrome."
        triggered_action = {"agent": "web", "subsystem": "canva", "action": "open"}
        background_tasks.add_task(run_canva_task, "presentation")
        audio_url = await generate_speech_file(response_text)
        return {"success": True, "response": response_text, "audio_url": audio_url, "current_agent": "web", "action": triggered_action}

    elif is_canva_cmd:
        CURRENT_AGENT = "web"
        response_text = "Web Agent active with Canva focus. What presentation should we create?"
        audio_url = await generate_speech_file(response_text)
        return {"success": True, "response": response_text, "audio_url": audio_url, "current_agent": "web", "action": {"agent": "web", "focus": "canva"}}

    elif is_ig_open:
        CURRENT_AGENT = "web"
        response_text = "Opening Instagram in Chrome."
        triggered_action = {"agent": "web", "subsystem": "instagram", "action": "open"}
        background_tasks.add_task(run_instagram_task, "feed", "")
        audio_url = await generate_speech_file(response_text)
        return {"success": True, "response": response_text, "audio_url": audio_url, "current_agent": "web", "action": triggered_action}

    elif is_ig_cmd:
        CURRENT_AGENT = "web"
        response_text = "Web Agent active with Instagram focus. What would you like to check?"
        audio_url = await generate_speech_file(response_text)
        return {"success": True, "response": response_text, "audio_url": audio_url, "current_agent": "web", "action": {"agent": "web", "focus": "instagram"}}

    elif is_web_open or is_web_cmd:
        CURRENT_AGENT = "web"
        response_text = "Web Agent activated. Ready for browser tasks, WhatsApp, Canva, and Google."
        if is_web_open:
            background_tasks.add_task(run_web_task, "")
        audio_url = await generate_speech_file(response_text)
        return {"success": True, "response": response_text, "audio_url": audio_url, "current_agent": "web", "action": {"agent": "web", "action": "switch"}}

    # 2. ROUTING BASED ON ACTIVE AGENT
    summary_text = ""

    if active_agent == "main":
        # Check if the user message is an actionable automation task vs general conversation
        is_actionable = any(kw in user_lower for kw in [
            "whatsapp", "canva", "instagram", "broadcast", 
            "ptm", "find file", "local file", "organize file", 
            "move file", "touch file", "open canva", "open whatsapp", "open instagram",
            "search google", "presentation deck", "create presentation"
        ])

        if is_actionable:
            # Full Multi-Agent Prompt Optimization & Task Decomposition
            try:
                plan = await master_orchestrator_instance.optimize_and_decompose(user_msg)
                exec_res = await master_orchestrator_instance.execute_plan(plan, user_msg)
                raw_spoken = exec_res.get("spoken_response") or "I've organized the task across your sub-agents."
                response_text = sanitize_speech_response(raw_spoken)
                bullets = exec_res.get("summary_bullets", [])
                if bullets:
                    summary_text = "\n".join(f"• {b}" for b in bullets)
                triggered_action = {"agent": "main", "plan": plan, "results": exec_res.get("subagent_results")}
            except Exception as orch_err:
                response_text = await local_llm_instance.generate_response(user_msg)
                response_text = sanitize_speech_response(response_text)
                triggered_action = {"agent": "main", "action": "fallback_chat"}
        else:
            # Direct conversational response to what the user wants!
            response_text = await local_llm_instance.generate_response(user_msg)
            response_text = sanitize_speech_response(response_text)
            triggered_action = {"agent": "main", "action": "chat"}

    elif active_agent == "desktop":
        # Local Desktop File & OS Operations
        try:
            d_res = await desktop_agent_instance.execute_task(user_msg)
            if d_res.get("action") == "find_files":
                count = d_res.get("count", 0)
                response_text = f"Found {count} matching files on your computer."
                if count > 0:
                    summary_text = "\n".join(f"• {f['name']} ({f['size_kb']} KB)" for f in d_res.get("files", [])[:8])
            else:
                response_text = d_res.get("summary") or d_res.get("message") or "Desktop operation complete."
            triggered_action = {"agent": "desktop", "result": d_res}
        except Exception as desk_err:
            response_text = f"Desktop agent encountered a notice: {desk_err}"

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
        except Exception as chat_err:
            response_text = await local_llm_instance.generate_response(user_msg)

    else:
        # Default: Web Agent (WhatsApp, Canva, Instagram, Google)
        if "whatsapp" in user_lower or "message" in user_lower:
            contact = ""
            message = ""
            if "to " in user_lower:
                parts = user_msg.split("to ", 1)[1]
                if ":" in parts:
                    contact, message = parts.split(":", 1)
                elif " saying " in parts:
                    contact, message = parts.split(" saying ", 1)
                else:
                    contact = parts.strip()
                    message = "Hello!"
            else:
                contact = user_msg.strip()
            response_text = f"Opening WhatsApp in Chrome for {contact}."
            triggered_action = {"agent": "web", "subsystem": "whatsapp", "contact": contact}
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
            response_text = f"Opening Instagram in Chrome."
            triggered_action = {"agent": "web", "subsystem": "instagram", "username": username}
            background_tasks.add_task(run_instagram_task, action, username)

        else:
            query = user_msg
            for w in ["search", "find", "google", "look up"]:
                query = query.replace(w, "").replace(w.capitalize(), "")
            query = query.strip() or user_msg
            response_text = f"Opening Google Chrome to search for '{query}'."
            triggered_action = {"agent": "web", "query": query}
            background_tasks.add_task(run_web_task, query)
        background_tasks.add_task(run_web_task, query)

    # 3. SYNTHESIZE SPEECH USING DHANUSH'S CLONED VOICE
    response_text = sanitize_speech_response(response_text)
    audio_url = await generate_speech_file(response_text)

    return {
        "success": True,
        "response": response_text,
        "audio_url": audio_url,
        "current_agent": CURRENT_AGENT,
        "action": triggered_action
    }


# Background tasks that launch the real Chrome browser:
async def run_whatsapp_task(contact: str, message: str):
    eng = get_or_create_visible_engine()
    if eng and eng.get_driver():
        from octopus_ai.automations.web.whatsapp import WhatsAppAutomation
        auto = WhatsAppAutomation(driver=eng.get_driver())
        await auto.run({"action": "send" if (contact and message) else "open", "contact": contact, "message": message})


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