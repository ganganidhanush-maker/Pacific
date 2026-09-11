"""
Octopus AI - WhatsApp Web Auto-Responder

Monitors WhatsApp Web in real-time, detects incoming messages,
and automatically generates and sends contextual replies using Groq LLM.
"""

import time
import asyncio
import logging
from typing import Optional, Dict, Any, Set
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .groq_llm import GroqLLM
from ..memory.context import Memory

logger = logging.getLogger(__name__)


class WhatsAppAutoResponder:
    """
    Automated WhatsApp Web Assistant powered by Groq LLM.
    
    Features:
    - Waits for WhatsApp authentication (QR code scan or existing session)
    - Monitors unread chats and active conversation for incoming messages
    - Automatically checks whether the last message was incoming or outgoing
    - Deduplicates replies using message fingerprints
    - Generates natural, context-aware responses via Groq LLM
    - Types and sends replies automatically via Selenium
    """
    
    def __init__(
        self, 
        driver=None, 
        groq_llm: Optional[GroqLLM] = None, 
        memory: Optional[Memory] = None,
        allow_group_replies: bool = False,
        user_name: str = "Dhanush"
    ):
        self.driver = driver
        self.llm = groq_llm or GroqLLM()
        self.memory = memory or Memory()
        self.allow_group_replies = allow_group_replies
        self.user_name = user_name
        self.replied_fingerprints: Set[str] = set()
        self.is_running = False
        self.is_authenticated = False
        self.whatsapp_handle: Optional[str] = None
    
    def set_driver(self, driver):
        """Set or update the WebDriver instance"""
        self.driver = driver

    def set_whatsapp_handle(self, handle: str):
        """Set the window handle for the WhatsApp tab"""
        self.whatsapp_handle = handle
    
    def wait_for_login(self, timeout: int = 120) -> bool:
        """
        Wait for WhatsApp Web to be authenticated.
        Prompts user if QR code needs to be scanned.
        """
        if not self.driver:
            print("❌ No browser driver available for WhatsApp.")
            return False
        
        print("📱 Checking WhatsApp Web login status...")
        start_time = time.time()
        qr_announced = False
        
        while time.time() - start_time < timeout:
            try:
                # Check if chat list or search bar is present (Authenticated)
                chat_list_selectors = [
                    "[data-testid='chat-list']",
                    "[aria-label='Chat list']",
                    "#pane-side",
                    "div[contenteditable='true'][data-tab='3']",
                    "[data-testid='search']",
                    "header [data-testid='default-user']",
                    "#app"
                ]
                
                for sel in chat_list_selectors[:4]:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if elems and elems[0].is_displayed():
                        # Double check that we're past the QR code
                        qr_elems = self.driver.find_elements(By.CSS_SELECTOR, "canvas[aria-label='Scan me!'], [data-ref]")
                        if not qr_elems:
                            self.is_authenticated = True
                            print("✅ WhatsApp Web authenticated successfully!")
                            self.seed_initial_messages()
                            return True
                
                # Check if QR code is visible
                qr_elems = self.driver.find_elements(By.CSS_SELECTOR, "canvas, [data-testid='qrcode'], [data-ref]")
                if qr_elems and not qr_announced:
                    print("\n" + "=" * 60)
                    print("📲 WhatsApp Web QR Code detected!")
                    print("👉 Please scan the QR code on your phone screen in the open Chrome browser.")
                    print("=" * 60 + "\n")
                    qr_announced = True
                
                time.sleep(2)
                
            except Exception:
                time.sleep(2)
        
        print("⚠️ WhatsApp Web login timeout. Please ensure you are logged in.")
        return False

    def seed_initial_messages(self):
        """Record existing messages in the open chat so we never reply to old history on startup"""
        if not self.driver:
            return
        try:
            msg_elems = self.driver.find_elements(By.CSS_SELECTOR, "div.message-in, div.message-out")
            if msg_elems:
                contact = self.get_active_chat_title()
                for el in msg_elems[-10:]:
                    text_elems = el.find_elements(By.CSS_SELECTOR, "span.selectable-text, div.copyable-text, [dir='ltr']")
                    for te in text_elems:
                        t = te.text.strip()
                        if t:
                            self.replied_fingerprints.add(f"{contact}::{t}")
        except Exception:
            pass

    def get_active_chat_title(self) -> str:
        """Get the title/contact name of currently open chat"""
        if not self.driver:
            return "Unknown"
        
        header_selectors = [
            "header span[title]",
            "header div[role='button'] span[dir='auto']",
            "header span[dir='auto']",
            "[data-testid='conversation-header'] span"
        ]
        
        for sel in header_selectors:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elems:
                    text = el.text.strip()
                    if text and not any(text.lower().startswith(x) for x in ["online", "typing", "last seen", "click here"]):
                        return text
            except Exception:
                continue
        return "Unknown"

    def is_group_chat(self) -> bool:
        """Check if currently open conversation is a group chat"""
        if not self.driver:
            return False
        try:
            # Check header subtitle: group chats list participants separated by commas
            header_elems = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "header div[role='button'] span, header span[dir='auto'], header span[title]"
            )
            for elem in header_elems:
                text = elem.text.strip()
                if "," in text and not any(k in text.lower() for k in ["online", "last seen"]):
                    return True
            
            # Check for group author elements
            author_elems = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "span[data-testid='author'], div.message-in span[dir='auto'][aria-label='']"
            )
            if author_elems:
                return True
        except Exception:
            pass
        return False

    def check_unread_chats(self) -> bool:
        """
        Look for any chats in the sidebar with an unread badge and click to open.
        Returns True if an unread chat was clicked and opened.
        """
        if not self.driver:
            return False
        
        unread_selectors = [
            "span[aria-label*='unread']",
            "span[data-testid='icon-unread-count']",
            "[data-testid='cell-frame-container'] span[class*='unread']",
            "span[aria-label*='unread message']"
        ]
        
        for sel in unread_selectors:
            try:
                badges = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for badge in badges:
                    if badge.is_displayed():
                        # Find clickable parent chat container
                        parent = badge
                        for _ in range(5):
                            parent = parent.find_element(By.XPATH, "..")
                            if parent.get_attribute("role") in ("listitem", "row") or "cell-frame" in (parent.get_attribute("class") or ""):
                                break
                        parent.click()
                        time.sleep(1)
                        logger.info("Opened unread chat")
                        return True
            except Exception:
                continue
        return False

    def get_latest_message_info(self) -> Optional[Dict[str, Any]]:
        """
        Inspect the currently open chat conversation.
        Returns message info dict ONLY if the VERY LAST message in conversation is INCOMING (from the other person),
        and not outgoing (sent by user/bot) and not already responded to.
        """
        if not self.driver:
            return None
        
        try:
            contact = self.get_active_chat_title()
            
            # Safeguard: Skip group chats if allow_group_replies is False
            if not self.allow_group_replies and self.is_group_chat():
                return None
            
            # Look strictly for message bubbles (message-in and message-out)
            msg_elems = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "div.message-in, div.message-out"
            )
            
            if not msg_elems:
                return None
            
            # The very last message element
            last_msg = msg_elems[-1]
            classes = (last_msg.get_attribute("class") or "").lower()
            
            # CRITICAL CHECK: If the last message is outgoing, return None immediately!
            if "message-out" in classes:
                return None
            
            # Check if this element or its ancestor has message-out
            is_out = last_msg.find_elements(By.XPATH, "ancestor-or-self::*[contains(@class, 'message-out')]")
            if is_out:
                return None
            
            # Verify it is an incoming message
            is_in = ("message-in" in classes) or bool(last_msg.find_elements(By.XPATH, "ancestor-or-self::*[contains(@class, 'message-in')]"))
            if not is_in:
                return None
            
            # Extract text content
            text = ""
            text_elems = last_msg.find_elements(By.CSS_SELECTOR, "span.selectable-text, div.copyable-text, [dir='ltr']")
            for te in text_elems:
                t = te.text.strip()
                if t:
                    text = t
                    break
            
            if not text:
                return None
            
            # Unique fingerprint for this message
            fingerprint = f"{contact}::{text}"
            
            if fingerprint in self.replied_fingerprints:
                return None
            
            return {
                "contact": contact,
                "text": text,
                "fingerprint": fingerprint
            }
            
        except Exception as e:
            logger.debug(f"Error inspecting latest message: {e}")
            return None

    def generate_ai_reply(self, contact: str, message_text: str) -> str:
        """
        Use Groq LLM to generate a natural, human reply representing Dhanush.
        """
        human_system_prompt = (
            f"You are {self.user_name}. You are texting a contact on WhatsApp from your personal phone.\n"
            "Write a single, natural, casual reply representing yourself.\n\n"
            "STRICT RULES:\n"
            f"1. Speak naturally in first person as {self.user_name}.\n"
            "2. Keep it brief: 1 short sentence or casual phrase (e.g. \"Hey! Yeah, give me a few minutes.\", \"Sure, sounds good!\", \"Haha cool, on it!\", \"Hey, what's up?\").\n"
            "3. NEVER say you are an AI, a language model, an assistant, or a bot.\n"
            "4. NEVER mention tasks, tools, systems, code, loops, or automation.\n"
            "5. NEVER use bullet points, numbered lists, markdown formatting, or quotation marks.\n"
            "6. Respond ONLY with the exact text message to be sent. Nothing else."
        )
        
        user_prompt = f"Incoming WhatsApp message from {contact}: \"{message_text}\""
        
        try:
            resp = self.llm.chat(
                user_message=user_prompt,
                context=None,
                available_tools=None,
                system_prompt=human_system_prompt
            )
            
            reply = resp.get("content") or resp.get("response", "")
            
            # Clean reply of any potential leftover think blocks or quotes
            if "</think>" in reply:
                reply = reply.split("</think>")[-1].strip()
            
            reply = reply.strip('"\n\r `*')
            
            # Safeguard: remove any lines that look like AI disclaimers or lists
            lines = [line.strip() for line in reply.split("\n") if line.strip()]
            if lines:
                clean_lines = []
                for line in lines:
                    low = line.lower()
                    if any(x in low for x in ["as an ai", "i am an ai", "automated response", "system status", "looping on"]):
                        continue
                    if line.startswith(("1.", "2.", "3.", "-", "*")):
                        continue
                    clean_lines.append(line)
                if clean_lines:
                    reply = clean_lines[0]
                else:
                    reply = "Hey! Got your message, will get back to you shortly."
            
            if not reply:
                reply = "Hey! Got your message, will get back to you shortly."
            
            return reply
            
        except Exception as e:
            logger.error(f"Error generating AI reply: {e}")
            return "Hey! Got your message, I'll get back to you soon."

    def send_reply(self, reply_text: str) -> bool:
        """
        Locate the message input box in WhatsApp Web, type the reply, and send it.
        """
        if not self.driver:
            return False
        
        input_selectors = [
            "footer div[contenteditable='true']",
            "div[data-testid='conversation-compose-box-input']",
            "footer [role='textbox']",
            "div[aria-label='Type a message']",
            "footer [data-tab='10']"
        ]
        
        input_elem = None
        for sel in input_selectors:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if elems and elems[0].is_displayed():
                    input_elem = elems[0]
                    break
            except Exception:
                continue
        
        if not input_elem:
            logger.warning("Could not locate WhatsApp message input box.")
            return False
        
        try:
            input_elem.click()
            time.sleep(0.2)
            
            # Send keys into input box
            input_elem.send_keys(reply_text)
            time.sleep(0.3)
            
            # Press Enter to send
            input_elem.send_keys(Keys.ENTER)
            time.sleep(0.4)
            
            # Check if send button needs to be clicked (in case Enter didn't trigger)
            send_btn_selectors = [
                "button[data-testid='compose-btn-send']",
                "span[data-icon='send']",
                "[data-testid='send']"
            ]
            for btn_sel in send_btn_selectors:
                try:
                    btns = self.driver.find_elements(By.CSS_SELECTOR, btn_sel)
                    if btns and btns[0].is_displayed():
                        btns[0].click()
                        time.sleep(0.3)
                        break
                except Exception:
                    pass
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send reply: {e}")
            return False

    def poll_once(self, whatsapp_handle: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Execute a single polling iteration with cross-tab support:
        1. If whatsapp_handle is specified and current active tab is different (e.g. user is on Instagram/Canva),
           switch to WhatsApp, check for new messages, respond, and restore the user's active tab!
        """
        if not self.driver:
            return None
        
        target_handle = whatsapp_handle or self.whatsapp_handle
        original_handle = None
        switched_tab = False
        
        try:
            if target_handle and hasattr(self.driver, "current_window_handle"):
                try:
                    current = self.driver.current_window_handle
                    if current != target_handle:
                        original_handle = current
                        self.driver.switch_to.window(target_handle)
                        switched_tab = True
                        time.sleep(0.15)
                except Exception:
                    pass
            
            # 1. Open any unread chat
            self.check_unread_chats()
            
            # 2. Check active chat for new incoming message
            msg_info = self.get_latest_message_info()
            if not msg_info:
                return None
            
            contact = msg_info["contact"]
            incoming_text = msg_info["text"]
            fingerprint = msg_info["fingerprint"]
            
            print("\n" + "─" * 60)
            print(f"📩 [New Message] from: {contact}")
            print(f"💬 Message: \"{incoming_text}\"")
            print(f"👤 Generating reply as {self.user_name}...")
            
            # 3. Generate AI reply
            ai_reply = self.generate_ai_reply(contact, incoming_text)
            print(f"✨ Reply: \"{ai_reply}\"")
            
            # 4. Send the reply
            sent = self.send_reply(ai_reply)
            if sent:
                self.replied_fingerprints.add(fingerprint)
                print("🚀 Reply sent successfully via WhatsApp Web!")
                
                # Record in memory
                self.memory.add_conversation("user", f"[{contact}]: {incoming_text}")
                self.memory.add_conversation("assistant", f"[To {contact}]: {ai_reply}")
                
                print("─" * 60 + "\n")
                return {
                    "contact": contact,
                    "message": incoming_text,
                    "reply": ai_reply,
                    "sent": True
                }
            else:
                print("❌ Failed to send reply.")
                print("─" * 60 + "\n")
                return None
                
        finally:
            # 5. Restore user's active tab (e.g. Instagram or Canva)
            if switched_tab and original_handle:
                try:
                    self.driver.switch_to.window(original_handle)
                except Exception:
                    pass

    async def start_listening(self, poll_interval: float = 3.0, whatsapp_handle: Optional[str] = None):
        """
        Continuous listening loop.
        Monitors WhatsApp Web and automatically responds to incoming messages.
        Supports cross-tab background monitoring.
        """
        self.is_running = True
        if whatsapp_handle:
            self.whatsapp_handle = whatsapp_handle
            
        print(f"👀 WhatsApp Auto-Responder is active (polling every {poll_interval}s)...")
        print(f"👤 Representing: {self.user_name}")
        print("💬 Listening for incoming messages... (Press Ctrl+C to stop)")
        
        loop = asyncio.get_event_loop()
        while self.is_running:
            try:
                await loop.run_in_executor(None, self.poll_once, self.whatsapp_handle)
                await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(poll_interval)
        
        print("🛑 WhatsApp Auto-Responder stopped.")

    def stop(self):
        """Stop the listening loop"""
        self.is_running = False
