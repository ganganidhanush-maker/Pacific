"""
Octopus AI - Agent Preview Manager

Provides real-time state, screenshot capture, and step execution logs
for the UI's Agent Preview drawer.
"""

import time
import base64
from typing import Dict, List, Any, Optional
from datetime import datetime


class PreviewManager:
    """
    Singleton manager tracking the current execution state, active browser screenshot,
    and step timeline for the Agent Preview drawer.
    """
    _instance: Optional["PreviewManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PreviewManager, cls).__new__(cls)
            cls._instance._init_state()
        return cls._instance

    def _init_state(self):
        self.active_automation: Optional[str] = None
        self.active_category: str = "web"
        self.is_running: bool = False
        self.is_paused: bool = False
        self.current_url: str = "about:blank"
        self.status_message: str = "Ready for tasks"
        self.screenshot_b64: Optional[str] = None
        self.steps: List[Dict[str, Any]] = []
        self.logs: List[Dict[str, Any]] = []
        self.driver = None

    def set_driver(self, driver):
        self.driver = driver

    def log(self, message: str, level: str = "info"):
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message
        }
        self.logs.append(entry)
        if len(self.logs) > 150:
            self.logs = self.logs[-100:]

    def start_automation(self, automation_id: str, name: str, category: str = "web"):
        self.active_automation = name
        self.active_category = category
        self.is_running = True
        self.is_paused = False
        self.steps = []
        self.status_message = f"Executing {name}..."
        self.log(f"Started automation '{name}' [{automation_id}]", "info")

    def update_step(self, step_data: Dict[str, Any]):
        step_num = step_data.get("step_number")
        existing = next((s for s in self.steps if s.get("step_number") == step_num), None)
        if existing:
            existing.update(step_data)
        else:
            self.steps.append(step_data)
        
        self.status_message = step_data.get("title", self.status_message)
        self.log(f"Step {step_num}: {step_data.get('title')} - {step_data.get('status')}", "info")
        self.capture_screenshot()

    def finish_automation(self, success: bool, message: str):
        self.is_running = False
        self.is_paused = False
        self.status_message = message if success else f"Error: {message}"
        self.log(f"Finished automation: {self.status_message}", "success" if success else "error")
        self.capture_screenshot()

    def capture_screenshot(self) -> Optional[str]:
        """Capture live screenshot from selenium driver if available."""
        if not self.driver:
            return self.screenshot_b64
        try:
            current_handle = None
            try:
                current_handle = self.driver.current_window_handle
                self.current_url = self.driver.current_url
            except Exception:
                pass
            png_data = self.driver.get_screenshot_as_png()
            self.screenshot_b64 = f"data:image/png;base64,{base64.b64encode(png_data).decode('utf-8')}"
            return self.screenshot_b64
        except Exception as e:
            return self.screenshot_b64

    def get_status(self) -> Dict[str, Any]:
        """Return the current status dictionary for the UI."""
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "active_automation": self.active_automation,
            "active_category": self.active_category,
            "status_message": self.status_message,
            "current_url": self.current_url,
            "screenshot": self.screenshot_b64,
            "steps": self.steps,
            "logs": self.logs[-25:]
        }
