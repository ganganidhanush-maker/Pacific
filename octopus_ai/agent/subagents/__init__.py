"""
Octopus AI - Sub-Agents Package
Provides specialized sub-agents orchestrated by the Main Agent Avatar:
- WebAgent: Browser automations (WhatsApp, Canva, Instagram, Web Search)
- DesktopAgent: Local file discovery, organization, manipulation, and system tasks
- ResearchAgent: Knowledge gathering, academic synthesis, and slide outlining
- ChatbotAgent: Conversational Q&A, tutoring, and educational dialogue
"""

from .web_agent import WebAgent, web_agent_instance
from .desktop_agent import DesktopAgent, desktop_agent_instance
from .research_agent import ResearchAgent, research_agent_instance
from .chatbot_agent import ChatbotAgent, chatbot_agent_instance

__all__ = [
    "WebAgent", "web_agent_instance",
    "DesktopAgent", "desktop_agent_instance",
    "ResearchAgent", "research_agent_instance",
    "ChatbotAgent", "chatbot_agent_instance"
]
