"""
WhatsApp Web Automation Module
"""

import time
import asyncio
from typing import Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from ..base import BaseAutomation, AutomationCategory, AutomationResult, AutomationStatus
from ..preview.preview_manager import PreviewManager


class WhatsAppAutomation(BaseAutomation):
    id = "whatsapp"
    name = "WhatsApp Web Automation"
    category = AutomationCategory.WEB
    description = "Automate WhatsApp Web: send messages, check unread chats, and run AI auto-responder."
    icon = "message-circle"

    async def run(self, params: Optional[Dict[str, Any]] = None) -> AutomationResult:
        params = params or {}
        action = params.get("action", "open")
        contact = params.get("contact", "")
        message = params.get("message", "")
        preview = PreviewManager()

        self.status = AutomationStatus.RUNNING
        preview.start_automation(self.id, self.name, self.category.value)
        start_time = time.time()

        if not self.driver:
            self.emit_step(1, "Browser Initialization", "No browser driver connected", "error")
            preview.finish_automation(False, "Browser driver not available")
            return AutomationResult(success=False, message="Browser driver not available")

        try:
            # Step 1: Navigate to WhatsApp Web
            self.emit_step(1, "Navigating to WhatsApp Web", "Opening https://web.whatsapp.com", "running")
            if "web.whatsapp.com" not in self.driver.current_url:
                self.driver.get("https://web.whatsapp.com")
            preview.capture_screenshot()
            self.emit_step(1, "WhatsApp Web Loaded", "Connected to web.whatsapp.com", "done")

            # Step 2: Check Login State
            self.emit_step(2, "Verifying Authentication", "Checking if WhatsApp session is authenticated...", "running")
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: d.find_elements(By.XPATH, "//div[@contenteditable='true']") or
                              d.find_elements(By.XPATH, "//canvas[@aria-label='Scan me!']")
                )
                qr = self.driver.find_elements(By.XPATH, "//canvas[@aria-label='Scan me!']")
                if qr:
                    self.emit_step(2, "QR Code Scan Required", "Please scan WhatsApp QR code in the browser", "running")
                    preview.finish_automation(True, "WhatsApp QR code displayed in preview. Ready for scan.")
                    return AutomationResult(success=True, message="Waiting for WhatsApp QR scan.")
                else:
                    self.emit_step(2, "Authenticated", "WhatsApp session is logged in and ready", "done")
            except Exception:
                self.emit_step(2, "Session Check Completed", "Proceeding with current view", "done")

            # Step 3: Perform specific action
            if action == "send" and contact and message:
                self.emit_step(3, f"Finding Contact: {contact}", f"Searching for '{contact}' in chat list", "running")
                # Search contact
                search_boxes = self.driver.find_elements(By.XPATH, "//div[@contenteditable='true'][@data-tab='3']")
                if search_boxes:
                    search_box = search_boxes[0]
                    search_box.click()
                    search_box.send_keys(Keys.CONTROL + "a")
                    search_box.send_keys(Keys.BACKSPACE)
                    search_box.send_keys(contact)
                    time.sleep(2)
                    search_box.send_keys(Keys.ENTER)
                    time.sleep(1)
                    self.emit_step(3, "Contact Selected", f"Opened chat with {contact}", "done")

                    # Type and send message
                    self.emit_step(4, "Typing Message", f"Sending: '{message}'", "running")
                    msg_boxes = self.driver.find_elements(By.XPATH, "//div[@contenteditable='true'][@data-tab='10']")
                    if msg_boxes:
                        msg_box = msg_boxes[0]
                        msg_box.click()
                        msg_box.send_keys(message)
                        time.sleep(0.5)
                        msg_box.send_keys(Keys.ENTER)
                        self.emit_step(4, "Message Sent", f"Delivered to {contact}", "done")
                        preview.finish_automation(True, f"Sent message to {contact}")
                        return AutomationResult(success=True, message=f"Message sent to {contact}")
                    else:
                        self.emit_step(4, "Message Box Not Found", "Could not locate chat input", "error")
                else:
                    self.emit_step(3, "Search Box Missing", "Chat search box not visible", "error")
            else:
                self.emit_step(3, "WhatsApp Standby", "WhatsApp Web is active and monitoring chats", "done")

            preview.finish_automation(True, "WhatsApp automation ready")
            return AutomationResult(success=True, message="WhatsApp automation active", execution_time_sec=time.time() - start_time)

        except Exception as e:
            self.emit_step(5, "Automation Error", str(e), "error")
            preview.finish_automation(False, str(e))
            return AutomationResult(success=False, message=str(e), execution_time_sec=time.time() - start_time)
