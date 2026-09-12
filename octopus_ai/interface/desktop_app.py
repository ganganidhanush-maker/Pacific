"""
Octopus AI - Standalone Desktop Tool Window Runner

Uses pywebview to launch Octopus AI as a native Windows desktop application tool
without browser tabs or URL bars.
"""

import os
import sys
import time
import threading
import socket
from pathlib import Path

# Ensure repo directory and parent directory are on sys.path
repo_dir = Path(__file__).resolve().parent.parent
parent_dir = repo_dir.parent
for p in [str(parent_dir), str(repo_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    check_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((check_host, port)) == 0


def run_desktop_app(host: str = None, port: int = None):
    """Start local API server and launch the native desktop tool application window."""
    import uvicorn
    from octopus_ai.server.app import app

    # Resolve host and port dynamically
    is_docker = os.path.exists("/.dockerenv") or os.environ.get("IN_DOCKER", "").lower() in ("true", "1", "yes")
    if host is None:
        host = os.environ.get("HOST", "0.0.0.0" if is_docker else "127.0.0.1")
    if port is None:
        port = int(os.environ.get("PORT", "8000"))

    # Start FastAPI server in background thread if not already running
    if not is_port_in_use(port, host):
        server_thread = threading.Thread(
            target=lambda: uvicorn.run(app, host=host, port=port, log_level="warning"),
            daemon=True
        )
        server_thread.start()
        # Wait until port is open
        for _ in range(50):
            if is_port_in_use(port, host):
                break
            time.sleep(0.1)

    display_host = "localhost" if host in ("0.0.0.0", "127.0.0.1") else host
    url = f"http://{display_host}:{port}"
    print("=" * 65)
    print("       OCTOPUS AI — NATIVE DESKTOP AGENT TOOL")
    print("=" * 65)
    print(f"🚀 Octopus AI server active at: {url} (Bound to {host}:{port})")
    print("   • Standalone Native Window (pywebview)")
    print("   • Frameless Video Avatar: Active")
    print("   • 9-Dots Multi-Agent Selector: Ready")
    print("   • Real Chrome Browser Automation: Standby")
    print("=" * 65)

    is_headless = os.environ.get("HEADLESS", "false").lower() in ("true", "1", "yes") or \
                  os.environ.get("BROWSER_HEADLESS", "false").lower() in ("true", "1", "yes") or \
                  is_docker or \
                  (sys.platform != "win32" and not os.environ.get("DISPLAY"))

    # If headless, containerized, or no X11 display, keep server alive in foreground
    if is_headless:
        print(f"\n[OctopusAI] Running in headless/container mode.")
        print(f"[OctopusAI] Open your browser and visit: {url}")
        print("[OctopusAI] Press Ctrl+C anytime to stop.\n")
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            print("\n[OctopusAI] Server shutting down.")
            return

    # In desktop environments, attempt pywebview native window
    try:
        import webview
        window = webview.create_window(
            title="Octopus AI — Desktop Agent Tool",
            url=url,
            width=1080,
            height=740,
            min_size=(820, 600),
            resizable=True
        )
        webview.start()
    except Exception as e:
        print(f"⚠️ Native window note: {e}. Opening in default browser fallback...")
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass
        print(f"\n[OctopusAI] Server running at {url}. Press Ctrl+C to stop.\n")
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            print("\n[OctopusAI] Server shutting down.")


if __name__ == "__main__":
    run_desktop_app()
