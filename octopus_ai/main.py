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


def prepare_main_profile() -> tuple[str, str]:
    """
    Automatically set up and use the user's primary Chrome profile (Dhanush) without asking.
    Syncs session tokens, WhatsApp IndexedDB, and Cookies into .chrome_profile so
    all existing logins work seamlessly without crashing ChromeDriver.
    """
    import shutil
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    src = os.path.join(local_app_data, "Google", "Chrome", "User Data", "Default") if local_app_data else None
    dst = os.path.abspath(os.path.join(os.path.dirname(__file__), ".chrome_profile", "Default"))
    
    if src and os.path.exists(src):
        os.makedirs(dst, exist_ok=True)
        # Sync session and login data into .chrome_profile
        items_to_sync = ["Network", "IndexedDB", "Local Storage", "Preferences"]
        for item in items_to_sync:
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            if os.path.exists(s):
                try:
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)
                except Exception:
                    pass
    
    return ".chrome_profile", "Main Profile (Dhanush)"


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
        engine.navigate_to("https://web.whatsapp.com")
        time.sleep(1.5)
        whatsapp_handle = engine.driver.current_window_handle
        
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
            allow_group_replies=False,
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
    finally:
        print("🧹 Cleaning up and closing browser...")
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
