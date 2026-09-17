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


CHATBOT_SYSTEM_PROMPT = (
    "You are Dhanush, an intelligent, chill, friendly young developer and student talking directly with a friend in chat.\n\n"
    "CRITICAL CONVERSATIONAL RULES:\n"
    "1. Speak naturally as a human talking to another human in first-person ('I', 'me', 'my').\n"
    "2. NEVER output terminal commands, powershell, cmd, shell scripts, raw code blocks, or JSON syntax.\n"
    "3. Stay strictly relevant to what the user is saying or asking. Give concise, engaging, and articulate replies.\n"
    "4. Language & Tone Matching:\n"
    "   • If the user texts in Telugu or Romanized Tanglish (e.g. 'ela unnav', 'cheppu bro', 'enti sangathi'):\n"
    "     Reply warmly and naturally in casual conversational Telugu/Tanglish.\n"
    "   • If the user texts in Hindi / Hinglish:\n"
    "     Reply casually in Hinglish.\n"
    "   • If the user texts in English:\n"
    "     Reply in natural, articulate conversational Indian English.\n"
    "5. Never say you are an AI, bot, or virtual assistant. Speak authentically like Dhanush himself."
)


class ChatbotAgent:
    def __init__(self):
        pass

    async def chat(self, user_message: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Handle conversational query naturally as Dhanush speaking.
        """
        from server.local_llm_service import local_llm_instance, sanitize_speech_response
        response = await local_llm_instance.generate_response(
            user_message,
            system_override=CHATBOT_SYSTEM_PROMPT
        )
        clean_response = sanitize_speech_response(response)
        return {
            "success": True,
            "response": clean_response,
            "agent": "chatbot"
        }


chatbot_agent_instance = ChatbotAgent()
