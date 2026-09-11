"""
Octopus AI Agent - Main Brain

This is the central intelligence module that:
- Understands user requests
- Plans multi-step tasks
- Makes decisions
- Selects and calls appropriate tools
- Maintains conversation context
- Handles errors and adapts plans
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from .groq_llm import GroqLLM, get_platform_workflow, PLATFORM_WORKFLOWS
from ..memory.context import Memory
from ..tools.browser_tools import BrowserTools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OctopusAgent:
    """
    The main AI Agent brain for Octopus.
    
    Orchestrates understanding, planning, decision-making, and tool execution
    using Groq LLM for intelligence.
    """
    
    def __init__(
        self,
        memory: Optional[Memory] = None, 
        browser_tools: Optional[Any] = None,
        groq_api_key: Optional[str] = None,
        safety_layer: Optional[Any] = None,
        llm_client: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize the Octopus Agent.
        
        Args:
            memory: Memory instance for context (creates new if None)
            browser_tools: BrowserTools or ToolRegistry instance (creates new if None)
            groq_api_key: Groq API key (uses env var if None)
            safety_layer: SafetyLayer instance for permission enforcement
            llm_client: Optional custom LLM client
        """
        self.memory = memory or Memory()
        
        if browser_tools is None:
            self.browser_tools = BrowserTools()
        elif hasattr(browser_tools, "execute_tool"):
            self.browser_tools = browser_tools
        else:
            self.browser_tools = BrowserTools(driver=browser_tools)
        
        self.safety_layer = safety_layer
        
        # Initialize Groq LLM or custom LLM client
        if llm_client is not None:
            self.llm = llm_client
        else:
            self.llm = GroqLLM(api_key=groq_api_key)
        
        # Agent state
        self.current_task: Optional[Dict[str, Any]] = None
        self.task_plan: List[Dict[str, Any]] = []
        self.current_step: int = 0
        self.is_running: bool = False
        
        # Get available tools for LLM
        self.available_tools = self._get_tool_definitions()
        
        logger.info("Octopus Agent initialized")
    
    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions for LLM."""
        return [
            {
                "name": "browser.open",
                "description": "Open a URL in the browser. Use this to navigate to websites like WhatsApp, Instagram, Canva.",
                "parameters": {"url": "string (required) - The URL to open"}
            },
            {
                "name": "browser.click",
                "description": "Click on an element. Use selector or description to identify the element.",
                "parameters": {
                    "selector": "string (optional) - CSS selector or XPath",
                    "description": "string (optional) - Description of element to click"
                }
            },
            {
                "name": "browser.type",
                "description": "Type text into an input field.",
                "parameters": {
                    "selector": "string (optional) - CSS selector or XPath of input",
                    "text": "string (required) - Text to type",
                    "clear_first": "boolean (optional) - Clear existing text first"
                }
            },
            {
                "name": "browser.read",
                "description": "Read content from the page. Returns text content of elements.",
                "parameters": {
                    "selector": "string (optional) - CSS selector or XPath",
                    "all_text": "boolean (optional) - Read all visible text"
                }
            },
            {
                "name": "browser.scroll",
                "description": "Scroll the page up or down.",
                "parameters": {
                    "direction": "string (required) - 'up' or 'down'",
                    "amount": "number (optional) - Pixels to scroll"
                }
            },
            {
                "name": "browser.wait",
                "description": "Wait for a specified time or condition.",
                "parameters": {
                    "seconds": "number (optional) - Seconds to wait",
                    "condition": "string (optional) - Condition to wait for"
                }
            },
            {
                "name": "browser.back",
                "description": "Navigate back in browser history.",
                "parameters": {}
            },
            {
                "name": "browser.refresh",
                "description": "Refresh the current page.",
                "parameters": {}
            },
            {
                "name": "browser.screenshot",
                "description": "Take a screenshot of the current page.",
                "parameters": {
                    "filename": "string (optional) - Filename for screenshot"
                }
            },
            {
                "name": "browser.find",
                "description": "Find elements on the page matching criteria.",
                "parameters": {
                    "selector": "string (optional) - CSS selector or XPath",
                    "text": "string (optional) - Text to search for",
                    "tag": "string (optional) - HTML tag name"
                }
            }
        ]
    
    async def process_request(self, user_message: str) -> Dict[str, Any]:
        """
        Process a user request through the full agent loop.
        
        Args:
            user_message: User's input message
            
        Returns:
            Response dictionary with action and result
        """
        logger.info(f"Processing request: {user_message[:100]}...")
        
        # Store in memory
        self.memory.add_conversation("user", user_message)
        
        # Get current context
        context = self._build_context()
        
        # Call Groq LLM for decision
        llm_response = self.llm.chat(
            user_message=user_message,
            context=context,
            available_tools=self.available_tools
        )
        
        # Process the response
        result = await self._execute_action(llm_response)
        
        # Store agent response
        if result.get('response'):
            self.memory.add_conversation("assistant", result['response'])
        
        result['success'] = result.get('success', not bool(result.get('error')))
        result['message'] = result.get('message', result.get('response', ''))
        return result
    
    def _build_context(self) -> Dict[str, Any]:
        """Build current context for the LLM."""
        current_url = None
        if hasattr(self.browser_tools, "engine") and self.browser_tools.engine:
            if hasattr(self.browser_tools.engine, "get_current_url"):
                current_url = self.browser_tools.engine.get_current_url()
            elif hasattr(self.browser_tools.engine, "driver") and self.browser_tools.engine.driver:
                try:
                    current_url = self.browser_tools.engine.driver.current_url
                except Exception:
                    pass

        return {
            "current_url": current_url,
            "current_task": self.current_task,
            "task_progress": f"Step {self.current_step}/{len(self.task_plan)}" if self.task_plan else None,
            "recent_actions": self.memory.get_recent_actions(5),
            "platform_workflows": list(PLATFORM_WORKFLOWS.keys())
        }
    
    async def _execute_action(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the action decided by the LLM.
        
        Args:
            llm_response: Response from Groq LLM
            
        Returns:
            Execution result
        """
        action = llm_response.get('action', 'response')
        
        try:
            if action == 'tool_call':
                tool_name = llm_response.get('tool_name')
                parameters = llm_response.get('parameters', {})
                
                # Check safety permissions
                if self.safety_layer:
                    permission = self.safety_layer.check_permission({
                        "tool": tool_name,
                        "params": parameters
                    })
                    if not permission.get("allowed"):
                        reason = permission.get("reason", "Permission denied")
                        logger.warning(f"Action blocked by safety layer: {reason}")
                        return {
                            "action": "blocked",
                            "tool": tool_name,
                            "error": reason,
                            "response": f"Action '{tool_name}' blocked by safety layer: {reason}",
                            "success": False
                        }
                
                logger.info(f"Executing tool: {tool_name} with params: {parameters}")
                
                # Execute the tool (handles sync or async)
                exec_result = self.browser_tools.execute_tool(tool_name, parameters)
                if asyncio.iscoroutine(exec_result):
                    result = await exec_result
                else:
                    result = exec_result
                
                # Store action in memory
                self.memory.add_action({
                    "tool": tool_name,
                    "parameters": parameters,
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Observe result and continue if needed
                observation = self._observe_result(result)
                
                # Ask LLM for next action based on observation
                if not result.get('error'):
                    next_response = self.llm.chat(
                        user_message=f"Tool '{tool_name}' executed successfully. Observation: {observation}. What should I do next?",
                        context=self._build_context(),
                        available_tools=self.available_tools
                    )
                    
                    # Recursively execute next action if needed
                    if next_response.get('action') == 'tool_call':
                        return await self._execute_action(next_response)
                
                return {
                    "action": action,
                    "tool": tool_name,
                    "result": result,
                    "observation": observation,
                    "response": f"Completed: {tool_name}"
                }
                
            elif action == 'plan':
                plan = llm_response.get('plan', [])
                self.task_plan = plan
                self.current_step = 0
                
                return {
                    "action": "plan_created",
                    "plan": plan,
                    "response": f"I've created a plan with {len(plan)} steps. Starting execution..."
                }
                
            elif action == 'complete':
                summary = llm_response.get('summary', 'Task completed.')
                self.current_task = None
                self.task_plan = []
                self.is_running = False
                
                return {
                    "action": "complete",
                    "summary": summary,
                    "response": summary
                }
                
            elif action == 'wait':
                reason = llm_response.get('reason', 'Waiting for confirmation or page load.')
                return {
                    "action": "wait",
                    "reason": reason,
                    "response": reason
                }
                
            else:  # response action
                content = llm_response.get('content', '')
                return {
                    "action": "response",
                    "content": content,
                    "response": content
                }
                
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            error_response = {
                "action": "response",
                "error": str(e),
                "response": f"I encountered an error: {str(e)}. Let me try a different approach."
            }
            
            # Ask LLM for recovery strategy
            recovery_response = self.llm.chat(
                user_message=f"Error occurred: {str(e)}. How should I recover or proceed differently?",
                context=self._build_context(),
                available_tools=self.available_tools
            )
            
            if recovery_response.get('action') == 'tool_call':
                return await self._execute_action(recovery_response)
            
            return error_response
    
    def _observe_result(self, result: Dict[str, Any]) -> str:
        """
        Observe and describe the result of an action.
        
        Args:
            result: Tool execution result
            
        Returns:
            Observation description
        """
        if result.get('error'):
            return f"Error: {result['error']}"
        
        observations = []
        
        if result.get('success'):
            observations.append("Action succeeded")
        
        if result.get('url'):
            observations.append(f"Current URL: {result['url']}")
        
        if result.get('text'):
            text_preview = result['text'][:200]
            observations.append(f"Page content: {text_preview}...")
        
        if result.get('elements_found'):
            observations.append(f"Found {result['elements_found']} elements")
        
        if result.get('screenshot'):
            observations.append(f"Screenshot saved: {result['screenshot']}")
        
        return "; ".join(observations) if observations else "Action completed"
    
    def start_task(self, task_description: str, platform: Optional[str] = None):
        """
        Start a new task with optional predefined workflow.
        
        Args:
            task_description: Description of the task
            platform: Platform name (whatsapp, instagram, canva)
        """
        self.current_task = {
            "description": task_description,
            "platform": platform,
            "started_at": datetime.now().isoformat()
        }
        
        # Load predefined workflow if platform specified
        if platform:
            workflow = get_platform_workflow(platform)
            if workflow:
                self.task_plan = workflow.get('steps', [])
                logger.info(f"Loaded workflow for {platform}: {len(self.task_plan)} steps")
        
        self.is_running = True
        self.current_step = 0
        
        logger.info(f"Started task: {task_description}")
    
    def clear_memory(self):
        """Clear agent memory and state."""
        self.memory.clear()
        self.llm.clear_history()
        self.current_task = None
        self.task_plan = []
        self.current_step = 0
        self.is_running = False
        logger.info("Agent memory cleared")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        return {
            "is_running": self.is_running,
            "current_task": self.current_task,
            "task_progress": f"{self.current_step}/{len(self.task_plan)}" if self.task_plan else "No active task",
            "memory_size": len(self.memory.conversation_history),
            "available_platforms": list(PLATFORM_WORKFLOWS.keys())
        }

    def execute_task(self, user_input: str) -> Dict[str, Any]:
        """
        Synchronous execution entry point (compatible with OctopusSystem and scripts).
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self.process_request(user_input)).result()
            else:
                return loop.run_until_complete(self.process_request(user_input))
        except RuntimeError:
            return asyncio.run(self.process_request(user_input))



# Convenience function for quick automation
async def automate(platform: str, task: str, contact: Optional[str] = None, 
                   message: Optional[str] = None, groq_api_key: Optional[str] = None):
    """
    Quick automation helper for common tasks.
    
    Args:
        platform: Platform name (whatsapp, instagram, canva)
        task: Task description
        contact: Contact name (for messaging)
        message: Message to send (for messaging)
        groq_api_key: Groq API key
        
    Returns:
        Automation result
    """
    agent = OctopusAgent(groq_api_key=groq_api_key)
    
    # Build user message
    user_message = f"Go to {platform}"
    if contact:
        user_message += f" and find {contact}"
    if message:
        user_message += f" and send message: {message}"
    if task:
        user_message += f". Also: {task}"
    
    return await agent.process_request(user_message)
