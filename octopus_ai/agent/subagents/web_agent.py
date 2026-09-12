"""
Web Agent for Octopus AI
Handles all browser-based automations in Real Visible Chrome:
- WhatsApp Web: Group broadcasts, contextual topic auto-replies, and marking off-topic chats as unread
- Canva: Presentation creation, slide templates, design automation
- Instagram: Notifications, direct messages, profile checking
- Web Search: Google research and live browser navigation
"""

import os
import sys
import time
import asyncio
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger("WebAgent")


class WebAgent:
    def __init__(self, driver_provider=None):
        self._driver_provider = driver_provider

    def get_driver(self):
        if self._driver_provider:
            return self._driver_provider()
        from octopus_ai.server.app import get_or_create_visible_engine
        eng = get_or_create_visible_engine()
        return eng.get_driver() if eng else None

    # =========================================================================
    # WHATSAPP WEB SUBSYSTEM (STUDENT & TEACHER WORKFLOWS)
    # =========================================================================
    async def send_whatsapp_broadcast(
        self,
        groups: List[str],
        message: str,
        sender_name: str = "Saiteja"
    ) -> Dict[str, Any]:
        """
        Send a notification/broadcast to specific student and parent groups as the teacher.
        """
        driver = self.get_driver()
        if not driver:
            return {"success": False, "error": "Chrome driver unavailable"}

        results = {"sent": [], "failed": []}
        try:
            if "web.whatsapp.com" not in driver.current_url:
                driver.get("https://web.whatsapp.com")
                await asyncio.sleep(4)

            # Wait for WhatsApp search box
            search_box = None
            search_selectors = [
                "//div[@contenteditable='true'][@data-tab='3']",
                "//div[@role='textbox'][@title='Search input textbox']",
                "//div[@role='textbox']"
            ]
            for sel in search_selectors:
                elems = driver.find_elements(By.XPATH, sel)
                if elems and elems[0].is_displayed():
                    search_box = elems[0]
                    break

            for group_name in groups:
                try:
                    if not search_box:
                        for sel in search_selectors:
                            elems = driver.find_elements(By.XPATH, sel)
                            if elems and elems[0].is_displayed():
                                search_box = elems[0]
                                break

                    if search_box:
                        search_box.click()
                        search_box.send_keys(Keys.CONTROL + "a")
                        search_box.send_keys(Keys.BACKSPACE)
                        await asyncio.sleep(0.3)
                        search_box.send_keys(group_name)
                        await asyncio.sleep(1.5)
                        search_box.send_keys(Keys.ENTER)
                        await asyncio.sleep(1.5)

                        # Find chat message input box
                        msg_boxes = driver.find_elements(By.XPATH, "//footer//div[@contenteditable='true']")
                        if msg_boxes:
                            input_box = msg_boxes[0]
                            input_box.click()
                            # Type message naturally as the teacher
                            input_box.send_keys(message)
                            await asyncio.sleep(0.5)
                            input_box.send_keys(Keys.ENTER)
                            results["sent"].append(group_name)
                            await asyncio.sleep(1.0)
                        else:
                            results["failed"].append({"group": group_name, "reason": "Message input box not found"})
                    else:
                        results["failed"].append({"group": group_name, "reason": "Search box not found"})
                except Exception as group_err:
                    results["failed"].append({"group": group_name, "reason": str(group_err)})

            return {
                "success": len(results["sent"]) > 0,
                "sent_count": len(results["sent"]),
                "details": results,
                "summary": f"Sent broadcast as {sender_name} to {len(results['sent'])} target group(s)."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def mark_chat_as_unread(self, contact_or_group_name: str) -> bool:
        """
        Mark a specific chat as unread in WhatsApp Web so the teacher can review it later.
        """
        driver = self.get_driver()
        if not driver:
            return False

        try:
            # Search or find the chat item in the left pane
            chat_items = driver.find_elements(By.XPATH, f"//span[@title='{contact_or_group_name}']")
            if not chat_items:
                return False

            chat_item = chat_items[0]
            # Hover or right click / click down arrow context menu
            from selenium.webdriver.common.action_chains import ActionChains
            actions = ActionChains(driver)
            actions.context_click(chat_item).perform()
            await asyncio.sleep(0.8)

            # Click 'Mark as unread'
            unread_options = driver.find_elements(By.XPATH, "//div[contains(text(), 'Mark as unread')] | //span[contains(text(), 'Mark as unread')]")
            if unread_options:
                unread_options[0].click()
                await asyncio.sleep(0.5)
                logger.info(f"[WebAgent] Marked '{contact_or_group_name}' as unread in WhatsApp.")
                return True
        except Exception as e:
            logger.warning(f"[WebAgent] Could not mark chat as unread: {e}")
        return False

    async def handle_whatsapp_topic_interaction(
        self,
        target_topic: str,
        teacher_name: str = "Saiteja",
        incoming_message: str = "",
        sender_name: str = ""
    ) -> Dict[str, Any]:
        """
        Determine if incoming message is on-topic (e.g. PTM):
        - If on-topic: Generate a respectful, natural reply as the teacher.
        - If off-topic: Mark the chat as unread in WhatsApp and leave it for the teacher.
        """
        topic_lower = target_topic.lower()
        msg_lower = incoming_message.lower()

        # Check topic relevance
        is_relevant = any(w in msg_lower for w in topic_lower.split()) or any(w in msg_lower for w in ["meeting", "ptm", "timing", "time", "where", "hall", "tomorrow", "venue", "schedule"])

        if is_relevant:
            # Generate respectful teacher reply
            from server.local_llm_service import local_llm_instance
            prompt = (
                f"You are {teacher_name}, a respected teacher replying directly on WhatsApp to a parent or student. "
                f"They asked: '{incoming_message}' regarding: '{target_topic}'. "
                f"Give a brief, professional, polite answer in 1-2 sentences as {teacher_name}."
            )
            reply_text = await local_llm_instance.generate_response(prompt)
            return {
                "action": "reply",
                "is_on_topic": True,
                "reply": reply_text,
                "reason": "Query matches active topic scope"
            }
        else:
            # Mark chat as unread in WhatsApp Web
            marked = await self.mark_chat_as_unread(sender_name)
            return {
                "action": "mark_unread",
                "is_on_topic": False,
                "marked_unread": marked,
                "reason": f"Message not related to '{target_topic}'. Marked as unread for {teacher_name} to review."
            }

    # =========================================================================
    # CANVA, INSTAGRAM & GOOGLE WEB SUBSYSTEMS
    # =========================================================================
    async def open_canva_presentation(self, topic: str = "presentation") -> Dict[str, Any]:
        """Open Canva in Chrome and search for matching educational/presentation templates."""
        from octopus_ai.automations.web.canva import CanvaAutomation
        driver = self.get_driver()
        auto = CanvaAutomation(driver=driver)
        res = await auto.run({"query": topic})
        return {"success": res.success, "message": res.message}

    async def open_instagram(self, action: str = "feed", username: str = "") -> Dict[str, Any]:
        """Open Instagram notifications or profile in Chrome."""
        from octopus_ai.automations.web.instagram import InstagramAutomation
        driver = self.get_driver()
        auto = InstagramAutomation(driver=driver)
        res = await auto.run({"action": action, "username": username})
        return {"success": res.success, "message": res.message}

    async def search_google(self, query: str) -> Dict[str, Any]:
        """Search Google and navigate in Chrome."""
        from octopus_ai.automations.web.browser_task import BrowserTaskAutomation
        driver = self.get_driver()
        auto = BrowserTaskAutomation(driver=driver)
        res = await auto.run({"query": query})
        return {"success": res.success, "message": res.message}


web_agent_instance = WebAgent()
