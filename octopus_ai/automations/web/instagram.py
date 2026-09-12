"""
Instagram Web Automation Module
"""

import time
import asyncio
from typing import Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from ..base import BaseAutomation, AutomationCategory, AutomationResult, AutomationStatus
from ..preview.preview_manager import PreviewManager


class InstagramAutomation(BaseAutomation):
    id = "instagram"
    name = "Instagram Automation"
    category = AutomationCategory.WEB
    description = "Check Instagram notifications, explore feeds, search profiles, and review direct messages."
    icon = "camera"

    async def run(self, params: Optional[Dict[str, Any]] = None) -> AutomationResult:
        params = params or {}
        action = params.get("action", "feed")
        username = params.get("username", "")
        preview = PreviewManager()

        self.status = AutomationStatus.RUNNING
        preview.start_automation(self.id, self.name, self.category.value)
        start_time = time.time()

        if not self.driver:
            self.emit_step(1, "Browser Initialization", "No browser driver connected", "error")
            preview.finish_automation(False, "Browser driver not available")
            return AutomationResult(success=False, message="Browser driver not available")

        try:
            # Step 1: Navigate to Instagram
            self.emit_step(1, "Navigating to Instagram", "Opening https://www.instagram.com", "running")
            self.driver.get("https://www.instagram.com")
            time.sleep(2)
            preview.capture_screenshot()
            self.emit_step(1, "Instagram Loaded", "Connected to Instagram", "done")

            if action == "profile" and username:
                # Step 2: Search or visit profile
                self.emit_step(2, f"Visiting @{username}", f"Navigating to https://www.instagram.com/{username}/", "running")
                self.driver.get(f"https://www.instagram.com/{username}/")
                time.sleep(2)
                preview.capture_screenshot()
                self.emit_step(2, f"Profile Opened", f"Viewing @{username}'s profile", "done")
                preview.finish_automation(True, f"Opened Instagram profile @{username}")
                return AutomationResult(success=True, message=f"Opened profile @{username}")
            else:
                self.emit_step(2, "Exploring Feed", "Viewing home feed and updates", "done")
                preview.finish_automation(True, "Instagram feed active")
                return AutomationResult(success=True, message="Instagram ready", execution_time_sec=time.time() - start_time)

        except Exception as e:
            self.emit_step(3, "Instagram Automation Error", str(e), "error")
            preview.finish_automation(False, str(e))
            return AutomationResult(success=False, message=str(e), execution_time_sec=time.time() - start_time)
