"""
Octopus Browser Engine - Selenium Integration

This module provides the browser engine that executes tool commands.
Currently uses Selenium WebDriver, with Playwright as a future option.
"""

from typing import Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


class BrowserEngine:
    """
    Browser Engine for Octopus
    
    Manages the Selenium WebDriver instance and provides
    low-level browser control for the tool layer.
    """
    
    def __init__(
        self, 
        headless: bool = False, 
        chrome_path: Optional[str] = None, 
        user_data_dir: Optional[str] = None,
        profile_directory: Optional[str] = "Default"
    ):
        self.driver: Optional[webdriver.Chrome] = None
        self.headless = headless
        self.chrome_path = chrome_path
        self.user_data_dir = user_data_dir
        self.profile_directory = profile_directory
        self.is_initialized = False
    
    def initialize(self) -> Dict[str, Any]:
        """
        Initialize the Chrome WebDriver
        
        Returns status dict with success/error info
        """
        try:
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument("--headless=new")
            
            if self.user_data_dir:
                import os
                abs_profile = os.path.abspath(self.user_data_dir)
                os.makedirs(abs_profile, exist_ok=True)
                chrome_options.add_argument(f"--user-data-dir={abs_profile}")
            
            if self.profile_directory:
                chrome_options.add_argument(f"--profile-directory={self.profile_directory}")
            
            # Disable profile picker and crash recovery prompts to prevent blocking
            chrome_options.add_argument("--disable-profile-picker")
            chrome_options.add_argument("--no-first-run")
            chrome_options.add_argument("--no-default-browser-check")
            chrome_options.add_argument("--disable-session-crashed-bubble")
            chrome_options.add_argument("--hide-crash-restore-bubble")
            
            # Standard options for automation
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            
            # Prevent detection
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            
            # Set user agent
            chrome_options.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Initialize driver
            if self.chrome_path:
                service = Service(self.chrome_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                try:
                    self.driver = webdriver.Chrome(options=chrome_options)
                except Exception:
                    try:
                        from webdriver_manager.chrome import ChromeDriverManager
                        service = Service(ChromeDriverManager().install())
                        self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    except Exception:
                        raise
            
            # Execute CDP command to hide automation
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                """
            })
            
            # Auto-click profile if Chrome opens profile-picker page
            try:
                if "profile-picker" in (self.driver.current_url or "").lower():
                    self.auto_select_profile()
            except Exception:
                pass
            
            self.is_initialized = True
            
            return {
                "success": True,
                "message": "Browser initialized successfully",
                "headless": self.headless
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to initialize browser"
            }
    
    def get_driver(self) -> Optional[webdriver.Chrome]:
        """Get the WebDriver instance"""
        return self.driver
    
    def is_ready(self) -> bool:
        """Check if browser is ready for automation"""
        return self.is_initialized and self.driver is not None

    def get_current_url(self) -> Optional[str]:
        """Get current URL if browser is ready, else None"""
        if self.is_ready() and self.driver:
            try:
                return self.driver.current_url
            except Exception:
                return None
        return None
    
    def navigate_to(self, url: str) -> Dict[str, Any]:
        """Navigate to a URL"""
        if not self.is_ready():
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            self.driver.get(url)
            return {
                "success": True,
                "url": self.driver.current_url,
                "title": self.driver.title
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_page_info(self) -> Dict[str, Any]:
        """Get current page information"""
        if not self.is_ready():
            return {"success": False, "error": "Browser not initialized"}
        
        return {
            "success": True,
            "url": self.driver.current_url,
            "title": self.driver.title,
            "page_source_length": len(self.driver.page_source)
        }
    
    def take_screenshot(self) -> Dict[str, Any]:
        """Take a screenshot"""
        if not self.is_ready():
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            screenshot = self.driver.get_screenshot_as_base64()
            return {
                "success": True,
                "screenshot_base64": screenshot,
                "url": self.driver.current_url
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def open_tab(self, url: str) -> Dict[str, Any]:
        """Open a new tab with the given URL and switch to it"""
        if not self.is_ready():
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            self.driver.execute_script("window.open(arguments[0], '_blank');", url)
            new_handle = self.driver.window_handles[-1]
            self.driver.switch_to.window(new_handle)
            return {
                "success": True,
                "handle": new_handle,
                "url": self.driver.current_url,
                "title": self.driver.title,
                "tab_count": len(self.driver.window_handles)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def switch_to_tab(self, identifier: Any) -> Dict[str, Any]:
        """
        Switch to a tab by index (int) or handle/URL keyword (str)
        """
        if not self.is_ready():
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            handles = self.driver.window_handles
            target = None
            if isinstance(identifier, int):
                if 0 <= identifier < len(handles):
                    target = handles[identifier]
                else:
                    return {"success": False, "error": f"Tab index {identifier} out of range (0-{len(handles)-1})"}
            elif isinstance(identifier, str):
                if identifier in handles:
                    target = identifier
                else:
                    # Match by URL or title substring
                    for h in handles:
                        self.driver.switch_to.window(h)
                        if identifier.lower() in self.driver.current_url.lower() or identifier.lower() in self.driver.title.lower():
                            target = h
                            break
                    if not target:
                        return {"success": False, "error": f"Tab matching '{identifier}' not found"}
            else:
                return {"success": False, "error": f"Invalid tab identifier: {identifier}"}

            self.driver.switch_to.window(target)
            return {
                "success": True,
                "handle": target,
                "url": self.driver.current_url,
                "title": self.driver.title
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_current_handle(self) -> Optional[str]:
        """Safely get the current window handle without raising an exception"""
        if not self.is_ready():
            return None
        try:
            return self.driver.current_window_handle
        except Exception:
            return None

    def is_alive(self) -> bool:
        """Check if the browser session is active and responsive"""
        return self.get_current_handle() is not None


    def get_tabs(self) -> Dict[str, Any]:
        """List all open tabs with their handles, URLs, and titles"""
        if not self.is_ready():
            return {"success": False, "error": "Browser not initialized", "tabs": []}
        
        try:
            current = self.driver.current_window_handle
            tabs_info = []
            for idx, h in enumerate(self.driver.window_handles):
                self.driver.switch_to.window(h)
                tabs_info.append({
                    "index": idx,
                    "handle": h,
                    "url": self.driver.current_url,
                    "title": self.driver.title,
                    "is_active": (h == current)
                })
            self.driver.switch_to.window(current)
            return {"success": True, "tabs": tabs_info, "count": len(tabs_info)}
        except Exception as e:
            return {"success": False, "error": str(e), "tabs": []}

    def close_current_tab(self) -> Dict[str, Any]:
        """Close current tab and switch to remaining active tab"""
        if not self.is_ready():
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            handles = self.driver.window_handles
            if len(handles) <= 1:
                return {"success": False, "error": "Cannot close the only open tab"}
            
            self.driver.close()
            remaining = self.driver.window_handles
            self.driver.switch_to.window(remaining[-1])
            return {
                "success": True,
                "remaining_tabs": len(remaining),
                "current_url": self.driver.current_url
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def auto_select_profile(self) -> bool:
        """
        Auto-click the main profile card if Chrome shows the profile picker page.
        """
        if not self.is_ready():
            return False
        try:
            # JavaScript to penetrate shadow DOM of profile-picker-app
            script = """
                const app = document.querySelector('profile-picker-app');
                if (app && app.shadowRoot) {
                    const mainView = app.shadowRoot.querySelector('profile-picker-main-view');
                    if (mainView && mainView.shadowRoot) {
                        const cards = mainView.shadowRoot.querySelectorAll('profile-card');
                        for (let c of cards) {
                            const nameEl = c.shadowRoot ? c.shadowRoot.querySelector('#profileName') : null;
                            const nameText = nameEl ? nameEl.textContent : '';
                            if (nameText.toLowerCase().includes('dhanush')) {
                                c.click();
                                return true;
                            }
                        }
                        if (cards.length > 0) {
                            cards[0].click();
                            return true;
                        }
                    }
                }
                const regularCard = document.querySelector('.profile-card, profile-card');
                if (regularCard) {
                    regularCard.click();
                    return true;
                }
                return false;
            """
            res = self.driver.execute_script(script)
            return bool(res)
        except Exception:
            return False

    def quit(self) -> Dict[str, Any]:
        """Close the browser and quit the driver safely without connection spam"""
        if not self.driver:
            self.is_initialized = False
            return {"success": True, "message": "Browser already closed"}
        
        try:
            # Temporarily suppress urllib3 retry warnings while tearing down
            import logging
            logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
            self.driver.quit()
        except Exception:
            pass
        finally:
            self.is_initialized = False
            self.driver = None
        return {"success": True, "message": "Browser closed"}
    
    def __enter__(self):
        """Context manager entry"""
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure browser is closed"""
        if self.is_ready():
            self.quit()


# Example usage
if __name__ == "__main__":
    print("Testing Browser Engine...")
    
    # Create engine (don't actually start browser in this demo)
    engine = BrowserEngine(headless=True)
    
    # Show what would happen
    print("\nBrowser Engine Configuration:")
    print(f"Headless: {engine.headless}")
    print(f"Ready: {engine.is_ready()}")
    
    # Note: Uncomment below to actually test with browser
    # result = engine.initialize()
    # print(f"\nInitialize result: {result}")
    # 
    # if engine.is_ready():
    #     nav_result = engine.navigate_to("https://www.google.com")
    #     print(f"Navigated: {nav_result}")
    #     
    #     info = engine.get_page_info()
    #     print(f"Page info: {info}")
    #     
    #     engine.quit()
