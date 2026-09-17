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


def _xpath_literal(s: str) -> str:
    """Safely represent a string as an XPath literal, handling single and double quotes."""
    if "'" not in s:
        return f"'{s}'"
    if '"' not in s:
        return f'"{s}"'
    parts = s.split("'")
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"


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

            selected_contact = params.get("selected_contact", "")

            # Step 3: Perform specific action
            if action == "send" and (contact or selected_contact) and message:
                search_target = selected_contact or contact
                self.emit_step(3, f"Finding Contact: {search_target}", f"Searching for '{search_target}' in chat list", "running")
                # Search contact
                search_boxes = self.driver.find_elements(By.XPATH, "//div[@contenteditable='true'][@data-tab='3'] | //div[@role='textbox']")
                if search_boxes:
                    search_box = search_boxes[0]
                    search_box.click()
                    search_box.send_keys(Keys.CONTROL + "a")
                    search_box.send_keys(Keys.BACKSPACE)
                    time.sleep(0.2)
                    search_box.send_keys(search_target)
                    time.sleep(1.8)

                    # If no specific contact was pre-selected, check for multiple matches in sidebar
                    if not selected_contact:
                        matching_contacts = []
                        seen = set()
                        spans = self.driver.find_elements(By.XPATH, "//div[@id='pane-side']//span[@title]")
                        for s in spans:
                            t = (s.get_attribute("title") or s.text or "").strip()
                            if t and t not in seen:
                                seen.add(t)
                                if contact.lower() in t.lower():
                                    matching_contacts.append(t)

                        # If multiple matches found (e.g. 2+ Harsha contacts), request disambiguation
                        if len(matching_contacts) > 1:
                            self.emit_step(3, "Multiple Contacts Found", f"Found {len(matching_contacts)} contacts matching '{contact}'", "done")
                            preview.finish_automation(True, f"Found {len(matching_contacts)} contacts matching '{contact}'")
                            return AutomationResult(
                                success=True,
                                message=f"Found {len(matching_contacts)} contacts matching '{contact}'. Clarification required.",
                                data={
                                    "disambiguation_required": True,
                                    "matches": matching_contacts,
                                    "contact_query": contact,
                                    "pending_message": message
                                }
                            )

                        target_name = matching_contacts[0] if matching_contacts else contact
                    else:
                        target_name = selected_contact

                    # Select the target contact
                    target_spans = self.driver.find_elements(By.XPATH, f"//div[@id='pane-side']//span[@title={_xpath_literal(target_name)}]")
                    if target_spans:
                        target_spans[0].click()
                    else:
                        search_box.send_keys(Keys.ENTER)
                    time.sleep(1.2)
                    self.emit_step(3, "Contact Selected", f"Opened chat with {target_name}", "done")

                    # Type and send message
                    self.emit_step(4, "Typing Message", f"Sending: '{message}'", "running")
                    msg_boxes = self.driver.find_elements(By.XPATH, "//div[@contenteditable='true'][@data-tab='10'] | //footer//div[@contenteditable='true']")
                    if msg_boxes:
                        msg_box = msg_boxes[0]
                        try:
                            msg_box.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].focus();", msg_box)
                        time.sleep(0.2)
                        
                        # Use document.execCommand for React/Lexical support
                        self.driver.execute_script("""
                            const box = arguments[0];
                            const text = arguments[1];
                            if (box) {
                                box.focus();
                                const sel = window.getSelection();
                                const range = document.createRange();
                                range.selectNodeContents(box);
                                sel.removeAllRanges();
                                sel.addRange(range);
                                document.execCommand('insertText', false, text);
                                box.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, inputType: 'insertText', data: text }));
                            }
                        """, msg_box, message)
                        time.sleep(0.3)
                        
                        if not msg_box.text.strip():
                            msg_box.send_keys(message)
                            time.sleep(0.3)
                        
                        msg_box.send_keys(Keys.ENTER)
                        time.sleep(0.3)
                        
                        # Also click send button via JS if present
                        self.driver.execute_script("""
                            const footer = document.querySelector("#main footer") || document.querySelector("footer");
                            if (footer) {
                                const sendBtn = footer.querySelector("button[aria-label*='Send' i], [data-testid='send'], [data-icon*='send']");
                                if (sendBtn) {
                                    const target = sendBtn.closest('button') || sendBtn.closest("[role='button']") || sendBtn;
                                    target.click();
                                }
                            }
                        """)
                        time.sleep(0.5)
                        self.emit_step(4, "Message Sent", f"Delivered to {target_name}", "done")
                        preview.finish_automation(True, f"Sent message to {target_name}")
                        return AutomationResult(
                            success=True,
                            message=f"Message sent to {target_name}",
                            data={"recipient": target_name, "message": message}
                        )
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
