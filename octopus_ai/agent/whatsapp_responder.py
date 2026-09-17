"""
Octopus AI - WhatsApp Web Auto-Responder

Monitors WhatsApp Web in real-time, detects incoming messages,
and automatically generates and sends contextual replies using Groq LLM.
"""

import time
import asyncio
import logging
from typing import Optional, Dict, Any, Set, List
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
        user_name: str = "Dhanush",
        inactivity_limit_seconds: float = 25.0
    ):
        self.driver = driver
        self.llm = groq_llm or GroqLLM()
        self.memory = memory or Memory()
        self.allow_group_replies = allow_group_replies
        self.user_name = user_name
        self.inactivity_limit_seconds = inactivity_limit_seconds
        self.last_activity_timestamp: float = 0.0
        self.active_chat_contact: Optional[str] = None
        self.replied_fingerprints: Set[str] = set()
        self.sent_replies_history: Set[str] = set()
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

    def is_conversation_open(self) -> bool:
        """Check if a conversation pane (#main) is currently open in WhatsApp Web."""
        if not self.driver:
            return False
        try:
            return bool(self.driver.execute_script("""
                const main = document.querySelector("#main");
                return !!main && main.offsetParent !== null;
            """))
        except Exception:
            return False

    def is_contact_typing(self) -> bool:
        """
        Check if the contact in the active WhatsApp conversation is currently typing.
        Inspects WhatsApp Web header subtitle and typing indicators across languages.
        """
        if not self.driver:
            return False
        
        try:
            res = self.driver.execute_script("""
                const header = document.querySelector("#main header") || document.querySelector("header");
                if (!header) return false;
                
                // 1. Check header text for 'typing' in multiple languages
                const txt = (header.innerText || header.textContent || "").toLowerCase();
                const typingWords = [
                    "typing", "రైటింగ్", "టైపింగ్", "టైప్", "टाइपिंग", "टाइप", 
                    "escribiendo", "digitando", "écrit", "schreibt", "sta scrivendo",
                    "aan het typen", "pisze", "yazıyor"
                ];
                for (const word of typingWords) {
                    if (txt.includes(word)) return true;
                }
                
                // 2. Check for animated typing indicators, SVGs, or dedicated spans
                const typingSelectors = [
                    "[data-testid='typing']",
                    "[data-icon*='typing']",
                    "span[title*='typing' i]",
                    "span[aria-label*='typing' i]",
                    "div._ak8q",
                    "span._ak8i"
                ];
                for (const sel of typingSelectors) {
                    const el = header.querySelector(sel);
                    if (el) {
                        const elTxt = (el.textContent || el.getAttribute("title") || "").toLowerCase();
                        if (elTxt.includes("typing") || elTxt.includes("టైపింగ్") || elTxt.includes("రైటింగ్")) {
                            return true;
                        }
                    }
                }
                
                return false;
            """)
            return bool(res)
        except Exception:
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
        Accurately identifies if last message is outgoing or incoming, extracts clean text,
        and collects recent conversation history for LLM context.
        """
        if not self.driver:
            return None
        
        script = """
            const activeContact = arguments[0] || "Friend";
            const userName = arguments[1] || "Dhanush";
            
            const result = (function() {
                const mainPane = document.querySelector("#main") || document;
                const rows = mainPane.querySelectorAll("div[data-id], div[class*='message-in'], div[class*='message-out'], div[role='row']");
                if (!rows || rows.length === 0) {
                    return null;
                }
                
                // Helper to extract text from a row
                function extractRowText(rowEl) {
                    const textSelectors = [
                        "span.selectable-text",
                        "div.copyable-text span",
                        "span._ao3e",
                        "span[dir='ltr']",
                        "span[dir='rtl']",
                        "span[dir='auto']",
                        "div.copyable-text"
                    ];
                    let raw = "";
                    for (let sel of textSelectors) {
                        const el = rowEl.querySelector(sel);
                        if (el && el.textContent.trim()) {
                            const meta = rowEl.querySelector("[data-testid='msg-meta'], span[data-testid='msg-time']");
                            if (meta && el.contains(meta)) continue;
                            raw = el.textContent.trim();
                            break;
                        }
                    }
                    if (!raw) {
                        const meta = rowEl.querySelector("[data-testid='msg-meta'], span[data-testid='msg-time']");
                        const metaText = meta ? meta.textContent : "";
                        raw = rowEl.textContent.replace(metaText, "").trim();
                    }
                    
                    // Deduplicate repeated text from WhatsApp Web accessibility mirrors
                    if (raw.length > 4 && raw.length % 2 === 0) {
                        const half = raw.length / 2;
                        if (raw.substring(0, half) === raw.substring(half)) {
                            raw = raw.substring(0, half);
                        }
                    }
                    return raw;
                }
                
                // 1. Build recent conversation context (last 6-8 valid messages)
                const recentHistory = [];
                const scanStart = Math.max(0, rows.length - 12);
                for (let i = scanStart; i < rows.length; i++) {
                    const row = rows[i];
                    const cls = (row.className || "") + " " + (row.parentElement ? row.parentElement.className || "" : "");
                    if (cls.includes("system-message") || row.querySelector("[data-testid='system-message']")) {
                        continue;
                    }
                    
                    const dataId = row.getAttribute("data-id") || (row.querySelector("[data-id]") ? row.querySelector("[data-id]").getAttribute("data-id") : "");
                    const hasChecks = !!row.querySelector("[data-icon='msg-check'], [data-icon='msg-dblcheck'], [data-icon='msg-time'], [data-icon*='check'], [data-icon*='time']");
                    const hasOutCls = cls.includes("message-out") || !!row.querySelector("[class*='message-out']");
                    const isDataIdOut = dataId.startsWith("true_");
                    
                    const copyable = row.querySelector(".copyable-text, [data-pre-plain-text]");
                    const prePlainText = copyable ? (copyable.getAttribute("data-pre-plain-text") || "") : "";
                    const isPrePlainOut = prePlainText.includes("You:") || prePlainText.includes("You :") || prePlainText.toLowerCase().includes(userName.toLowerCase() + ":");
                    
                    const isOut = isDataIdOut || hasChecks || hasOutCls || isPrePlainOut;
                    const rowText = extractRowText(row);
                    
                    if (rowText) {
                        let senderName = isOut ? userName : activeContact;
                        if (!isOut && prePlainText) {
                            const match = prePlainText.match(/\\]\\s*([^:]+):/);
                            if (match && match[1]) senderName = match[1].trim();
                        }
                        recentHistory.push({
                            sender: senderName,
                            text: rowText,
                            is_outgoing: isOut
                        });
                    }
                }
                
                // 2. Scan backwards from the newest message to collect consecutive incoming messages (burst)
                // until we hit our own outgoing message or the start of recent history.
                const incomingBurst = [];
                let isOutgoing = false;
                let lastDataId = "";

                for (let i = rows.length - 1; i >= 0; i--) {
                    const row = rows[i];
                    const cls = (row.className || "") + " " + (row.parentElement ? row.parentElement.className || "" : "");
                    if (cls.includes("system-message") || row.querySelector("[data-testid='system-message']")) {
                        continue;
                    }
                    
                    const dataId = row.getAttribute("data-id") || (row.querySelector("[data-id]") ? row.querySelector("[data-id]").getAttribute("data-id") : "");
                    const hasChecks = !!row.querySelector("[data-icon='msg-check'], [data-icon='msg-dblcheck'], [data-icon='msg-time'], [data-icon*='check'], [data-icon*='time']");
                    const hasOutCls = cls.includes("message-out") || !!row.querySelector("[class*='message-out']");
                    const isDataIdOut = dataId.startsWith("true_");
                    
                    const copyable = row.querySelector(".copyable-text, [data-pre-plain-text]");
                    const prePlainText = copyable ? (copyable.getAttribute("data-pre-plain-text") || "") : "";
                    const isPrePlainOut = prePlainText.includes("You:") || prePlainText.includes("You :") || prePlainText.toLowerCase().includes(userName.toLowerCase() + ":");
                    
                    const isOut = isDataIdOut || hasChecks || hasOutCls || isPrePlainOut;
                    
                    if (isOut) {
                        if (incomingBurst.length === 0) {
                            isOutgoing = true;
                            lastDataId = dataId;
                        }
                        break;
                    }
                    
                    const hasInCls = cls.includes("message-in") || !!row.querySelector("[class*='message-in']");
                    const isDataIdIn = dataId.startsWith("false_");
                    const isPrePlainIn = prePlainText.length > 0 && !isPrePlainOut;
                    const isIn = (isDataIdIn || hasInCls || isPrePlainIn) && !hasChecks;
                    
                    if (isIn) {
                        const rowText = extractRowText(row);
                        if (rowText) {
                            let senderName = activeContact;
                            if (prePlainText) {
                                const match = prePlainText.match(/\\]\\s*([^:]+):/);
                                if (match && match[1]) senderName = match[1].trim();
                            }
                            incomingBurst.unshift({
                                text: rowText,
                                data_id: dataId,
                                sender: senderName
                            });
                        }
                    } else {
                        // Unclassified message: treat as outgoing to prevent infinite loop
                        if (incomingBurst.length === 0) {
                            isOutgoing = true;
                            lastDataId = dataId;
                        }
                        break;
                    }
                }
                
                if (incomingBurst.length === 0) {
                    if (isOutgoing) {
                        return { is_outgoing: true, is_incoming: false, data_id: lastDataId, recent_history: recentHistory };
                    }
                    return null;
                }
                
                // Construct composite burst representation
                const burstTexts = incomingBurst.map(b => b.text);
                const burstDataIds = incomingBurst.map(b => b.data_id).filter(Boolean);
                const lastIncoming = incomingBurst[incomingBurst.length - 1];
                const compositeText = burstTexts.join("\n");
                
                return {
                    is_outgoing: false,
                    is_incoming: true,
                    is_burst: incomingBurst.length > 1,
                    burst_messages: burstTexts,
                    burst_data_ids: burstDataIds,
                    data_id: lastIncoming.data_id || "",
                    sender: lastIncoming.sender || activeContact,
                    text: compositeText,
                    recent_history: recentHistory
                };
            })();
            return result;
        """
        try:
            contact = self.get_active_chat_title()
            return self.driver.execute_script(script, contact, self.user_name)
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
                is_burst = js_res.get("is_burst", False)
                burst_messages = js_res.get("burst_messages", [text])
                burst_data_ids = js_res.get("burst_data_ids", [data_id] if data_id else [])
                sender = js_res.get("sender", contact)
                
                if not text:
                    return None
                
                # Group chat selective filtering
                if self.is_group_chat():
                    if not self.allow_group_replies:
                        return None
                    if not self.should_reply_to_group_message(contact, text, sender=sender, recent_history=js_res.get("recent_history")):
                        fingerprint = f"{contact}::{text}"
                        self.replied_fingerprints.add(fingerprint)
                        for b_id in burst_data_ids:
                            if b_id:
                                self.replied_fingerprints.add(f"{contact}::{b_id}")
                        return None
                
                # WhatsApp Web text deduplication safeguard
                if len(text) > 4 and len(text) % 2 == 0:
                    half = len(text) // 2
                    if text[:half] == text[half:]:
                        text = text[:half]
                
                clean_text = text.strip().lower()
                
                # Self-chat prevention: Verify text does not match our own sent replies
                if clean_text in self.sent_replies_history:
                    logger.info(f"Ignoring message because it matches our own recently sent reply: '{text}'")
                    return None
                
                for sent_msg in self.sent_replies_history:
                    if len(sent_msg) >= 8 and (clean_text == sent_msg or clean_text.startswith(sent_msg) or sent_msg.startswith(clean_text)):
                        logger.info(f"Ignoring message matching sent reply history prefix: '{text}'")
                        return None
                
                # Fingerprint combining contact, text, and data_id
                fingerprint = f"{contact}::{text}"
                if data_id:
                    fingerprint = f"{contact}::{data_id}::{text}"
                
                if fingerprint in self.replied_fingerprints:
                    return None
                for b_id in burst_data_ids:
                    if b_id and f"{contact}::{b_id}" in self.replied_fingerprints and not is_burst:
                        return None
                
                return {
                    "contact": contact,
                    "text": text,
                    "fingerprint": fingerprint,
                    "data_id": data_id,
                    "is_burst": is_burst,
                    "burst_messages": burst_messages,
                    "burst_data_ids": burst_data_ids,
                    "sender": sender,
                    "recent_history": js_res.get("recent_history", [])
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
            data_id = last_msg.get_attribute("data-id") or ""
            
            # Check checkmarks
            has_checks = len(last_msg.find_elements(By.CSS_SELECTOR, "[data-icon='msg-check'], [data-icon='msg-dblcheck'], [data-icon='msg-time'], [data-icon*='check']")) > 0
            
            # Check data-pre-plain-text
            copyable_elems = last_msg.find_elements(By.CSS_SELECTOR, ".copyable-text, [data-pre-plain-text]")
            pre_text = ""
            if copyable_elems:
                pre_text = copyable_elems[0].get_attribute("data-pre-plain-text") or ""
            
            is_out = (
                "message-out" in classes 
                or data_id.startswith("true_") 
                or has_checks 
                or "you:" in pre_text.lower()
                or self.user_name.lower() in pre_text.lower()
            )
            if is_out:
                return None
            
            is_in = (
                ("message-in" in classes or data_id.startswith("false_")) 
                and not has_checks
            )
            if not is_in:
                # Ambiguous: safety first, do not reply
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
            
            # Deduplicate text
            if len(text) > 4 and len(text) % 2 == 0:
                half = len(text) // 2
                if text[:half] == text[half:]:
                    text = text[:half]
            
            clean_text = text.strip().lower()
            if clean_text in self.sent_replies_history:
                logger.info(f"Ignoring message because it matches our own recently sent reply: '{text}'")
                return None
            
            fingerprint = f"{contact}::{text}"
            if fingerprint in self.replied_fingerprints:
                return None
            
            return {
                "contact": contact,
                "text": text,
                "fingerprint": fingerprint,
                "data_id": data_id,
                "recent_history": []
            }
            
        except Exception as e:
            logger.debug(f"Error inspecting latest message: {e}")
            return None

    def should_reply_to_group_message(
        self,
        contact: str,
        message_text: str,
        sender: Optional[str] = None,
        recent_history: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Intelligent gating for WhatsApp Group chats:
        Ignores low-value chatter, generic reactions, announcements,
        or messages clearly addressed to other members.
        """
        msg_lower = message_text.lower().strip()

        # 1. Automated/broadcast messages
        if self.is_automated_or_broadcast(contact, message_text):
            return False

        # 2. Low-entropy reactions, single-word chatter, emojis
        low_entropy = {
            "ok", "k", "okay", "kk", "hmmm", "hmm", "hm", "lol", "lmao", "rofl",
            "haha", "hahaha", "cool", "nice", "great", "fine", "done", "yes", "no",
            "yeah", "yep", "nope", "sare", "avunu", "ayyo", "super", "gm", "gn",
            "good morning", "good night", "tq", "thanks", "thank you", "welcome",
            "+1", "congrats", "congratulations", "happy birthday", "hbd"
        }
        if msg_lower in low_entropy or len(msg_lower) <= 2:
            logger.info(f"Group filter: skipping low-entropy reaction '{message_text}' in '{contact}'")
            return False

        # Drop messages with no alphanumeric characters (pure emojis)
        cleaned_chars = [c for c in msg_lower if c.isalnum()]
        if len(cleaned_chars) == 0:
            return False

        # 3. Explicitly addressed to another person (e.g. '@Someone', 'Ramesh bro', 'Rahul:')
        user_aliases = ["dhanush", "dhanu", "gangani", "saiteja", "pacifica"]
        if "@" in msg_lower:
            has_self_mention = any(alias in msg_lower for alias in user_aliases)
            if not has_self_mention:
                logger.info(f"Group filter: message addressed to someone else ('{message_text}')")
                return False

        # Check if message starts with another member's name followed by punctuation
        # e.g., "Kiran, did you submit?" or "Ajay: check this"
        first_word = msg_lower.split()[0].rstrip(",:;-")
        if first_word not in user_aliases and any(msg_lower.startswith(f"{first_word}{sep}") for sep in [",", ":", " -"]):
            return False

        # 4. If Dhanush is explicitly tagged or mentioned, definitely reply!
        if any(alias in msg_lower for alias in user_aliases):
            return True

        # 5. For general group chatter: only reply if it's an open substantive question
        is_question = "?" in message_text or any(msg_lower.startswith(q) for q in [
            "who", "what", "where", "when", "why", "how", "anyone", "anybody", "can someone", "does anyone"
        ])
        if is_question and len(message_text.split()) >= 3:
            return True

        # By default in group chats, stay quiet on incidental chatter
        logger.info(f"Group filter: staying silent on incidental group chatter in '{contact}'")
        return False

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



    def generate_ai_reply(
        self, 
        contact: str, 
        message_text: str, 
        recent_history: Optional[List[Dict[str, Any]]] = None,
        burst_messages: Optional[List[str]] = None
    ) -> str:
        """
        Use Groq LLM to generate a natural, human reply representing Dhanush.
        Authentically matches the sender's slang and language (Telugu/Hinglish/English),
        and responds directly to context in 3-10 words.
        If a multi-message burst was sent, synthesizes ONE cohesive reply.
        """
        human_system_prompt = (
            f"You are {self.user_name}, a friendly, chill young Indian college student and developer chatting with friends on WhatsApp.\n"
            "You are texting friends from your personal phone.\n\n"
            "CRITICAL TONE & SLANG MATCHING RULES:\n"
            "1. Always match the sender's language, dialect, and slang naturally:\n"
            "   • If they text in Telugu / Telugu-English (e.g., 'mana peru undhi roiii', 'Finally chip dobinda', 'enti bro', 'avuna', 'inkenti', 'cheppu', 'ekkadunnav', 'ledu', 'chudu'):\n"
            "     Reply naturally in authentic, casual Telugu/English mix (e.g., 'Haha avuna roiii! Super!', 'Haha ledu bro, inka raledhu', 'Haha anthe anthe!', 'Nuvvu cheppu enti sangathi', 'Chusa bro haha!', 'Ledu bro inka announce cheyaledhu').\n"
            "   • If they text in Hindi / Hinglish (e.g., 'kya kar raha hai bro', 'scene kya hai', 'free hai kya', 'bhai sun'):\n"
            "     Reply casually in Hinglish (e.g., 'Arre bas chill kar raha, tu bata', 'Haan bol bhai kya scene', 'Thoda busy hu abhi, 10 min me bolta hu').\n"
            "   • If they text in English / casual college slang (e.g., 'are you free bro', 'did you push the code', 'check this out'):\n"
            "     Reply in casual conversational Indian English (e.g., 'Yeah bro checking it now', 'Haha yeah finally done', 'Busy right now, ping you in a bit').\n"
            "2. Length: Keep it ultra-realistic and brief: 3 to 10 words. Real people on WhatsApp never send long or formal paragraphs.\n"
            "3. Directly answer or react to their message or question based on the conversation context. If they tease or joke, joke back casually.\n"
            "4. If the message is an automated commercial promotion, OTP, bank alert, or broadcast announcement not meant for 1-on-1 human chatting, reply with ONLY the single word: IGNORE\n"
            "5. ABSOLUTE PROHIBITIONS:\n"
            "   • NEVER say you are an AI, a language model, an assistant, or a bot.\n"
            "   • NEVER mention code, tasks, systems, tools, loops, or automation.\n"
            "   • NEVER use corporate formalities ('Hope you are doing well', 'How may I help you', 'Dear').\n"
            "   • NEVER use quotation marks, bullet points, markdown, or emoji spam (1 emoji max).\n"
            "   • Respond with ONLY the exact text message to send. Nothing else."
        )
        
        history_lines = []
        if recent_history:
            for item in recent_history[-6:]:
                sender = item.get("sender", "Friend")
                txt = item.get("text", "")
                if txt:
                    history_lines.append(f"{sender}: {txt}")

        burst_note = ""
        if burst_messages and len(burst_messages) > 1:
            burst_list = "\n".join(f"• \"{m}\"" for m in burst_messages)
            burst_note = f"\nNote: {contact} sent multiple messages in rapid succession (burst):\n{burst_list}\n"
        
        if history_lines:
            conv_context = "\n".join(history_lines)
            user_prompt = (
                f"Recent conversation:\n{conv_context}\n"
                f"{burst_note}\n"
                f"Incoming message(s) from {contact} to reply to: \"{message_text}\"\n"
                f"Provide ONE single cohesive natural reply addressing their complete thought."
            )
        else:
            user_prompt = (
                f"{burst_note}\n"
                f"Incoming WhatsApp message(s) from {contact}: \"{message_text}\"\n"
                f"Provide ONE single cohesive natural reply addressing their complete thought."
            )
        
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
                    reply = "Hey! Will get back to you shortly."
            
            if not reply:
                reply = "Hey! Will get back to you shortly."
            
            return reply
            
        except Exception as e:
            logger.error(f"Error generating AI reply: {e}")
            return "Hey! Will get back to you soon."

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
        Execute a single polling iteration with cross-tab support and 25-second chat retention:
        - Stays focused on the active chat as long as the contact is typing or sending messages.
        - Only checks or switches to another chat if the contact has stopped typing and been inactive for > 25 seconds.
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
            
            now = time.time()
            conv_open = self.is_conversation_open()
            active_title = self.get_active_chat_title() if conv_open else None
            
            # Sync active chat contact and initialize activity timestamp if newly opened
            if conv_open and active_title and active_title != "Unknown":
                if self.active_chat_contact != active_title:
                    self.active_chat_contact = active_title
                    self.last_activity_timestamp = now
                    logger.info(f"Switched to active chat: '{active_title}'. 25s inactivity timer initiated.")

            # Check if contact in active conversation is currently typing
            contact_typing = False
            if conv_open and self.active_chat_contact:
                contact_typing = self.is_contact_typing()
                if contact_typing:
                    self.last_activity_timestamp = now
                    logger.debug(f"{self.active_chat_contact} is typing... Activity timer refreshed.")

            # 1. 25-SECOND INACTIVITY RULE:
            # Only leave the chat if the contact is NOT typing and has had no new messages for > 25 seconds.
            can_switch_chat = True
            if conv_open and self.active_chat_contact:
                elapsed = now - self.last_activity_timestamp
                if contact_typing or elapsed < self.inactivity_limit_seconds:
                    can_switch_chat = False

            if can_switch_chat:
                # We are allowed to scan and open any unread chat in the sidebar
                opened = self.check_unread_chats()
                if opened:
                    self.active_chat_contact = self.get_active_chat_title()
                    self.last_activity_timestamp = time.time()
                    conv_open = True

            # 2. Check active chat for new incoming message
            msg_info = self.get_latest_message_info()
            
            # Heartbeat print every 15 seconds so user knows bot is actively monitoring
            if not hasattr(self, "_last_heartbeat"):
                self._last_heartbeat = 0
            if now - self._last_heartbeat > 15:
                self._last_heartbeat = now
                curr_chat = self.get_active_chat_title()
                if curr_chat and curr_chat != "Unknown":
                    status_extra = " (typing...)" if contact_typing else ""
                    print(f"⏳ [Active] Listening in: \"{curr_chat}\"{status_extra}...")
                else:
                    print(f"⏳ [Active] Listening for incoming messages...")
            
            if not msg_info:
                return None

            contact = msg_info["contact"]

            # Typing debounce: If contact is typing, wait 2.0s to let them finish sending their burst sequence
            if self.is_contact_typing():
                logger.info(f"Contact '{contact}' is typing. Waiting 2.0s for multi-message burst completion...")
                time.sleep(2.0)
                newer_info = self.get_latest_message_info()
                if newer_info:
                    msg_info = newer_info
            
            # We received an incoming message! Reset activity timestamp immediately
            self.last_activity_timestamp = time.time()
            
            contact = msg_info["contact"]
            incoming_text = msg_info["text"]
            fingerprint = msg_info["fingerprint"]
            recent_history = msg_info.get("recent_history", [])
            is_burst = msg_info.get("is_burst", False)
            burst_messages = msg_info.get("burst_messages", [incoming_text])
            burst_data_ids = msg_info.get("burst_data_ids", [])
            
            # 3. Filter only obvious commercial marketing/OTP broadcasts
            if self.is_automated_or_broadcast(contact, incoming_text):
                self.replied_fingerprints.add(fingerprint)
                for b_id in burst_data_ids:
                    if b_id:
                        self.replied_fingerprints.add(f"{contact}::{b_id}")
                print(f"ℹ️ [Skipped] Message from \"{contact}\" is an automated broadcast/promotional alert. No reply needed.")
                return None

            print("\n" + "─" * 60)
            if is_burst and len(burst_messages) > 1:
                print(f"📩 [Multi-Message Burst ({len(burst_messages)})] from: {contact}")
                for idx, b_m in enumerate(burst_messages, 1):
                    print(f"   {idx}. \"{b_m}\"")
            else:
                print(f"📩 [New Message] from: {contact}")
                print(f"💬 Message: \"{incoming_text}\"")
            print(f"👤 Generating reply as {self.user_name} via Groq...")
            
            # 4. Generate AI reply using full recent conversation context and burst sequence
            ai_reply = self.generate_ai_reply(
                contact, 
                incoming_text, 
                recent_history=recent_history,
                burst_messages=burst_messages
            )
            
            if ai_reply == "IGNORE":
                self.replied_fingerprints.add(fingerprint)
                for b_id in burst_data_ids:
                    if b_id:
                        self.replied_fingerprints.add(f"{contact}::{b_id}")
                print(f"ℹ️ [Ignored] Message flagged as not requiring reply.")
                print("─" * 60 + "\n")
                return None
                
            print(f"✨ Reply: \"{ai_reply}\"")
            
            # 5. Send the reply
            sent = self.send_reply(ai_reply)
            
            # Update activity timestamp upon sending reply
            self.last_activity_timestamp = time.time()
            
            # ALWAYS record fingerprint, burst data IDs, and burst texts to prevent repeated loops
            self.replied_fingerprints.add(fingerprint)
            for b_id in burst_data_ids:
                if b_id:
                    self.replied_fingerprints.add(f"{contact}::{b_id}")
            for b_msg in burst_messages:
                self.replied_fingerprints.add(f"{contact}::{b_msg}")
            self.sent_replies_history.add(ai_reply.strip().lower())
            if len(self.sent_replies_history) > 100:
                self.sent_replies_history.pop()
            
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
