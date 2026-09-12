"""
Octopus AI - Standalone Desktop Tool Window Runner

Uses pywebview to launch Octopus AI as a native Windows desktop application tool
without browser tabs or URL bars.
"""

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


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def run_desktop_app(host: str = "127.0.0.1", port: int = 8000):
    """Start local API server and launch the native desktop tool application window."""
    import uvicorn
    from octopus_ai.server.app import app

    # Start FastAPI server in background thread if not already running
    if not is_port_in_use(port):
        server_thread = threading.Thread(
            target=lambda: uvicorn.run(app, host=host, port=port, log_level="warning"),
            daemon=True
        )
        server_thread.start()
        # Wait until port is open
        for _ in range(30):
            if is_port_in_use(port):
                break
            time.sleep(0.1)

    url = f"http://{host}:{port}"
    print("=" * 65)
    print("       OCTOPUS AI — NATIVE DESKTOP AGENT TOOL")
    print("=" * 65)
    print(f"🚀 Launching Desktop Tool Window from {url}")
    print("   • Standalone Native Window (pywebview)")
    print("   • Frameless Video Avatar: Active")
    print("   • 9-Dots Multi-Agent Selector: Ready")
    print("   • Real Chrome Browser Automation: Standby")
    print("=" * 65)

    try:
        import webview
        # Create standalone native desktop tool window
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
        print(f"⚠️ PyWebView note: {e}. Opening in default browser fallback...")
        import webbrowser
        webbrowser.open(url)


if __name__ == "__main__":
    run_desktop_app()
