"""
Octopus Tool Layer - The Hands of the System

Tools are what the AI Agent calls to perform browser actions.
Each tool is executed by Selenium (or Playwright in future).

Available Tools:
- browser.open(url)
- browser.click(element)
- browser.type(element, text)
- browser.read()
- browser.scroll(direction)
- browser.wait(condition)
- browser.back()
- browser.refresh()
- browser.screenshot()
- browser.find(selector)
"""

from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod


class BaseTool(ABC):
    """Abstract base class for all browser automation tools"""
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool and return result"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Return description of what this tool does"""
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Return parameter schema for this tool"""
        pass


class BrowserOpenTool(BaseTool):
    """Open a URL in the browser"""
    
    def __init__(self, driver=None):
        self.driver = driver
    
    def execute(self, url: str, **kwargs) -> Dict[str, Any]:
        if not self.driver:
            return {"success": False, "error": "No browser driver available"}
        
        try:
            self.driver.get(url)
            return {
                "success": True,
                "url": url,
                "title": self.driver.title,
                "current_url": self.driver.current_url
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_description(self) -> str:
        return "Open a URL in the browser"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "url": {"type": "string", "required": True, "description": "URL to open"}
        }


class BrowserClickTool(BaseTool):
    """Click on an element"""
    
    def __init__(self, driver=None):
        self.driver = driver
    
    def execute(self, selector: str, selector_type: str = "css", **kwargs) -> Dict[str, Any]:
        if not self.driver:
            return {"success": False, "error": "No browser driver available"}
        
        try:
            from selenium.webdriver.common.by import By
            
            # Map selector type to Selenium By
            by_map = {
                "css": By.CSS_SELECTOR,
                "xpath": By.XPATH,
                "id": By.ID,
                "name": By.NAME,
                "class": By.CLASS_NAME,
                "tag": By.TAG_NAME
            }
            
            by = by_map.get(selector_type, By.CSS_SELECTOR)
            element = self.driver.find_element(by, selector)
            element.click()
            
            return {
                "success": True,
                "element": selector,
                "message": f"Clicked element: {selector}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_description(self) -> str:
        return "Click on a web element"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "selector": {"type": "string", "required": True, "description": "Element selector"},
            "selector_type": {
                "type": "string", 
                "required": False, 
                "default": "css",
                "enum": ["css", "xpath", "id", "name", "class", "tag"],
                "description": "Type of selector"
            }
        }


class BrowserTypeTool(BaseTool):
    """Type text into an input field"""
    
    def __init__(self, driver=None):
        self.driver = driver
    
    def execute(self, selector: str, text: str, selector_type: str = "css", 
                clear: bool = True, **kwargs) -> Dict[str, Any]:
        if not self.driver:
            return {"success": False, "error": "No browser driver available"}
        
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.keys import Keys
            
            by_map = {
                "css": By.CSS_SELECTOR,
                "xpath": By.XPATH,
                "id": By.ID,
                "name": By.NAME
            }
            
            by = by_map.get(selector_type, By.CSS_SELECTOR)
            element = self.driver.find_element(by, selector)
            
            if clear:
                element.clear()
            
            element.send_keys(text)
            
            return {
                "success": True,
                "element": selector,
                "text": text,
                "message": f"Typed '{text}' into {selector}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_description(self) -> str:
        return "Type text into an input field"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "selector": {"type": "string", "required": True, "description": "Input element selector"},
            "text": {"type": "string", "required": True, "description": "Text to type"},
            "selector_type": {
                "type": "string",
                "required": False,
                "default": "css",
                "description": "Type of selector"
            },
            "clear": {
                "type": "boolean",
                "required": False,
                "default": True,
                "description": "Whether to clear field first"
            }
        }


class BrowserReadTool(BaseTool):
    """Read content from the current page"""
    
    def __init__(self, driver=None):
        self.driver = driver
    
    def execute(self, selector: Optional[str] = None, 
                selector_type: str = "css", **kwargs) -> Dict[str, Any]:
        if not self.driver:
            return {"success": False, "error": "No browser driver available"}
        
        try:
            from selenium.webdriver.common.by import By
            
            if selector:
                by_map = {
                    "css": By.CSS_SELECTOR,
                    "xpath": By.XPATH,
                    "id": By.ID,
                    "class": By.CLASS_NAME
                }
                
                by = by_map.get(selector_type, By.CSS_SELECTOR)
                element = self.driver.find_element(by, selector)
                content = element.text
            else:
                # Read entire page
                content = self.driver.find_element(By.TAG_NAME, "body").text
            
            return {
                "success": True,
                "content": content,
                "url": self.driver.current_url,
                "title": self.driver.title
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_description(self) -> str:
        return "Read text content from the page"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "selector": {
                "type": "string", 
                "required": False, 
                "description": "Element selector (optional, reads whole page if not provided)"
            },
            "selector_type": {
                "type": "string",
                "required": False,
                "default": "css",
                "description": "Type of selector"
            }
        }


class BrowserScrollTool(BaseTool):
    """Scroll the page"""
    
    def __init__(self, driver=None):
        self.driver = driver
    
    def execute(self, direction: str = "down", amount: int = 500, **kwargs) -> Dict[str, Any]:
        if not self.driver:
            return {"success": False, "error": "No browser driver available"}
        
        try:
            if direction == "down":
                script = f"window.scrollBy(0, {amount});"
            elif direction == "up":
                script = f"window.scrollBy(0, -{amount});"
            elif direction == "top":
                script = "window.scrollTo(0, 0);"
            elif direction == "bottom":
                script = "window.scrollTo(0, document.body.scrollHeight);"
            else:
                return {"success": False, "error": f"Unknown direction: {direction}"}
            
            self.driver.execute_script(script)
            
            return {
                "success": True,
                "direction": direction,
                "message": f"Scrolled {direction}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_description(self) -> str:
        return "Scroll the page up or down"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "direction": {
                "type": "string",
                "required": True,
                "enum": ["up", "down", "top", "bottom"],
                "description": "Scroll direction"
            },
            "amount": {
                "type": "integer",
                "required": False,
                "default": 500,
                "description": "Pixels to scroll (for up/down)"
            }
        }


class BrowserWaitTool(BaseTool):
    """Wait for a condition"""
    
    def __init__(self, driver=None):
        self.driver = driver
    
    def execute(self, condition: str = "seconds", value: Any = 5, **kwargs) -> Dict[str, Any]:
        import time
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        if not self.driver:
            return {"success": False, "error": "No browser driver available"}
        
        try:
            if condition == "seconds":
                time.sleep(int(value))
                return {"success": True, "waited": f"{value} seconds"}
            
            elif condition == "element_visible":
                wait = WebDriverWait(self.driver, int(value))
                element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, kwargs.get("selector"))))
                return {"success": True, "message": f"Element visible: {kwargs.get('selector')}"}
            
            elif condition == "element_clickable":
                wait = WebDriverWait(self.driver, int(value))
                element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, kwargs.get("selector"))))
                return {"success": True, "message": f"Element clickable: {kwargs.get('selector')}"}
            
            elif condition == "url_contains":
                wait = WebDriverWait(self.driver, int(value))
                wait.until(EC.url_contains(str(value)))
                return {"success": True, "message": f"URL contains: {value}"}
            
            else:
                return {"success": False, "error": f"Unknown condition: {condition}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_description(self) -> str:
        return "Wait for a condition (time, element visibility, etc.)"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "condition": {
                "type": "string",
                "required": True,
                "enum": ["seconds", "element_visible", "element_clickable", "url_contains"],
                "description": "Wait condition type"
            },
            "value": {
                "type": "any",
                "required": True,
                "description": "Value (seconds for 'seconds', selector for element conditions)"
            },
            "selector": {
                "type": "string",
                "required": False,
                "description": "Element selector (for element conditions)"
            }
        }


class BrowserScreenshotTool(BaseTool):
    """Take a screenshot of the current page"""
    
    def __init__(self, driver=None):
        self.driver = driver
    
    def execute(self, filename: Optional[str] = None, 
                full_page: bool = False, **kwargs) -> Dict[str, Any]:
        if not self.driver:
            return {"success": False, "error": "No browser driver available"}
        
        try:
            import base64
            from datetime import datetime
            
            if filename is None:
                filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            screenshot_data = self.driver.get_screenshot_as_base64()
            
            return {
                "success": True,
                "filename": filename,
                "screenshot_base64": screenshot_data,
                "url": self.driver.current_url,
                "message": f"Screenshot taken: {filename}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_description(self) -> str:
        return "Take a screenshot of the current page"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "filename": {
                "type": "string",
                "required": False,
                "description": "Filename for screenshot (auto-generated if not provided)"
            },
            "full_page": {
                "type": "boolean",
                "required": False,
                "default": False,
                "description": "Capture full page (requires additional setup)"
            }
        }


class BrowserBackTool(BaseTool):
    """Navigate back in browser history"""
    
    def __init__(self, driver=None):
        self.driver = driver
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        if not self.driver:
            return {"success": False, "error": "No browser driver available"}
        
        try:
            previous_url = self.driver.current_url
            self.driver.back()
            
            return {
                "success": True,
                "previous_url": previous_url,
                "current_url": self.driver.current_url,
                "message": "Navigated back"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_description(self) -> str:
        return "Navigate back in browser history"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {}


class BrowserRefreshTool(BaseTool):
    """Refresh the current page"""
    
    def __init__(self, driver=None):
        self.driver = driver
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        if not self.driver:
            return {"success": False, "error": "No browser driver available"}
        
        try:
            self.driver.refresh()
            
            return {
                "success": True,
                "url": self.driver.current_url,
                "title": self.driver.title,
                "message": "Page refreshed"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_description(self) -> str:
        return "Refresh the current page"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {}


class BrowserFindTool(BaseTool):
    """Find elements on the page"""
    
    def __init__(self, driver=None):
        self.driver = driver
    
    def execute(self, selector: str, selector_type: str = "css", 
                multiple: bool = False, **kwargs) -> Dict[str, Any]:
        if not self.driver:
            return {"success": False, "error": "No browser driver available"}
        
        try:
            from selenium.webdriver.common.by import By
            
            by_map = {
                "css": By.CSS_SELECTOR,
                "xpath": By.XPATH,
                "id": By.ID,
                "name": By.NAME,
                "class": By.CLASS_NAME,
                "tag": By.TAG_NAME
            }
            
            by = by_map.get(selector_type, By.CSS_SELECTOR)
            
            if multiple:
                elements = self.driver.find_elements(by, selector)
                count = len(elements)
                return {
                    "success": True,
                    "found": count,
                    "elements": [elem.tag_name for elem in elements[:10]],  # Limit to first 10
                    "message": f"Found {count} elements matching '{selector}'"
                }
            else:
                element = self.driver.find_element(by, selector)
                return {
                    "success": True,
                    "tag": element.tag_name,
                    "text": element.text[:200],  # First 200 chars
                    "displayed": element.is_displayed(),
                    "enabled": element.is_enabled(),
                    "message": f"Found element: {selector}"
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_description(self) -> str:
        return "Find elements on the page"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "selector": {"type": "string", "required": True, "description": "Element selector"},
            "selector_type": {
                "type": "string",
                "required": False,
                "default": "css",
                "enum": ["css", "xpath", "id", "name", "class", "tag"],
                "description": "Type of selector"
            },
            "multiple": {
                "type": "boolean",
                "required": False,
                "default": False,
                "description": "Find multiple elements"
            }
        }


class ToolRegistry:
    """Registry for all available browser tools"""
    
    def __init__(self, driver=None):
        self.driver = driver
        self.tools = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register all default browser tools"""
        self.register("browser.open", BrowserOpenTool(self.driver))
        self.register("browser.click", BrowserClickTool(self.driver))
        self.register("browser.type", BrowserTypeTool(self.driver))
        self.register("browser.read", BrowserReadTool(self.driver))
        self.register("browser.scroll", BrowserScrollTool(self.driver))
        self.register("browser.wait", BrowserWaitTool(self.driver))
        self.register("browser.back", BrowserBackTool(self.driver))
        self.register("browser.refresh", BrowserRefreshTool(self.driver))
        self.register("browser.screenshot", BrowserScreenshotTool(self.driver))
        self.register("browser.find", BrowserFindTool(self.driver))
    
    def register(self, name: str, tool: BaseTool):
        """Register a tool"""
        self.tools[name] = tool
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools with descriptions"""
        return [
            {
                "name": name,
                "description": tool.get_description(),
                "parameters": tool.get_parameters()
            }
            for name, tool in self.tools.items()
        ]
    
    def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Execute a tool by name"""
        tool = self.get_tool(tool_name)
        if not tool:
            return {"success": False, "error": f"Tool not found: {tool_name}"}
        
        return tool.execute(**kwargs)


# Example usage
if __name__ == "__main__":
    # Create registry (without driver for demo)
    registry = ToolRegistry()
    
    # List all tools
    print("Available Tools:")
    for tool in registry.list_tools():
        print(f"\n{tool['name']}: {tool['description']}")
        print(f"Parameters: {tool['parameters']}")
