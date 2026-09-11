"""
Octopus AI - Agentic Browser Automation System

Main system integration module that brings together all components.
"""

from typing import Dict, Any, Optional

from .agent.agent import OctopusAgent
from .tools.browser_tools import ToolRegistry
from .engine.selenium_engine import BrowserEngine
from .memory.context import Memory
from .safety.permissions import SafetyLayer
from .interface.chat import ChatInterface


class OctopusSystem:
    """
    Main Octopus AI System
    
    Integrates all components:
    - AI Agent (brain)
    - Tool Layer (hands)
    - Browser Engine (execution)
    - Memory (context)
    - Safety Layer (control)
    - Interface (user interaction)
    """
    
    def __init__(self, headless: bool = False):
        # Initialize components
        self.engine = BrowserEngine(headless=headless)
        self.memory = Memory()
        self.safety = SafetyLayer()
        
        # Initialize browser engine and create tool registry
        engine_result = self.engine.initialize()
        if not engine_result.get("success"):
            print(f"Warning: Browser initialization failed: {engine_result.get('error')}")
        
        # Create tool registry with driver
        driver = self.engine.get_driver()
        self.tools = ToolRegistry(driver=driver)
        
        # Initialize agent with dependencies
        self.agent = OctopusAgent(
            llm_client=None,  # TODO: Add LLM client
            memory=self.memory,
            safety_layer=self.safety
        )
        
        # Initialize chat interface
        self.interface = ChatInterface()
        self.interface.set_message_handler(self._handle_message)
        
        self.is_initialized = self.engine.is_ready()
    
    def _handle_message(self, message: str) -> str:
        """
        Handle incoming user message
        
        This is the main entry point for user requests
        """
        # Store conversation
        self.memory.add_conversation("user", message)
        
        if not self.is_initialized:
            return "Browser engine not initialized. Cannot execute commands."
        
        # Execute task through agent
        result = self.agent.execute_task(message)
        
        # Store response
        if result.get("success"):
            response = f"✅ Task completed: {result.get('message')}"
        else:
            response = f"❌ Task failed: {result.get('message')}"
        
        self.memory.add_conversation("assistant", response)
        
        return response
    
    def chat(self, message: str) -> str:
        """
        Send a message to Octopus and get response
        
        Args:
            message: User's natural language request
            
        Returns:
            Agent's response
        """
        result = self.interface.receive_user_message(message)
        return result.get("response", "Error processing message")
    
    def execute_action(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Directly execute a browser action
        
        Args:
            tool_name: Name of tool (e.g., 'browser.open')
            **kwargs: Tool parameters
            
        Returns:
            Execution result
        """
        # Check safety permissions
        action = {"tool": tool_name, "params": kwargs}
        permission = self.safety.check_permission(action)
        
        if not permission.get("allowed"):
            return {
                "success": False,
                "error": f"Action blocked: {permission.get('reason')}"
            }
        
        # Execute tool
        result = self.tools.execute_tool(tool_name, **kwargs)
        
        # Record in memory
        self.memory.add_action(action, result)
        
        # Update location if navigation occurred
        if tool_name == "browser.open" and result.get("success"):
            self.memory.set_current_location(
                url=result.get("current_url", ""),
                page_title=result.get("title", "")
            )
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status"""
        return {
            "initialized": self.is_initialized,
            "browser_ready": self.engine.is_ready(),
            "current_task": self.memory.get_current_task(),
            "current_location": self.memory.get_current_location(),
            "available_tools": len(self.tools.list_tools()),
            "conversation_length": len(self.memory.get_conversation_history()),
            "action_count": len(self.memory.get_action_history())
        }
    
    def get_context(self) -> Dict[str, Any]:
        """Get current context summary"""
        return self.memory.get_context_summary()
    
    def configure_safety(self, **kwargs) -> None:
        """
        Configure safety settings
        
        Example:
            octopus.configure_safety(
                blocked_domains=["gambling.com"],
                require_confirmation_for=["communicate"]
            )
        """
        # Add blocked domains
        if "blocked_domains" in kwargs:
            for domain in kwargs["blocked_domains"]:
                self.safety.add_blocked_domain(domain)
        
        # Set allowed domains (whitelist mode)
        if "allowed_domains" in kwargs:
            self.safety.set_allowed_domains(kwargs["allowed_domains"])
    
    def quit(self) -> None:
        """Shutdown the system and close browser"""
        if self.engine.is_ready():
            self.engine.quit()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure cleanup"""
        self.quit()


# Convenience function for quick testing
def create_octopus(headless: bool = False) -> OctopusSystem:
    """Create and return an OctopusSystem instance"""
    return OctopusSystem(headless=headless)


# Example usage
if __name__ == "__main__":
    print("🐙 Octopus AI System Demo\n")
    print("=" * 60)
    
    # Create system (will fail gracefully if Chrome not available)
    try:
        octopus = OctopusSystem(headless=True)
        
        # Show status
        status = octopus.get_status()
        print(f"\nSystem Status:")
        print(f"  Initialized: {status['initialized']}")
        print(f"  Available Tools: {status['available_tools']}")
        
        # List tools
        print(f"\nAvailable Tools:")
        for tool in octopus.tools.list_tools():
            print(f"  • {tool['name']}: {tool['description']}")
        
        # Cleanup
        octopus.quit()
        
    except Exception as e:
        print(f"Note: Full demo requires Chrome/Chromium installed")
        print(f"Error: {e}")
    
    print("\n" + "=" * 60)
    print("\nTo use Octopus:")
    print("  from octopus_ai import OctopusSystem")
    print("  octopus = OctopusSystem()")
    print("  response = octopus.chat('Open Google and search for Python')")
    print("  print(response)")
