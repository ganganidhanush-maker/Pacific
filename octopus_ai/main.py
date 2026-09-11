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

# Ensure repository root is in sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

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
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
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



async def main():
    """Main entry point for Octopus AI Agent."""
    
    print("=" * 65)
    print("       OCTOPUS AI AGENT - Web Automation & WhatsApp Bot")
    print("=" * 65)
    print()
    
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        print("⚠️  NOTICE: GROQ_API_KEY not found in environment.")
        print("   Running in rule-based workflow mode.")
        print("   Set GROQ_API_KEY in your .env for dynamic AI reasoning.")
        print()
    else:
        print("✓ Groq API key loaded")
    
    headless_env = os.getenv("BROWSER_HEADLESS", "false").lower()
    headless = headless_env in ("true", "1", "yes")
    
    # Automatically prepare and use main profile (Dhanush) without prompting
    user_data_dir, profile_label = prepare_main_profile()
    
    print(f"✓ Configuration:")
    print(f"  • Headless: {headless}")
    print(f"  • Profile: {profile_label}")
    print(f"  • Groq Model: {os.getenv('GROQ_MODEL', 'qwen/qwen3.8-27b')}")
    print(f"  • Persona: Dhanush (Natural human text)")
    print()
    
    # 1. Initialize Browser Engine with Main Profile
    print("🚀 Launching Chrome browser with Main Profile (Dhanush)...")
    engine = BrowserEngine(
        headless=headless, 
        user_data_dir=user_data_dir,
        profile_directory="Default"
    )
    init_res = engine.initialize()
    if not init_res.get("success"):
        print(f"❌ Failed to initialize browser: {init_res.get('error')}")
        return
    
    print("✓ Browser launched successfully!")
    print()
    
    try:
        # 2. Open all designated tabs
        print("🌐 Opening designated tabs:")
        
        # Tab 1: WhatsApp Web
        print("  1️⃣  Opening WhatsApp Web (https://web.whatsapp.com)...")
        nav_res = engine.navigate_to("https://web.whatsapp.com")
        if not nav_res.get("success"):
            print(f"  ⚠️  Initial WhatsApp navigation note: {nav_res.get('error')}")
        time.sleep(2)
        
        whatsapp_handle = engine.get_current_handle()
        if not whatsapp_handle and engine.driver:
            try:
                handles = engine.driver.window_handles
                whatsapp_handle = handles[0] if handles else None
            except Exception:
                whatsapp_handle = None
        
        if not whatsapp_handle:
            print("❌ Unable to acquire WhatsApp window handle. Browser may have been closed.")
            return

        # Tab 2: Instagram
        print("  2️⃣  Opening Instagram (https://instagram.com)...")
        engine.open_tab("https://instagram.com")
        time.sleep(1)
        
        # Tab 3: Canva
        print("  3️⃣  Opening Canva (https://canva.com)...")
        engine.open_tab("https://canva.com")
        time.sleep(1)
        
        # 3. Switch back to WhatsApp Web tab
        print("  🎯 Switching focus back to WhatsApp Web tab...")
        engine.switch_to_tab(whatsapp_handle)
        print("✓ All tabs opened and ready!\n")
        
        # 4. Initialize Tools, Agent, and WhatsApp Auto-Responder
        tools = BrowserTools(engine=engine)
        agent = OctopusAgent(browser_tools=tools, groq_api_key=groq_api_key)
        
        responder = WhatsAppAutoResponder(
            driver=engine.get_driver(),
            groq_llm=agent.llm,
            memory=agent.memory,
            allow_group_replies=os.getenv("ALLOW_GROUP_REPLIES", "true").lower() in ("true", "1", "yes"),
            user_name="Dhanush"
        )
        responder.set_whatsapp_handle(whatsapp_handle)
        
        # Check authentication status
        print("=" * 65)
        print("📲 WhatsApp Web Status:")
        logged_in = responder.wait_for_login(timeout=45)
        if not logged_in:
            print("ℹ️ Note: If you need to scan the QR code, scan it in the open browser window.")
            print("   The auto-responder will begin as soon as chats load.")
        print("=" * 65)
        print()
        print("🤖 Octopus WhatsApp Auto-Responder is ACTIVE!")
        print("   • When an incoming message arrives, Octopus will auto-reply representing Dhanush.")
        print("   • If you are browsing Instagram or Canva, Octopus will auto-switch to WhatsApp and return you back!")
        print("   • Press Ctrl+C in this terminal anytime to stop.")
        print("=" * 65 + "\n")
        
        # 5. Start continuous listening loop with cross-tab support
        await responder.start_listening(poll_interval=2.5, whatsapp_handle=whatsapp_handle)
        
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n\n🛑 Stopping Octopus Agent...")
    except Exception as e:
        print(f"\n⚠️ Octopus Agent stopped: {e}")
    finally:
        print("🛑 Closing browser and stopping driver processes...")
        engine.quit()
        print("✓ All done. Goodbye!")


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
        asyncio.run(main())
