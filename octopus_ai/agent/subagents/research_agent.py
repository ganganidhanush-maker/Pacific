"""
Research Agent for Octopus AI
Specialized in academic and educational research:
- Gathers key concepts, facts, and explanations on any subject
- Structures presentation slide outlines (for Canva in Web Agent)
- Produces study summaries and lecture notes
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("ResearchAgent")


class ResearchAgent:
    def __init__(self):
        pass

    async def research_topic(self, topic: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Research a topic and provide a structured synthesis with key takeaways.
        """
        from server.local_llm_service import local_llm_instance
        prompt = (
            f"You are an academic Research Agent assisting students and educators. "
            f"Provide a comprehensive, accurate research synthesis on the topic: '{topic}'. "
            f"Context: {context or 'General academic overview'}. "
            f"Structure your response with: "
            f"1. Core Overview, 2. Key Components/Takeaways, 3. Practical Applications or Code Concepts if technical."
        )
        response = await local_llm_instance.generate_response(prompt)
        return {
            "success": True,
            "topic": topic,
            "synthesis": response,
            "summary": f"Completed research synthesis on '{topic}'."
        }

    async def generate_presentation_outline(self, topic: str, slide_count: int = 5) -> Dict[str, Any]:
        """
        Generate a slide-by-slide outline ready to be built in Canva.
        """
        from server.local_llm_service import local_llm_instance
        prompt = (
            f"Create a structured {slide_count}-slide presentation outline on: '{topic}'. "
            f"For each slide, provide: Slide Title and 3 bullet points of concise content. "
            f"Format cleanly for an educational presentation."
        )
        outline = await local_llm_instance.generate_response(prompt)
        return {
            "success": True,
            "topic": topic,
            "slide_count": slide_count,
            "outline": outline,
            "summary": f"Created {slide_count}-slide presentation outline on '{topic}'."
        }


research_agent_instance = ResearchAgent()
