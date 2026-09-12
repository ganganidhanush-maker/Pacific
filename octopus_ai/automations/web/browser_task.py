"""
General Browser and Web Search Automation Module
"""

import time
import asyncio
from typing import Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from ..base import BaseAutomation, AutomationCategory, AutomationResult, AutomationStatus
from ..preview.preview_manager import PreviewManager


class BrowserTaskAutomation(BaseAutomation):
    id = "browser_task"
    name = "Web Search & Browser Automation"
    category = AutomationCategory.WEB
    description = "Navigate to any website, run Google searches, extract page text, and perform web actions."
    icon = "globe"

    async def run(self, params: Optional[Dict[str, Any]] = None) -> AutomationResult:
        params = params or {}
        url = params.get("url")
        search_query = params.get("query")
        preview = PreviewManager()

        self.status = AutomationStatus.RUNNING
        preview.start_automation(self.id, self.name, self.category.value)
        start_time = time.time()

        if not self.driver:
            self.emit_step(1, "Browser Initialization", "No browser driver connected", "error")
            preview.finish_automation(False, "Browser driver not available")
            return AutomationResult(success=False, message="Browser driver not available")

        try:
            if search_query:
                self.emit_step(1, "Google Search", f"Searching for '{search_query}'", "running")
                self.driver.get(f"https://www.google.com/search?q={search_query}")
                time.sleep(2)
                preview.capture_screenshot()
                self.emit_step(1, "Search Results Ready", f"Loaded results for '{search_query}'", "done")
                preview.finish_automation(True, f"Google search for '{search_query}' completed")
                return AutomationResult(success=True, message=f"Searched Google for '{search_query}'", execution_time_sec=time.time() - start_time)

            elif url:
                if not url.startswith("http"):
                    url = "https://" + url
                self.emit_step(1, f"Navigating to {url}", f"Opening {url}", "running")
                self.driver.get(url)
                time.sleep(2)
                preview.capture_screenshot()
                self.emit_step(1, "Page Loaded", f"Successfully opened {url}", "done")
                preview.finish_automation(True, f"Opened {url}")
                return AutomationResult(success=True, message=f"Navigated to {url}", execution_time_sec=time.time() - start_time)

            else:
                self.emit_step(1, "Standby", "Browser is ready for URLs or search queries", "done")
                preview.finish_automation(True, "Browser ready")
                return AutomationResult(success=True, message="Browser ready")

        except Exception as e:
            self.emit_step(2, "Browser Error", str(e), "error")
            preview.finish_automation(False, str(e))
            return AutomationResult(success=False, message=str(e), execution_time_sec=time.time() - start_time)
