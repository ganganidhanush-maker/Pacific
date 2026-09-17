"""
Octopus AI Agent - Groq LLM Integration

This module integrates Groq API for AI-powered reasoning, planning, and decision-making.
The AI Agent uses Groq's fast LLM to understand user requests, plan tasks, and select tools.
"""

import os
import json
from typing import Dict, List, Any, Optional
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


DEFAULT_GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


class GroqLLM:
    """
    Groq LLM integration for the Octopus AI Agent.
    
    Provides:
    - Intent understanding
    - Task planning
    - Tool selection
    - Response generation
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize Groq LLM client.
        
        Args:
            api_key: Groq API key (defaults to GROQ_API_KEY env var or embedded key)
            model: Model name (defaults to GROQ_MODEL env var or qwen/qwen3.8-27b)
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY") or DEFAULT_GROQ_API_KEY
        self.model = model or os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        self.conversation_history: List[Dict[str, str]] = []
        
        if self.api_key:
            try:
                self.client = Groq(api_key=self.api_key)
                self.is_available = True
            except Exception:
                self.client = None
                self.is_available = False
        else:
            self.client = None
            self.is_available = False
        
    def _build_system_prompt(self, available_tools: List[Dict[str, Any]]) -> str:
        """
        Build the system prompt with tool definitions.
        
        Args:
            available_tools: List of available browser tools with descriptions
            
        Returns:
            System prompt string
        """
        tools_json = json.dumps(available_tools, indent=2)
        
        return f"""You are Octopus, an intelligent AI agent that automates web browsing tasks.
You have access to browser automation tools and must help users complete their web tasks.

## Available Tools:
{tools_json}

## Your Responsibilities:
1. Understand the user's request and intent
2. Create a step-by-step plan to accomplish the task
3. Select appropriate tools and call them with correct parameters
4. Observe results and adapt your plan if needed
5. Continue until the task is complete
6. Report results to the user

## Tool Call Format:
When you need to use a tool, respond with JSON in this format:
{{
    "action": "tool_call",
    "tool_name": "browser.click",
    "parameters": {{"element": "button", "description": "Submit button"}}
}}

## Available Actions:
- "tool_call": Execute a browser tool
- "plan": Create or update a task plan
- "response": Respond to the user with information
- "wait": Wait for user confirmation or page load
- "complete": Mark task as complete with summary

## Important Rules:
1. Always think step-by-step before acting
2. Verify page state before taking actions
3. Handle errors gracefully by adapting your approach
4. For WhatsApp, Instagram, Canva - use their specific workflows
5. Never make up information - only report what you observe
6. Ask for clarification if the request is ambiguous

## Default Workflows:

### WhatsApp Web:
1. Open https://web.whatsapp.com
2. Wait for QR code scan or check if already logged in
3. Search for contact by name
4. Click on contact to open chat
5. Type message in message box
6. Click send button
7. Verify message was sent

### Instagram:
1. Open https://instagram.com
2. Check if logged in, otherwise wait for user to login
3. Navigate to profile or search for user
4. Perform actions (follow, like, comment, etc.)

### Canva:
1. Open https://canva.com
2. Check authentication
3. Navigate to templates or create new design
4. Use drag-drop interface for design elements

Respond in JSON format for tool calls, or natural language for responses."""

    def chat(self, user_message: str, context: Optional[Dict[str, Any]] = None, 
             available_tools: Optional[List[Dict[str, Any]]] = None,
             system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a message to Groq LLM and get response.
        
        Args:
            user_message: User's input message
            context: Additional context (current page, task state, etc.)
            available_tools: List of available tools
            system_prompt: Optional custom system prompt (e.g. for human persona)
            
        Returns:
            Parsed response from LLM
        """
        if not self.is_available or not self.client:
            return self._rule_based_response(user_message, context)

        # Build conversation history
        active_system_prompt = system_prompt or self._build_system_prompt(available_tools or [])
        
        messages = [{"role": "system", "content": active_system_prompt}]
        
        # Add conversation history only when using default agent prompt
        if not system_prompt:
            messages.extend(self.conversation_history[-10:])  # Last 10 messages
        
        # Add context if provided
        if context:
            context_str = json.dumps(context, indent=2)
            messages.append({
                "role": "user", 
                "content": f"Current Context:\n{context_str}\n\nUser: {user_message}"
            })
        else:
            messages.append({"role": "user", "content": user_message})
        
        try:
            # Call Groq API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=300,
                top_p=1,
                stream=False
            )
            
            assistant_message = response.choices[0].message.content
            
            # Add to conversation history if default mode
            if not system_prompt:
                self.conversation_history.append({"role": "user", "content": user_message})
                self.conversation_history.append({"role": "assistant", "content": assistant_message})
            
            # Parse response
            return self._parse_response(assistant_message)
            
        except Exception as e:
            error_msg = f"Error calling Groq API: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return {
                "action": "response",
                "content": f"I encountered an error: {str(e)}. Please try again."
            }
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse LLM response to extract action and parameters.
        
        Args:
            response_text: Raw response text from LLM
            
        Returns:
            Parsed response dictionary
        """
        response_text = response_text.strip()
        
        # Try to extract JSON from response
        try:
            # Look for JSON block
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                parsed = json.loads(json_str)
                
                # Ensure required fields
                if "action" not in parsed:
                    parsed["action"] = "response"
                
                return parsed
            else:
                # No JSON found, treat as natural language response
                return {
                    "action": "response",
                    "content": response_text
                }
                
        except json.JSONDecodeError:
            # If JSON parsing fails, treat as natural language
            return {
                "action": "response",
                "content": response_text
            }
    
    def _rule_based_response(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Provide intelligent rule-based fallback when Groq LLM API is unavailable."""
        msg_lower = user_message.lower().strip()
        context = context or {}
        current_url = (context.get("current_url") or "").lower()

        # Record conversation
        self.conversation_history.append({"role": "user", "content": user_message})

        if "whatsapp" in msg_lower:
            if "web.whatsapp.com" in current_url:
                resp = {"action": "response", "content": "Already on WhatsApp Web. Specify contact or message to send."}
            else:
                resp = {
                    "action": "tool_call",
                    "tool_name": "browser.open",
                    "parameters": {"url": "https://web.whatsapp.com"}
                }
        elif "instagram" in msg_lower:
            if "instagram.com" in current_url:
                resp = {"action": "response", "content": "Already on Instagram. Specify profile or action."}
            else:
                resp = {
                    "action": "tool_call",
                    "tool_name": "browser.open",
                    "parameters": {"url": "https://instagram.com"}
                }
        elif "canva" in msg_lower:
            if "canva.com" in current_url:
                resp = {"action": "response", "content": "Already on Canva. Specify design or template."}
            else:
                resp = {
                    "action": "tool_call",
                    "tool_name": "browser.open",
                    "parameters": {"url": "https://canva.com"}
                }
        elif "google" in msg_lower or "search" in msg_lower:
            resp = {
                "action": "tool_call",
                "tool_name": "browser.open",
                "parameters": {"url": "https://www.google.com"}
            }
        elif "http://" in msg_lower or "https://" in msg_lower:
            # Extract url
            import re
            urls = re.findall(r'https?://[^\s]+', user_message)
            target_url = urls[0] if urls else "https://google.com"
            resp = {
                "action": "tool_call",
                "tool_name": "browser.open",
                "parameters": {"url": target_url}
            }
        elif msg_lower in ("screenshot", "take screenshot"):
            resp = {
                "action": "tool_call",
                "tool_name": "browser.screenshot",
                "parameters": {}
            }
        elif msg_lower in ("refresh", "reload"):
            resp = {
                "action": "tool_call",
                "tool_name": "browser.refresh",
                "parameters": {}
            }
        else:
            resp = {
                "action": "response",
                "content": f"Understood: '{user_message}'. (Note: Running in rule-based fallback mode. Set GROQ_API_KEY for dynamic LLM reasoning.)"
            }

        reply_content = resp.get("content") or f"Executing tool: {resp.get('tool_name')}"
        self.conversation_history.append({"role": "assistant", "content": reply_content})
        return resp
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
    
    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history."""
        return self.conversation_history.copy()

    def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav", language: Optional[str] = None) -> str:
        """
        Transcribe spoken audio bytes to text using Groq Whisper.
        Supports English, Telugu, Hindi, and 90+ languages with ultra-low latency.
        """
        if not self.is_available or not self.client:
            return ""
        try:
            import io
            file_obj = io.BytesIO(audio_bytes)
            file_obj.name = filename
            kwargs = {
                "file": file_obj,
                "model": "whisper-large-v3-turbo",
                "response_format": "text"
            }
            if language:
                kwargs["language"] = language
            transcription = self.client.audio.transcriptions.create(**kwargs)
            return str(transcription).strip()
        except Exception as e:
            print(f"[GroqLLM] Audio transcription note: {e}")
            return ""


# Predefined automation workflows for common platforms
PLATFORM_WORKFLOWS = {
    "whatsapp": {
        "name": "WhatsApp Web",
        "url": "https://web.whatsapp.com",
        "steps": [
            {"action": "open", "url": "https://web.whatsapp.com"},
            {"action": "wait", "condition": "page_loaded", "timeout": 10},
            {"action": "check_auth", "selector": "[data-testid='chat-list']"},
            {"action": "search_contact", "input_selector": "[title='Search or start new chat']"},
            {"action": "click_contact", "result": True},
            {"action": "type_message", "selector": "[title='Type a message']"},
            {"action": "send_message", "selector": "[data-testid='compose-btn-send']"},
            {"action": "verify_sent", "selector": "[data-testid='msg-status']"}
        ],
        "selectors": {
            "chat_list": "[data-testid='chat-list']",
            "search_box": "[title='Search or start new chat']",
            "message_box": "[title='Type a message']",
            "send_button": "[data-testid='compose-btn-send']",
            "contact_name": "span[title='{contact_name}']"
        }
    },
    "instagram": {
        "name": "Instagram",
        "url": "https://instagram.com",
        "steps": [
            {"action": "open", "url": "https://instagram.com"},
            {"action": "wait", "condition": "page_loaded", "timeout": 10},
            {"action": "check_auth", "selector": "[role='navigation']"},
            {"action": "navigate", "options": ["profile", "explore", "messages", "notifications"]},
            {"action": "search_user", "input_selector": "input[type='text']"},
            {"action": "perform_action", "options": ["follow", "unfollow", "like", "comment", "dm"]}
        ],
        "selectors": {
            "nav_bar": "[role='navigation']",
            "search_box": "input[type='text']",
            "profile_pic": "img[alt*='Profile picture']",
            "follow_button": "button containing 'Follow'",
            "message_button": "button containing 'Message'"
        }
    },
    "canva": {
        "name": "Canva",
        "url": "https://canva.com",
        "steps": [
            {"action": "open", "url": "https://canva.com"},
            {"action": "wait", "condition": "page_loaded", "timeout": 10},
            {"action": "check_auth", "selector": "[data-testid='account-menu-trigger']"},
            {"action": "create_design", "options": ["presentation", "social_media", "document", "video"]},
            {"action": "select_template", "result": True},
            {"action": "edit_element", "options": ["text", "image", "shape", "color"]},
            {"action": "download", "format": ["png", "pdf", "jpg"]}
        ],
        "selectors": {
            "account_menu": "[data-testid='account-menu-trigger']",
            "create_button": "button containing 'Create a design'",
            "template_grid": "[data-testid='template-grid']",
            "editor_canvas": "[data-testid='editor-canvas']"
        }
    }
}


def get_platform_workflow(platform: str) -> Optional[Dict[str, Any]]:
    """
    Get predefined workflow for a platform.
    
    Args:
        platform: Platform name (whatsapp, instagram, canva)
        
    Returns:
        Workflow configuration or None
    """
    return PLATFORM_WORKFLOWS.get(platform.lower())


if __name__ == "__main__":
    # Test Groq integration
    print("Testing Groq LLM Integration...")
    
    llm = GroqLLM()
    
    # Define available tools
    tools = [
        {"name": "browser.open", "description": "Open a URL in the browser", "parameters": {"url": "string"}},
        {"name": "browser.click", "description": "Click an element", "parameters": {"selector": "string"}},
        {"name": "browser.type", "description": "Type text into an input", "parameters": {"selector": "string", "text": "string"}},
        {"name": "browser.read", "description": "Read content from page", "parameters": {"selector": "string"}},
        {"name": "browser.wait", "description": "Wait for condition", "parameters": {"seconds": "number"}}
    ]
    
    # Test conversation
    test_messages = [
        "Open WhatsApp Web and send a message to Rahul saying I'll call him after 6 PM",
        "Go to Instagram and check my notifications",
        "Create a presentation in Canva about AI"
    ]
    
    for msg in test_messages:
        print(f"\n{'='*60}")
        print(f"User: {msg}")
        print('-'*60)
        
        response = llm.chat(msg, available_tools=tools)
        print(f"Agent Action: {response.get('action')}")
        
        if response.get('action') == 'tool_call':
            print(f"Tool: {response.get('tool_name')}")
            print(f"Parameters: {response.get('parameters')}")
        else:
            print(f"Response: {response.get('content', 'N/A')[:200]}")
    
    print("\n✓ Groq LLM Integration test complete!")
