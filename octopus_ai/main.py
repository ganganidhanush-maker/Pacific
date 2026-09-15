#!/usr/bin/env python3
"""
Octopus AI Agent - Main Entry Point

Run this script to start the Octopus AI Agent with Groq LLM integration.
The agent will automate WhatsApp, Instagram, Canva and other websites based on natural language commands.

Usage:
    python main.py
    
Environment Variables:
    GROQ_API_KEY: Your Groq API key (required)
    GROQ_MODEL: Model to use (default: llama-3.3-70b-versatile)
    BROWSER_HEADLESS: Run browser in headless mode (default: true)
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Configure utf-8 encoding for Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure repository root and package directory are in sys.path
this_dir = Path(__file__).resolve().parent
parent_dir = this_dir.parent
for p in [str(this_dir), str(parent_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Load environment variables
load_dotenv()

from octopus_ai.engine.selenium_engine import BrowserEngine
from octopus_ai.tools.browser_tools import BrowserTools
from octopus_ai.agent.agent import OctopusAgent
from octopus_ai.agent.whatsapp_responder import WhatsAppAutoResponder
from octopus_ai.interface.chat import ChatInterface
import time


def _safe_copy_tree(src: str, dst: str):
    """Safely copy a file or directory tree, skipping locked files without aborting the rest."""
    import shutil
    if not os.path.exists(src):
        return
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        for root, dirs, files in os.walk(src):
            rel_path = os.path.relpath(root, src)
            dest_dir = os.path.join(dst, rel_path)
            os.makedirs(dest_dir, exist_ok=True)
            for file in files:
                sf = os.path.join(root, file)
                df = os.path.join(dest_dir, file)
                try:
                    shutil.copy2(sf, df)
                except Exception:
                    pass
    else:
        try:
            shutil.copy2(src, dst)
        except Exception:
            pass


def prepare_main_profile() -> tuple[str, str]:
    """
    Automatically prepare and use the user's dedicated automation Chrome profile.
    Uses a dedicated AutomationData directory that retains all logins (WhatsApp, Instagram, Canva)
    permanently across reruns without overwriting them or causing Chrome DevTools conflicts.
    """
    chrome_data_env = os.environ.get("CHROME_USER_DATA_DIR")
    if chrome_data_env:
        os.makedirs(chrome_data_env, exist_ok=True)
        return chrome_data_env, "Configured Chrome Data"

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        os.makedirs(".chrome_profile", exist_ok=True)
        return ".chrome_profile", "Default Profile"

    dst_root = os.path.join(local_app_data, "Google", "Chrome", "AutomationData")
    dst_default = os.path.join(dst_root, "Default")
    
    # 1. If AutomationData already exists, DO NOT overwrite it!
    # Overwriting IndexedDB or Network files wipes active WhatsApp sessions!
    if os.path.exists(dst_default):
        for lock_name in ["SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile", "DevToolsActivePort"]:
            lock_file = os.path.join(dst_root, lock_name)
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                except Exception:
                    pass
        return dst_root, "Personal Chrome Profile (Dhanush)"

    # 2. First-time initialization only (when AutomationData does not exist yet)
    src_root = os.path.join(local_app_data, "Google", "Chrome", "User Data")
    if os.path.exists(src_root):
        os.makedirs(dst_root, exist_ok=True)
        
        # Sync Local State for DPAPI encryption key
        src_ls = os.path.join(src_root, "Local State")
        dst_ls = os.path.join(dst_root, "Local State")
        _safe_copy_tree(src_ls, dst_ls)
        
        # Initial seed of Default profile
        src_default = os.path.join(src_root, "Default")
        os.makedirs(dst_default, exist_ok=True)
        items = [
            "Network", 
            "IndexedDB", 
            "Local Storage", 
            "Session Storage", 
            "Preferences", 
            "Secure Preferences"
        ]
        for item in items:
            s = os.path.join(src_default, item)
            d = os.path.join(dst_default, item)
            _safe_copy_tree(s, d)
        
        return dst_root, "Personal Chrome Profile (Dhanush)"
    
    return ".chrome_profile", "Default Profile"



def main(initial_agent: str = "main", reload: bool = True):
    """Main entry point for Octopus AI Desktop Agent Tool."""
    try:
        from server.app import AVAILABLE_AGENTS
        import server.app as srv
        valid_ids = [a["id"] for a in AVAILABLE_AGENTS]
        if initial_agent in valid_ids:
            srv.CURRENT_AGENT = initial_agent
            print(f"[OctopusAI] Initial active agent set to: {initial_agent.upper()}")
    except Exception as e:
        print(f"[OctopusAI] Agent init notice: {e}")

    from octopus_ai.interface.desktop_app import run_desktop_app
    run_desktop_app(reload=reload)


def run_demo():
    """Run a quick demo of the agent capabilities."""
    print("\n" + "=" * 60)
    print("              OCTOPUS AI DEMO MODE")
    print("=" * 60)
    
    # Test without actual browser automation
    from octopus_ai.agent.groq_llm import GroqLLM, PLATFORM_WORKFLOWS
    
    llm = GroqLLM()
    
    test_commands = [
        "Open WhatsApp Web and send a message to Rahul saying I'll call him after 6 PM",
        "Go to Instagram and check my notifications",
        "Create a presentation in Canva about artificial intelligence"
    ]
    
    tools = [
        {"name": "browser.open", "description": "Open a URL", "parameters": {"url": "string"}},
        {"name": "browser.click", "description": "Click an element", "parameters": {"selector": "string"}},
        {"name": "browser.type", "description": "Type text", "parameters": {"selector": "string", "text": "string"}},
        {"name": "browser.read", "description": "Read page content", "parameters": {"selector": "string"}},
        {"name": "browser.wait", "description": "Wait for time", "parameters": {"seconds": "number"}}
    ]
    
    for i, cmd in enumerate(test_commands, 1):
        print(f"\n{'='*60}")
        print(f"Test {i}: {cmd}")
        print('-' * 60)
        
        response = llm.chat(cmd, available_tools=tools)
        
        print(f"Action: {response.get('action')}")
        if response.get('action') == 'tool_call':
            print(f"Tool: {response.get('tool_name')}")
            print(f"Parameters: {response.get('parameters')}")
        else:
            content = response.get('content', '')
            print(f"Response: {content[:300]}...")
    
    print("\n" + "=" * 60)
    print("Demo complete! Ready for full automation.")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_demo()
    else:
        initial_agent = "main"
        if "--agent" in sys.argv:
            idx = sys.argv.index("--agent")
            if idx + 1 < len(sys.argv):
                initial_agent = sys.argv[idx + 1].strip().lower()
        reload_flag = "--no-reload" not in sys.argv
        main(initial_agent=initial_agent, reload=reload_flag)
