"""
Octopus AI - Playwright Browser Engine
Comet-Grade Browser Automation Foundation (Stagehand + browser-use pattern)

Provides:
- Persistent profile support (real user cookies/sessions or automation profile)
- High-level primitives:
  - observe(): DOM and Accessibility snapshot with interactive element indexing
  - act(): Deterministic action execution (click, type, key, scroll, navigate)
  - extract(): Structured text and element extraction
  - screenshot(): Base64 or binary visual state capture
"""

import os
import sys
import json
import base64
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class PlaywrightEngine:
    """
    Asynchronous Playwright Browser Controller with persistent context support.
    """

    def __init__(
        self,
        headless: bool = False,
        user_data_dir: Optional[str] = None,
        channel: str = "chrome",
        viewport: Optional[Dict[str, int]] = None
    ):
        self.headless = headless
        self.user_data_dir = user_data_dir
        self.channel = channel
        self.viewport = viewport or {"width": 1280, "height": 800}

        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_ready: bool = False

    @property
    def is_available(self) -> bool:
        return PLAYWRIGHT_AVAILABLE

    def is_ready(self) -> bool:
        return self._is_ready and self._page is not None and not self._page.is_closed()

    async def initialize(self) -> Dict[str, Any]:
        """
        Launch persistent browser context or fallback to standard Chromium.
        """
        if not PLAYWRIGHT_AVAILABLE:
            return {"success": False, "error": "Playwright is not installed. Run 'pip install playwright'"}

        try:
            self._playwright = await async_playwright().start()

            args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]

            if self.user_data_dir:
                os.makedirs(self.user_data_dir, exist_ok=True)
                try:
                    self._context = await self._playwright.chromium.launch_persistent_context(
                        user_data_dir=self.user_data_dir,
                        channel=self.channel,
                        headless=self.headless,
                        viewport=self.viewport,
                        args=args
                    )
                except Exception as chrome_err:
                    print(f"[PlaywrightEngine] Launching with bundled Chromium (fallback from {self.channel}): {chrome_err}")
                    self._context = await self._playwright.chromium.launch_persistent_context(
                        user_data_dir=self.user_data_dir,
                        headless=self.headless,
                        viewport=self.viewport,
                        args=args
                    )
            else:
                browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    args=args
                )
                self._context = await browser.new_context(viewport=self.viewport)

            pages = self._context.pages
            if pages:
                self._page = pages[0]
            else:
                self._page = await self._context.new_page()

            self._is_ready = True
            return {"success": True, "message": "Playwright browser initialized"}
        except Exception as e:
            self._is_ready = False
            return {"success": False, "error": str(e)}

    async def goto(self, url: str, timeout: int = 30000) -> Dict[str, Any]:
        """Navigate to URL."""
        if not self.is_ready():
            init_res = await self.initialize()
            if not init_res.get("success"):
                return init_res

        try:
            if not url.startswith("http://") and not url.startswith("https://"):
                url = f"https://{url}"
            response = await self._page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            status = response.status if response else 200
            return {"success": True, "url": self._page.url, "status": status}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def observe(self) -> Dict[str, Any]:
        """
        Extract accessibility tree and interactive elements with index IDs.
        Provides a structured DOM snapshot for LLM decision making.
        """
        if not self.is_ready():
            return {"success": False, "error": "Browser is not initialized"}

        try:
            js_script = """
            () => {
                const elements = [];
                const selector = 'button, a, input, textarea, select, [role="button"], [role="link"], [tabindex]:not([tabindex="-1"])';
                const nodes = Array.from(document.querySelectorAll(selector));
                
                let idx = 0;
                for (const el of nodes) {
                    const rect = el.getBoundingClientRect();
                    const isVisible = rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden';
                    if (!isVisible) continue;

                    let text = (el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('title') || '').trim();
                    text = text.replace(/\\s+/g, ' ').substring(0, 100);

                    elements.push({
                        id: idx++,
                        tag: el.tagName.toLowerCase(),
                        type: el.getAttribute('type') || null,
                        role: el.getAttribute('role') || null,
                        text: text,
                        selector: el.id ? `#${el.id}` : (el.className ? `.${el.className.split(' ')[0]}` : el.tagName.toLowerCase()),
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
                    });
                    if (elements.length >= 60) break;
                }

                return {
                    url: window.location.href,
                    title: document.title,
                    interactive_elements: elements
                };
            }
            """
            snapshot = await self._page.evaluate(js_script)
            return {"success": True, "snapshot": snapshot}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def act(self, action_type: str, selector: Optional[str] = None, value: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform an action: 'click', 'type', 'press', 'scroll_down', 'scroll_up', 'wait'.
        """
        if not self.is_ready():
            return {"success": False, "error": "Browser is not ready"}

        try:
            action = action_type.lower()
            if action == "click":
                if not selector:
                    return {"success": False, "error": "Selector is required for click"}
                await self._page.click(selector, timeout=5000)
                return {"success": True, "action": "click", "selector": selector}

            elif action == "type":
                if not selector or value is None:
                    return {"success": False, "error": "Selector and value required for type"}
                await self._page.fill(selector, value, timeout=5000)
                return {"success": True, "action": "type", "selector": selector, "value": value}

            elif action == "press":
                key = value or "Enter"
                await self._page.keyboard.press(key)
                return {"success": True, "action": "press", "key": key}

            elif action in ["scroll_down", "scroll_up"]:
                delta = 500 if action == "scroll_down" else -500
                await self._page.mouse.wheel(0, delta)
                return {"success": True, "action": action}

            elif action == "wait":
                delay = float(value or 1.0)
                await asyncio.sleep(delay)
                return {"success": True, "action": "wait", "seconds": delay}

            else:
                return {"success": False, "error": f"Unknown action: {action_type}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def extract(self, query: Optional[str] = None) -> Dict[str, Any]:
        """Extract visible text content or search for specific text."""
        if not self.is_ready():
            return {"success": False, "error": "Browser is not ready"}

        try:
            text = await self._page.evaluate("() => document.body ? document.body.innerText : ''")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            cleaned_text = "\n".join(lines[:200])
            return {"success": True, "text": cleaned_text, "url": self._page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def screenshot(self, base64_encode: bool = True) -> Union[str, bytes, Dict[str, Any]]:
        """Capture screenshot of the active page."""
        if not self.is_ready():
            return {"success": False, "error": "Browser is not ready"}

        try:
            data = await self._page.screenshot(type="jpeg", quality=80)
            if base64_encode:
                return base64.b64encode(data).decode("utf-8")
            return data
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close(self):
        """Close page and context gracefully."""
        self._is_ready = False
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._page = None
