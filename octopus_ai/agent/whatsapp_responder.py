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
    
    def __init__(self, driver=None, groq_llm: Optional[GroqLLM] = None, memory: Optional[Memory] = None):
        self.driver = driver
        self.llm = groq_llm or GroqLLM()
        self.memory = memory or Memory()
        self.replied_fingerprints: Set[str] = set()
        self.is_running = False
        self.is_authenticated = False
    
    def set_driver(self, driver):
        """Set or update the WebDriver instance"""
        self.driver = driver
    
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
                
            except Exception as e:
                time.sleep(2)
        
        print("⚠️ WhatsApp Web login timeout. Please ensure you are logged in.")
        return False

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
                    if text and not any(text.startswith(x) for x in ["online", "typing", "last seen", "click here"]):
                        return text
            except Exception:
                continue
        return "Unknown"

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
        Returns message info dict if the VERY LAST message in conversation is INCOMING (from the other person),
        or None if the last message was outgoing (sent by user) or already responded to.
        """
        if not self.driver:
            return None
        
        try:
            # Find all message containers in the conversation panel
            # In WhatsApp Web, incoming messages have class 'message-in', outgoing have 'message-out'
            msg_elems = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "div.message-in, div.message-out, div[data-testid='msg-container']"
            )
            
            if not msg_elems:
                return None
            
            # The very last message element
            last_msg = msg_elems[-1]
            classes = (last_msg.get_attribute("class") or "").lower()
            
            # If the last message is outgoing, we already replied!
            if "message-out" in classes:
                return None
            
            # It's an incoming message!
            contact = self.get_active_chat_title()
            
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
            return None

    def generate_ai_reply(self, contact: str, message_text: str) -> str:
        """
        Use Groq LLM (e.g. Qwen 3.8) to generate a concise, friendly, contextual reply.
        """
        system_prompt = (
            "You are an intelligent, friendly AI personal assistant automatically replying to WhatsApp messages on behalf of the user. "
            "Write a natural, polite, and concise reply (1-2 sentences maximum). "
            "Do NOT include quotation marks, think tags, explanations, or meta-commentary. "
            "Respond directly as the message to be sent."
        )
        
        user_prompt = f"Incoming message from {contact}: '{message_text}'"
        
        try:
            resp = self.llm.chat(
                user_message=user_prompt,
                context={"contact": contact, "last_message": message_text}
            )
            
            reply = resp.get("content") or resp.get("response", "")
            
            # Clean reply of any potential leftover think blocks or quotes
            if "</think>" in reply:
                reply = reply.split("</think>")[-1].strip()
            reply = reply.strip('"\n\r ')
            
            if not reply:
                reply = "Got it! Thanks for reaching out. I'll get back to you shortly."
            
            return reply
            
        except Exception as e:
            logger.error(f"Error generating AI reply: {e}")
            return "Hey, thanks for your message! I will get back to you soon."

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
            time.sleep(0.3)
            
            # Send keys into input box
            input_elem.send_keys(reply_text)
            time.sleep(0.5)
            
            # Press Enter to send
            input_elem.send_keys(Keys.ENTER)
            time.sleep(0.5)
            
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
                        time.sleep(0.5)
                        break
                except Exception:
                    pass
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send reply: {e}")
            return False

    def poll_once(self) -> Optional[Dict[str, Any]]:
        """
        Execute a single polling iteration:
        1. Check for unread chats in sidebar
        2. Check for new incoming message in active chat
        3. If message found, generate Groq AI reply and send it
        """
        if not self.driver:
            return None
        
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
        print("🤖 Generating Groq AI reply...")
        
        # 3. Generate AI reply
        ai_reply = self.generate_ai_reply(contact, incoming_text)
        print(f"✨ AI Reply: \"{ai_reply}\"")
        
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

    async def start_listening(self, poll_interval: float = 2.0):
        """
        Continuous listening loop.
        Monitors WhatsApp Web and automatically responds to incoming messages.
        """
        self.is_running = True
        print(f"👀 WhatsApp Auto-Responder is active (polling every {poll_interval}s)...")
        print("💬 Listening for new messages... (Press Ctrl+C to stop)")
        
        loop = asyncio.get_event_loop()
        while self.is_running:
            try:
                await loop.run_in_executor(None, self.poll_once)
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
