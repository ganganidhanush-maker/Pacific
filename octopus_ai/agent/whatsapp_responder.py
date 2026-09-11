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
        self._current_chat_title: Optional[str] = None
    
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
                
            except Exception as e:
                err_str = str(e).lower()
                if any(x in err_str for x in ["refused", "disconnected", "closed", "invalid session", "target machine", "connection reset"]):
                    print("ℹ️ Browser was closed or disconnected during login wait.")
                    return False
                time.sleep(2)
        
        print("⚠️ WhatsApp Web login timeout. Please ensure you are logged in.")
        return False

    def seed_initial_messages(self):
        """
        Record existing messages on startup.
        CRITICAL: Only record outgoing messages. If the very last message in the active chat
        is an unreplied incoming message, we DO NOT blacklist it so the bot can respond immediately!
        """
        if not self.driver:
            return
        try:
            msg_data = self._inspect_conversation_js()
            if msg_data and msg_data.get("is_outgoing"):
                # Last message is already outgoing, nothing pending
                pass
        except Exception:
            pass

    def get_active_chat_title(self) -> str:
        """Get the title/contact name of currently open chat"""
        if not self.driver:
            return self._current_chat_title or "Unknown"
        
        try:
            title = self.driver.execute_script("""
                // 1. Check header in #main
                const mainHeader = document.querySelector("#main header") || document.querySelector("#main > header") || document.querySelector("[data-testid='conversation-header']");
                if (mainHeader) {
                    const spanTitle = mainHeader.querySelector("span[title]");
                    if (spanTitle && spanTitle.title) return spanTitle.title.trim();
                    if (spanTitle && spanTitle.textContent) return spanTitle.textContent.trim();
                    
                    const h2Span = mainHeader.querySelector("h2 span, [data-testid*='title'] span, div[role='button'] span[dir='auto']");
                    if (h2Span && h2Span.textContent) {
                        const t = h2Span.textContent.trim();
                        const low = t.toLowerCase();
                        if (t && !low.startsWith("online") && !low.startsWith("typing") && !low.startsWith("last seen") && !low.startsWith("click here")) {
                            return t;
                        }
                    }
                }
                
                // 2. Check active conversation row in the sidebar
                const activeSidebar = document.querySelector("#pane-side div[aria-selected='true'], #pane-side div._ak72");
                if (activeSidebar) {
                    const sTitle = activeSidebar.querySelector("span[title]") || activeSidebar.querySelector("span[dir='auto']");
                    if (sTitle) {
                        const t = (sTitle.title || sTitle.textContent || "").trim();
                        if (t) return t;
                    }
                }
                
                return null;
            """)
            if title:
                self._current_chat_title = title
                return title
        except Exception:
            pass

        if self._current_chat_title:
            return self._current_chat_title

        return "Unknown"

    def is_group_chat(self) -> bool:
        """Check if currently open conversation is a group chat"""
        if not self.driver:
            return False
        try:
            # Check header subtitle
            header_elems = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "header div[role='button'] span, header span[dir='auto']"
            )
            for elem in header_elems:
                text = elem.text.strip()
                # Group subtitle has comma-separated member names
                if "," in text and not any(k in text.lower() for k in ["online", "last seen", "typing", "click here"]):
                    return True
            
            # Check community / group header icons
            group_icons = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "header [data-icon='default-group'], header [data-testid='chat-header-group']"
            )
            if group_icons:
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
        
        try:
            res = self.driver.execute_script("""
                const pane = document.querySelector("#pane-side");
                if (!pane) return null;
                
                const badges = pane.querySelectorAll(
                    "span[aria-label*='unread' i], [data-testid='icon-unread-count'], span[class*='_aou8'], div[aria-label*='unread' i]"
                );
                for (let b of badges) {
                    if (b.offsetParent === null) continue;
                    
                    let p = b;
                    let target = null;
                    for (let i = 0; i < 8; i++) {
                        if (p.parentElement) {
                            p = p.parentElement;
                            if (p.getAttribute('role') === 'row' || p.getAttribute('role') === 'listitem' || p.getAttribute('data-testid') === 'cell-frame-container') {
                                target = p;
                                break;
                            }
                        }
                    }
                    if (!target) target = b.closest('div');
                    if (!target) continue;
                    
                    let contact = "";
                    const tEl = target.querySelector("span[title]") || target.querySelector("div[role='gridcell'] span") || target.querySelector("span[dir='auto']");
                    if (tEl) {
                        contact = (tEl.title || tEl.textContent || "").trim();
                    }
                    
                    // Dispatch full synthetic mouse event sequence to trigger React click handler
                    const opts = { bubbles: true, cancelable: true, view: window };
                    target.dispatchEvent(new MouseEvent('mousedown', opts));
                    target.dispatchEvent(new MouseEvent('mouseup', opts));
                    target.dispatchEvent(new MouseEvent('click', opts));
                    try { target.click(); } catch(e) {}
                    
                    return { clicked: true, contact: contact };
                }
                return null;
            """)
            if res and res.get("clicked"):
                if res.get("contact"):
                    self._current_chat_title = res.get("contact")
                time.sleep(1.5)
                logger.info(f"Opened unread chat: {self._current_chat_title or 'contact'} via sidebar badge")
                return True
        except Exception:
            pass
        
        return False

    def _inspect_conversation_js(self) -> Optional[Dict[str, Any]]:
        """
        Execute high-performance JavaScript to inspect active chat messages.
        Accurately identifies if last message is outgoing or incoming, and extracts text.
        """
        if not self.driver:
            return None
        
        script = """
            const result = (function() {
                const mainPane = document.querySelector("#main") || document;
                const rows = mainPane.querySelectorAll("div[data-id], div[class*='message-in'], div[class*='message-out'], div[role='row']");
                if (!rows || rows.length === 0) {
                    return null;
                }
                
                let lastMsg = null;
                let lastDataId = "";
                let isOutgoing = false;
                let isIncoming = false;
                
                for (let i = rows.length - 1; i >= 0; i--) {
                    const row = rows[i];
                    const dataId = row.getAttribute("data-id") || (row.querySelector("[data-id]") ? row.querySelector("[data-id]").getAttribute("data-id") : "");
                    const cls = (row.className || "") + " " + (row.parentElement ? row.parentElement.className || "" : "");
                    
                    if (cls.includes("system-message") || row.querySelector("[data-testid='system-message']")) {
                        continue;
                    }
                    
                    const hasChecks = !!row.querySelector("[data-icon='msg-check'], [data-icon='msg-dblcheck'], [data-icon='msg-time'], [data-icon*='check']");
                    const hasOutCls = cls.includes("message-out") || !!row.querySelector("[class*='message-out']");
                    const isDataIdOut = dataId.startsWith("true_");
                    
                    const hasInCls = cls.includes("message-in") || !!row.querySelector("[class*='message-in']");
                    const isDataIdIn = dataId.startsWith("false_");
                    
                    if (isDataIdOut || hasChecks || hasOutCls) {
                        isOutgoing = true;
                        lastMsg = row;
                        lastDataId = dataId;
                        break;
                    } else if (isDataIdIn || hasInCls) {
                        isIncoming = true;
                        lastMsg = row;
                        lastDataId = dataId;
                        break;
                    } else {
                        const tEl = row.querySelector(".selectable-text, .copyable-text, [dir='ltr'], [dir='rtl'], [dir='auto']");
                        if (tEl && tEl.textContent.trim()) {
                            lastMsg = row;
                            lastDataId = dataId;
                            isIncoming = true;
                            break;
                        }
                    }
                }
                
                if (!lastMsg) return null;
                if (isOutgoing) return { is_outgoing: true, is_incoming: false, data_id: lastDataId };
                
                const textSelectors = [
                    "span.selectable-text",
                    "div.copyable-text span",
                    "span._ao3e",
                    "span[dir='ltr']",
                    "span[dir='rtl']",
                    "span[dir='auto']",
                    "div.copyable-text"
                ];
                
                let text = "";
                for (let sel of textSelectors) {
                    const el = lastMsg.querySelector(sel);
                    if (el && el.textContent.trim()) {
                        const meta = lastMsg.querySelector("[data-testid='msg-meta'], span[data-testid='msg-time']");
                        if (meta && el.contains(meta)) continue;
                        text = el.textContent.trim();
                        break;
                    }
                }
                
                if (!text) {
                    const meta = lastMsg.querySelector("[data-testid='msg-meta'], span[data-testid='msg-time']");
                    const metaText = meta ? meta.textContent : "";
                    text = lastMsg.textContent.replace(metaText, "").trim();
                }
                
                return {
                    is_outgoing: false,
                    is_incoming: true,
                    data_id: lastDataId,
                    text: text
                };
            })();
            return result;
        """
        try:
            return self.driver.execute_script(script)
        except Exception:
            return None

    def get_latest_message_info(self) -> Optional[Dict[str, Any]]:
        """
        Inspect the currently open chat conversation.
        Returns message info dict ONLY if the VERY LAST message is INCOMING and unreplied.
        """
        if not self.driver:
            return None
        
        try:
            contact = self.get_active_chat_title()
            
            # Safeguard: Skip group chats ONLY if explicitly configured to disallow
            if not self.allow_group_replies and self.is_group_chat():
                return None
            
            # 1. Use JavaScript inspection for maximum accuracy
            js_res = self._inspect_conversation_js()
            if js_res:
                if js_res.get("is_outgoing"):
                    return None
                
                text = js_res.get("text", "").strip()
                data_id = js_res.get("data_id", "")
                
                if not text:
                    return None
                
                # Fingerprint combining contact, text, and data_id
                fingerprint = f"{contact}::{text}"
                if data_id:
                    fingerprint = f"{contact}::{data_id}::{text}"
                
                if fingerprint in self.replied_fingerprints:
                    return None
                
                return {
                    "contact": contact,
                    "text": text,
                    "fingerprint": fingerprint,
                    "data_id": data_id
                }
            
            # 2. Fallback to DOM elements if JS inspection returned None
            msg_elems = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "div.message-in, div.message-out, div[class*='message-in'], div[class*='message-out']"
            )
            if not msg_elems:
                return None
            
            last_msg = msg_elems[-1]
            classes = (last_msg.get_attribute("class") or "").lower()
            
            if "message-out" in classes:
                return None
            
            text = ""
            text_elems = last_msg.find_elements(By.CSS_SELECTOR, "span.selectable-text, div.copyable-text, [dir='ltr'], [dir='rtl']")
            for te in text_elems:
                t = te.text.strip()
                if t:
                    text = t
                    break
            
            if not text:
                return None
            
            fingerprint = f"{contact}::{text}"
            if fingerprint in self.replied_fingerprints:
                return None
            
            return {
                "contact": contact,
                "text": text,
                "fingerprint": fingerprint,
                "data_id": ""
            }
            
        except Exception as e:
            logger.debug(f"Error inspecting latest message: {e}")
            return None

    def is_automated_or_broadcast(self, contact: str, message: str) -> bool:
        """
        Determine if a message is an automated broadcast, commercial alert, OTP, or announcement
        that a human would NOT reply to.
        """
        contact_lower = contact.lower()
        automated_contacts = [
            "domino", "swiggy", "zomato", "uber", "ola", "amazon", "flipkart",
            "bank", "hdfc", "sbi", "icici", "axis", "kotak", "paytm", "phonepe",
            "otp", "alert", "service", "notification", "support", "broadcast",
            "official", "update", "promo", "marketing"
        ]
        if any(ac in contact_lower for ac in automated_contacts):
            return True
            
        msg_lower = message.lower()
        automated_patterns = [
            "dear customer", "account alert",
            "credited successfully", "debited successfully",
            "wallet has been credited", "wallet has been debited",
            "thanks for choosing domino", "thank you for choosing",
            "otp is", "verification code", "one time password",
            "never share your otp", "do not share this otp",
            "reply stop to unsubscribe"
        ]
        if any(pat in msg_lower for pat in automated_patterns):
            return True
            
        return False



    def generate_ai_reply(self, contact: str, message_text: str) -> str:
        """
        Use Groq LLM to generate a natural, human reply representing Dhanush.
        """
        human_system_prompt = (
            f"You are {self.user_name}. You are texting a contact on WhatsApp from your personal phone.\n"
            "Write a single, natural, casual reply representing yourself.\n\n"
            "STRICT RULES:\n"
            "1. If the message is an automated promotional ad, marketing spam, OTP, bank alert, or broadcast announcement not meant for personal 1-on-1 human conversation, respond with ONLY the single word: IGNORE\n"
            f"2. Speak naturally in first person as {self.user_name}.\n"
            "3. Keep it brief: 1 short sentence or casual phrase (e.g. \"Hey! Yeah, give me a few minutes.\", \"Sure, sounds good!\", \"Haha cool, on it!\", \"Hey, what's up?\").\n"
            "4. NEVER say you are an AI, a language model, an assistant, or a bot.\n"
            "5. NEVER mention tasks, tools, systems, code, loops, or automation.\n"
            "6. NEVER use bullet points, numbered lists, markdown formatting, or quotation marks.\n"
            "7. Respond ONLY with the exact text message to be sent, or IGNORE. Nothing else."
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
            
            if reply.strip().upper() == "IGNORE":
                return "IGNORE"
            
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
        Uses native Selenium typing with Lexical React support and Enter key / Send button.
        """
        if not self.driver:
            return False
        
        selectors = [
            "#main footer div[contenteditable='true']",
            "#main div[contenteditable='true'][role='textbox']",
            "div[data-testid='conversation-compose-box-input']",
            "footer div[contenteditable='true']",
            "#main footer [role='textbox']",
            "div[aria-label*='Type a message' i]",
            "#main [contenteditable='true']"
        ]
        
        input_elem = None
        start_t = time.time()
        while time.time() - start_t < 4.0:
            for sel in selectors:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in elems:
                        input_elem = el
                        break
                    if input_elem:
                        break
                except Exception:
                    continue
            if input_elem:
                break
            time.sleep(0.3)
        
        if not input_elem:
            logger.warning("Could not locate WhatsApp message input box.")
            return False
        
        try:
            # 1. Click and focus the input element
            try:
                input_elem.click()
            except Exception:
                self.driver.execute_script("arguments[0].focus();", input_elem)
            time.sleep(0.2)
            
            # 2. Type via Selenium send_keys (proven to work with WhatsApp Lexical editor)
            input_elem.send_keys(reply_text)
            time.sleep(0.3)
            
            # 3. Press ENTER to send
            input_elem.send_keys(Keys.ENTER)
            time.sleep(0.4)
            
            # 4. Also click send button via JS if still present
            self.driver.execute_script("""
                const footer = document.querySelector("#main footer") || document.querySelector("footer");
                if (footer) {
                    const sendBtn = footer.querySelector(
                        "button[aria-label='Send'], button[data-testid='compose-btn-send'], span[data-icon='send'], span[data-icon*='send'], span[data-icon*='send-filled']"
                    );
                    if (sendBtn) {
                        const btn = sendBtn.tagName.toLowerCase() === 'button' ? sendBtn : sendBtn.closest('button');
                        if (btn) btn.click();
                    }
                }
            """)
            time.sleep(0.3)
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
            
            # 1. Open any unread chat in sidebar
            self.check_unread_chats()
            
            # 2. Check active chat for new incoming message
            msg_info = self.get_latest_message_info()
            
            # Heartbeat print every 15 seconds so user knows bot is actively monitoring
            now = time.time()
            if not hasattr(self, "_last_heartbeat"):
                self._last_heartbeat = 0
            if now - self._last_heartbeat > 15:
                self._last_heartbeat = now
                curr_chat = self.get_active_chat_title()
                if curr_chat and curr_chat != "Unknown":
                    print(f"⏳ [Active] Listening for messages in: \"{curr_chat}\"...")
                else:
                    print(f"⏳ [Active] Listening for incoming messages...")
            
            if not msg_info:
                return None
            
            contact = msg_info["contact"]
            incoming_text = msg_info["text"]
            fingerprint = msg_info["fingerprint"]
            
            # 3. Filter only obvious commercial marketing/OTP broadcasts
            if self.is_automated_or_broadcast(contact, incoming_text):
                self.replied_fingerprints.add(fingerprint)
                print(f"ℹ️ [Skipped] Message from \"{contact}\" is an automated broadcast/promotional alert. No reply needed.")
                return None

            print("\n" + "─" * 60)
            print(f"📩 [New Message] from: {contact}")
            print(f"💬 Message: \"{incoming_text}\"")
            print(f"👤 Generating reply as {self.user_name} via Groq...")
            
            # 4. Generate AI reply
            ai_reply = self.generate_ai_reply(contact, incoming_text)
            
            if ai_reply == "IGNORE":
                self.replied_fingerprints.add(fingerprint)
                print(f"ℹ️ [Ignored] Message flagged as not requiring reply.")
                print("─" * 60 + "\n")
                return None
                
            print(f"✨ Reply: \"{ai_reply}\"")
            
            # 5. Send the reply
            sent = self.send_reply(ai_reply)
            
            # ALWAYS record fingerprint to prevent repeated loops
            self.replied_fingerprints.add(fingerprint)
            
            if sent:
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
                err_str = str(e).lower()
                if any(x in err_str for x in ["refused", "disconnected", "closed", "invalid session", "target machine", "connection reset"]):
                    print("\nℹ️ Browser closed or disconnected. Exiting WhatsApp Auto-Responder.")
                    self.is_running = False
                    break
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(poll_interval)
        
        print("🛑 WhatsApp Auto-Responder stopped.")

    def stop(self):
        """Stop the listening loop"""
        self.is_running = False
