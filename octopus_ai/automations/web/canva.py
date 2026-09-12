"""
Canva Web Automation Module
"""

import time
import asyncio
from typing import Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from ..base import BaseAutomation, AutomationCategory, AutomationResult, AutomationStatus
from ..preview.preview_manager import PreviewManager


class CanvaAutomation(BaseAutomation):
    id = "canva"
    name = "Canva Design Automation"
    category = AutomationCategory.WEB
    description = "Search Canva templates, open design editor, and automate visual presentations."
    icon = "layout"

    async def run(self, params: Optional[Dict[str, Any]] = None) -> AutomationResult:
        params = params or {}
        query = params.get("query", "presentation")
        preview = PreviewManager()

        self.status = AutomationStatus.RUNNING
        preview.start_automation(self.id, self.name, self.category.value)
        start_time = time.time()

        if not self.driver:
            self.emit_step(1, "Browser Initialization", "No browser driver connected", "error")
            preview.finish_automation(False, "Browser driver not available")
            return AutomationResult(success=False, message="Browser driver not available")

        try:
            # Step 1: Open Canva
            self.emit_step(1, "Navigating to Canva", "Opening https://www.canva.com", "running")
            self.driver.get("https://www.canva.com")
            time.sleep(2)
            preview.capture_screenshot()
            self.emit_step(1, "Canva Loaded", "Connected to Canva homepage", "done")

            # Step 2: Search template
            if query:
                self.emit_step(2, f"Searching Templates: '{query}'", f"Querying Canva for '{query}' designs", "running")
                search_url = f"https://www.canva.com/search?q={query}"
                self.driver.get(search_url)
                time.sleep(2.5)
                preview.capture_screenshot()
                self.emit_step(2, "Templates Retrieved", f"Displaying '{query}' templates", "done")

            preview.finish_automation(True, f"Canva search for '{query}' completed")
            return AutomationResult(success=True, message=f"Canva designs for '{query}' ready", execution_time_sec=time.time() - start_time)

        except Exception as e:
            self.emit_step(3, "Canva Automation Error", str(e), "error")
            preview.finish_automation(False, str(e))
            return AutomationResult(success=False, message=str(e), execution_time_sec=time.time() - start_time)
