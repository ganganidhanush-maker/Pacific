#!/usr/bin/env python3
"""
Octopus AI Agent - Universal Main Entry Point

Cross-Platform runner that starts the Octopus AI Agent with Groq LLM integration.
Automatically validates dependencies, resolves API keys, configures Chrome profiles,
and launches the application seamlessly across Windows, macOS, and Linux.

Usage:
    python main.py
    python main.py --key <GROQ_API_KEY>
    python main.py --agent computer|web|desktop|research|chatbot|main
    python main.py --port 8080 --headless
    python main.py --no-reload
    python main.py --headless

Environment Variables:
    GROQ_API_KEY: Groq API key (automatically configured with fallback if not provided)
    GROQ_MODEL: Model to use (default: llama-3.3-70b-versatile)
    PORT: Server port (default: 8000)
    HOST: Server host (default: 127.0.0.1)
    BROWSER_HEADLESS: Run browser in headless mode (default: false)
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path
from typing import Tuple, Optional

# ==============================================================================
# 1. Console UTF-8 Encoding Setup (Safe across all OSes)
# ==============================================================================
for stream in (sys.stdout, sys.stderr):
    if stream and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# ==============================================================================
# 2. Path & Package Resolution
# ==============================================================================
this_dir = Path(__file__).resolve().parent
parent_dir = this_dir.parent
for p in [str(this_dir), str(parent_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Guarantee that 'octopus_ai' package can always be imported, even if cloned
# into a directory named 'Pacific' or any custom folder name.
if "octopus_ai" not in sys.modules:
    import types
    mod = types.ModuleType("octopus_ai")
    mod.__path__ = [str(this_dir)]
    init_file = this_dir / "__init__.py"
    if init_file.exists():
        mod.__file__ = str(init_file)
    sys.modules["octopus_ai"] = mod

# ==============================================================================
# 3. Dependency Self-Healing & Pre-Flight Check
# ==============================================================================
# Critical modules required for Octopus AI to function
DEPENDENCY_MAP = {
    "dotenv": "python-dotenv>=1.0.0",
    "fastapi": "fastapi>=0.104.0",
    "uvicorn": "uvicorn[standard]>=0.24.0",
    "pydantic": "pydantic>=2.5.0",
    "requests": "requests>=2.31.0",
    "python_multipart": "python-multipart>=0.0.9",
    "httpx": "httpx>=0.25.0",
    "groq": "groq>=0.4.2",
    "edge_tts": "edge-tts>=6.1.9",
    "selenium": "selenium>=4.15.0",
    "webdriver_manager": "webdriver-manager>=4.0.1",
    "playwright": "playwright>=1.40.0",
    "PIL": "pillow>=10.0.0",
    "psutil": "psutil>=5.9.0",
}

if sys.platform == "win32":
    DEPENDENCY_MAP["win32gui"] = "pywin32>=306"
    DEPENDENCY_MAP["comtypes"] = "comtypes>=1.4.0"
    DEPENDENCY_MAP["pyautogui"] = "pyautogui>=0.9.54"
    DEPENDENCY_MAP["keyboard"] = "keyboard>=0.13.5"


def ensure_dependencies() -> None:
    """
    Verify that required dependencies are installed.
    If any are missing, automatically installs them via pip so that the file runs
    identically on any fresh machine or operating system without crashing.
    """
    missing_packages = []
    for mod_name, pkg_spec in DEPENDENCY_MAP.items():
        try:
            __import__(mod_name)
        except ImportError:
            missing_packages.append(pkg_spec)

    if missing_packages:
        print("=" * 65)
        print("[OctopusAI] Dependency Check: Missing packages detected:")
        for pkg in missing_packages:
            print(f"   • {pkg}")
        print("[OctopusAI] Installing ONLY the missing dependencies, please wait...")
        print("=" * 65)

        try:
            # Only install the specific packages that are missing, avoiding redundant installations
            cmd = [sys.executable, "-m", "pip", "install", "--no-warn-script-location"] + missing_packages
            subprocess.check_call(cmd)
            print("[OctopusAI] [OK] Missing dependencies successfully installed!\n")
        except Exception as err:
            print(f"[OctopusAI] [WARNING] Automatic dependency install encountered: {err}")
            print("[OctopusAI] Attempting to proceed with available modules...\n")


# Run dependency verification immediately before importing non-standard modules
ensure_dependencies()

# Safe imports after dependency verification
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ==============================================================================
# 4. API Key & Environment Auto-Configuration
# ==============================================================================
DEFAULT_GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


def setup_environment(cli_api_key: Optional[str] = None) -> str:
    """
    Ensure a valid Groq API key and environment configuration are active.
    1. Checks CLI argument --key
    2. Checks os.environ['GROQ_API_KEY']
    3. Checks .env file
    4. Automatically falls back to DEFAULT_GROQ_API_KEY
    5. Persists to .env file so worker subprocesses inherit the configuration.
    """
    active_key = cli_api_key or os.environ.get("GROQ_API_KEY")
    env_file = this_dir / ".env"

    # If still not found, check .env manually
    if not active_key and env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GROQ_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip("\"'")
                        if val:
                            active_key = val
                            break
        except Exception:
            pass

    # Use embedded default if none was configured
    if not active_key:
        active_key = DEFAULT_GROQ_API_KEY

    # Export to current environment
    os.environ["GROQ_API_KEY"] = active_key
    os.environ.setdefault("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    os.environ.setdefault("BROWSER_HEADLESS", "false")
    os.environ.setdefault("PORT", "8000")
    os.environ.setdefault("HOST", "127.0.0.1")

    # Ensure .env file exists and contains the active key
    try:
        env_content = ""
        has_key = False
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                env_content = f.read()
            if "GROQ_API_KEY=" in env_content:
                has_key = True

        if not has_key:
            with open(env_file, "a", encoding="utf-8") as f:
                if env_content and not env_content.endswith("\n"):
                    f.write("\n")
                f.write(f"# Octopus AI Configuration (Auto-generated)\n")
                f.write(f"GROQ_API_KEY={active_key}\n")
                f.write(f"GROQ_MODEL={os.environ.get('GROQ_MODEL', DEFAULT_GROQ_MODEL)}\n")
                f.write(f"BROWSER_HEADLESS={os.environ.get('BROWSER_HEADLESS', 'false')}\n")
                f.write(f"PORT={os.environ.get('PORT', '8000')}\n")
    except Exception:
        pass

    masked_key = f"{active_key[:8]}...{active_key[-4:]}" if len(active_key) > 12 else "***"
    print(f"[OctopusAI] Groq API Key configured: {masked_key} (Ready)")
    return active_key


# ==============================================================================
# 5. Cross-Platform Safe File & Tree Copying
# ==============================================================================
def _safe_copy_tree(src: str, dst: str) -> None:
    """Safely copy a file or directory tree, skipping locked or inaccessible files without aborting."""
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


def cleanup_orphaned_automation_chrome(target_user_data_dir: str) -> int:
    """
    Safely find and terminate background chrome.exe processes associated ONLY with
    the automation user-data-dir, leaving user's personal browsing tabs completely untouched.
    """
    if not target_user_data_dir or not os.path.exists(target_user_data_dir):
        return 0
    try:
        import psutil
        killed = 0
        norm_target = os.path.normpath(os.path.abspath(target_user_data_dir)).lower()
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = (proc.info.get('name') or '').lower()
                if 'chrome' in name:
                    cmdline = proc.info.get('cmdline') or []
                    cmd_str = ' '.join(cmdline).lower()
                    if norm_target in cmd_str or ('automationdata' in cmd_str and 'automationdata' in norm_target):
                        proc.kill()
                        killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return killed
    except Exception as e:
        print(f"[OctopusAI] Note during chrome process cleanup: {e}")
        return 0


# ==============================================================================
# 6. Cross-Platform Chrome Profile Resolution (Windows, macOS, Linux)
# ==============================================================================
def prepare_main_profile() -> Tuple[str, str]:
    """
    Automatically prepare and use a dedicated automation Chrome profile.
    Resolves Chrome paths across Windows, macOS, and Linux.
    Uses an AutomationData directory that preserves user logins (WhatsApp, Instagram, Canva)
    permanently across reruns without session wipe or lock conflicts.
    """
    # 1. Custom override from environment
    chrome_data_env = os.environ.get("CHROME_USER_DATA_DIR")
    if chrome_data_env:
        os.makedirs(chrome_data_env, exist_ok=True)
        cleanup_orphaned_automation_chrome(chrome_data_env)
        return chrome_data_env, "Configured Chrome Data"

    # 2. Platform-specific resolution
    current_os = sys.platform
    src_root = None
    dst_root = None

    if current_os == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            src_root = os.path.join(local_app_data, "Google", "Chrome", "User Data")
            dst_root = os.path.join(local_app_data, "Google", "Chrome", "AutomationData")
    elif current_os == "darwin":  # macOS
        home = os.path.expanduser("~")
        src_root = os.path.join(home, "Library", "Application Support", "Google", "Chrome")
        dst_root = os.path.join(home, "Library", "Application Support", "Google", "Chrome", "AutomationData")
    else:  # Linux / Unix
        home = os.path.expanduser("~")
        src_candidate = os.path.join(home, ".config", "google-chrome")
        if not os.path.exists(src_candidate):
            src_candidate = os.path.join(home, ".config", "chromium")
        src_root = src_candidate
        dst_root = os.path.join(home, ".config", "google-chrome-automation")

    # Fallback to repository-local profile directory if system paths unavailable
    if not dst_root:
        local_fallback = os.path.join(str(this_dir), ".chrome_profile")
        os.makedirs(local_fallback, exist_ok=True)
        cleanup_orphaned_automation_chrome(local_fallback)
        return local_fallback, "Local Fallback Profile"

    # Safely terminate any orphaned automation Chrome processes holding open file locks
    cleanup_orphaned_automation_chrome(dst_root)

    dst_default = os.path.join(dst_root, "Default")

    # 3. If AutomationData already exists, clean lockfiles and return
    if os.path.exists(dst_default):
        lock_names = ["SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile", "DevToolsActivePort"]
        for lock_name in lock_names:
            lock_file = os.path.join(dst_root, lock_name)
            if os.path.exists(lock_file) or os.path.islink(lock_file):
                try:
                    if os.path.islink(lock_file) or os.path.isfile(lock_file):
                        os.remove(lock_file)
                    elif os.path.isdir(lock_file):
                        shutil.rmtree(lock_file, ignore_errors=True)
                except Exception:
                    pass
        return dst_root, "Personal Automation Profile"

    # 4. First-time initialization: safely clone profile from system Chrome
    if src_root and os.path.exists(src_root):
        os.makedirs(dst_root, exist_ok=True)

        # Sync Local State (contains encryption keys)
        src_ls = os.path.join(src_root, "Local State")
        dst_ls = os.path.join(dst_root, "Local State")
        _safe_copy_tree(src_ls, dst_ls)

        # Initial seed of Default profile
        src_default = os.path.join(src_root, "Default")
        if os.path.exists(src_default):
            os.makedirs(dst_default, exist_ok=True)
            essential_items = [
                "Network",
                "IndexedDB",
                "Local Storage",
                "Session Storage",
                "Preferences",
                "Secure Preferences"
            ]
            for item in essential_items:
                s = os.path.join(src_default, item)
                d = os.path.join(dst_default, item)
                _safe_copy_tree(s, d)

        return dst_root, "Personal Automation Profile"

    # Default fallback
    local_fallback = os.path.join(str(this_dir), ".chrome_profile")
    os.makedirs(local_fallback, exist_ok=True)
    return local_fallback, "Default Automation Profile"


# ==============================================================================
# 7. Quick Interactive / Demo Mode
# ==============================================================================
def run_demo() -> None:
    """Run a quick test demonstration of the agent reasoning capabilities."""
    print("\n" + "=" * 60)
    print("              OCTOPUS AI — DEMO MODE")
    print("=" * 60)

    from octopus_ai.agent.groq_llm import GroqLLM

    llm = GroqLLM()
    test_commands = [
        "Open WhatsApp Web and send a message to Rahul saying I'll call him after 6 PM",
        "Create a presentation in Canva about artificial intelligence",
        "Open Notepad and type meeting notes for Pacific AI"
    ]

    tools = [
        {"name": "browser.open", "description": "Open a URL", "parameters": {"url": "string"}},
        {"name": "browser.click", "description": "Click an element", "parameters": {"selector": "string"}},
        {"name": "computer.launch_app", "description": "Launch desktop application", "parameters": {"app_name": "string"}},
        {"name": "computer.type_text", "description": "Type text into active window", "parameters": {"text": "string"}},
        {"name": "computer.powershell", "description": "Execute diagnostic query via PowerShell", "parameters": {"command": "string"}}
    ]

    for i, cmd in enumerate(test_commands, 1):
        print(f"\n{'=' * 60}")
        print(f"Test {i}: {cmd}")
        print("-" * 60)

        response = llm.chat(cmd, available_tools=tools)
        print(f"Action: {response.get('action')}")
        if response.get('action') == 'tool_call':
            print(f"Tool: {response.get('tool_name')}")
            print(f"Parameters: {response.get('parameters')}")
        else:
            content = response.get('content', '')
            print(f"Response: {content[:300]}...")

    print("\n" + "=" * 60)
    print("Demo complete! All systems operational.")
    print("=" * 60)


# ==============================================================================
# 8. Main Application Entry Point
# ==============================================================================
def main(
    initial_agent: str = "main",
    reload: bool = True,
    port: int = 8000,
    host: str = "127.0.0.1",
    api_key: Optional[str] = None
) -> None:
    """
    Main entry point for Octopus AI Desktop Agent Tool.
    Initializes environment, profiles, agents, and starts the interface.
    """
    # Initialize environment and API key
    setup_environment(api_key)

    # Initialize and clean Chrome automation profile
    profile_path, profile_desc = prepare_main_profile()
    print(f"[OctopusAI] Chrome Automation Profile: {profile_desc} ({profile_path})")

    # Initialize active agent in server
    try:
        from server.app import AVAILABLE_AGENTS
        import server.app as srv
        valid_ids = [a["id"] for a in AVAILABLE_AGENTS]
        if initial_agent in valid_ids:
            srv.CURRENT_AGENT = initial_agent
            print(f"[OctopusAI] Initial active agent set to: {initial_agent.upper()}")
    except Exception as err:
        print(f"[OctopusAI] Agent initialization notice: {err}")

    # Launch desktop application window (falls back to browser if pywebview unavailable)
    try:
        from interface.desktop_app import run_desktop_app
    except ImportError:
        from octopus_ai.interface.desktop_app import run_desktop_app
    run_desktop_app(
        host=host,
        port=port,
        reload=reload,
        initial_agent=initial_agent
    )


# ==============================================================================
# 9. CLI Argument Parsing & Launch
# ==============================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Octopus AI Agent — Universal Desktop & Web Automation Platform",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--key", type=str, default=None, help="Groq API Key (uses embedded fallback if omitted)")
    parser.add_argument("--agent", type=str, default="main", help="Initial agent (main, computer, web, desktop, research, chatbot)")
    parser.add_argument("--port", type=int, default=8000, help="Local server port")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host address")
    parser.add_argument("--no-reload", action="store_true", help="Disable live auto-reloading")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--demo", action="store_true", help="Run quick demo of agent capabilities")

    args = parser.parse_args()

    if args.headless:
        os.environ["BROWSER_HEADLESS"] = "true"

    if args.demo:
        setup_environment(args.key)
        run_demo()
    else:
        main(
            initial_agent=args.agent.strip().lower(),
            reload=not args.no_reload,
            port=args.port,
            host=args.host,
            api_key=args.key
        )
