"""
Chatbot Agent for Octopus AI
Dedicated to student tutoring, teacher advisory, and interactive educational dialogue:
- Answers student doubts with clear explanations and analogies
- Helps teachers brainstorm lesson plans and assignments
- Provides friendly, engaging conversational assistance
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("ChatbotAgent")


class ChatbotAgent:
    def __init__(self):
        pass

    async def chat(self, user_message: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Handle conversational query from a student or teacher.
        """
        from server.local_llm_service import local_llm_instance
        response = await local_llm_instance.generate_response(user_message)
        return {
            "success": True,
            "response": response,
            "agent": "chatbot"
        }


chatbot_agent_instance = ChatbotAgent()
