# Octopus AI Agent

"""
Main Entry Point

This module integrates all components of the Octopus system:
- AI Agent (brain)
- Tool Layer (hands)
- Browser Engine (execution)
- Memory (context)
- Safety Layer (control)
- Interface (user interaction)

```python
from octopus_ai import OctopusSystem

# Initialize the system
octopus = OctopusSystem()

# Start interacting
response = octopus.chat("Open WhatsApp Web and send a message to Rahul")
print(response)
```

## Architecture

The system follows this flow:

1. **User** sends a natural language request
2. **AI Agent** understands the intent and creates a plan
3. **Safety Layer** checks permissions for each action
4. **Tool Layer** executes browser commands via Selenium
5. **Observation** captures results
6. **AI Agent** evaluates and continues until task complete
7. **Response** is sent back to user

## Components

- `agent/` - AI Agent that understands, plans, and decides
- `tools/` - Browser automation tools (open, click, type, etc.)
- `engine/` - Selenium WebDriver integration
- `memory/` - Context and conversation history
- `safety/` - Permission and safety controls
- `interface/` - User chat interface
"""

from .system import OctopusSystem, create_octopus
from .agent.agent import OctopusAgent, automate
from .agent.groq_llm import GroqLLM, get_platform_workflow, PLATFORM_WORKFLOWS
from .agent.whatsapp_responder import WhatsAppAutoResponder
from .tools.browser_tools import BrowserTools, ToolRegistry
from .engine.selenium_engine import BrowserEngine
from .memory.context import Memory
from .safety.permissions import SafetyLayer, PermissionLevel, ActionCategory
from .interface.chat import ChatInterface, WebChatInterface
from .computer_use import ComputerAgent, computer_agent_instance, computer_router

__all__ = [
    "OctopusSystem",
    "create_octopus",
    "OctopusAgent",
    "automate",
    "GroqLLM",
    "get_platform_workflow",
    "PLATFORM_WORKFLOWS",
    "WhatsAppAutoResponder",
    "BrowserTools",
    "ToolRegistry",
    "BrowserEngine",
    "Memory",
    "SafetyLayer",
    "PermissionLevel",
    "ActionCategory",
    "ChatInterface",
    "WebChatInterface",
    "ComputerAgent",
    "computer_agent_instance",
    "computer_router",
]
__version__ = "0.2.0"
