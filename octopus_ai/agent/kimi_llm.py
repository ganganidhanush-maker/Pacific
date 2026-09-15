"""
Kimi K3 ("Kiwi") LLM Integration for Octopus AI
Flagship engine referenced from Open Interpreter blueprint:
- Uses Moonshot Platform API (https://api.moonshot.cn/v1 or https://api.kimi.com/v1)
- Model: kimi-k3 (or moonshot-v1-128k / moonshot-v1-32k)
- 256K up to 1M token context window for massive academic textbooks, syllabi, and research papers
- Ultra-low cost ($0.30/M cached input tokens) and lightning-fast agentic reasoning
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("KimiLLM")

DEFAULT_KIMI_BASE_URL = "https://api.moonshot.cn/v1"
DEFAULT_KIMI_MODEL = "kimi-k3"
FALLBACK_KIMI_MODELS = ["moonshot-v1-128k", "moonshot-v1-32k", "moonshot-v1-8k", "kimi-latest"]


class KimiLLM:
    """
    Kimi K3 ("Kiwi") provider engine for Octopus AI Desktop Brain.
    Provides deep reasoning, coding capabilities, and educational synthesis
    for Students and Teachers.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        # Support both KIMI_API_KEY and MOONSHOT_API_KEY environment variables
        self.api_key = (
            api_key
            or os.getenv("KIMI_API_KEY")
            or os.getenv("MOONSHOT_API_KEY")
            or os.getenv("KIWI_API_KEY")
        )
        self.base_url = (
            base_url
            or os.getenv("KIMI_BASE_URL")
            or os.getenv("MOONSHOT_BASE_URL")
            or DEFAULT_KIMI_BASE_URL
        )
        self.model = model or os.getenv("KIMI_MODEL", DEFAULT_KIMI_MODEL)
        self.client = None
        self.is_available = False
        self.conversation_history: List[Dict[str, str]] = []

        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
                self.is_available = True
                logger.info(f"[KimiLLM] Initialized Kimi K3 engine (model: {self.model}, base: {self.base_url})")
            except Exception as e:
                logger.warning(f"[KimiLLM] Failed to initialize OpenAI client for Kimi: {e}")
                self.client = None
                self.is_available = False
        else:
            logger.debug("[KimiLLM] No KIMI_API_KEY / MOONSHOT_API_KEY found. Engine in inactive state.")

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.6,
        max_tokens: int = 1500,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Send a synchronous chat completion request to Kimi K3.
        """
        if not self.is_available or not self.client:
            return {"error": "Kimi K3 engine not available (missing KIMI_API_KEY or MOONSHOT_API_KEY)"}

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        for msg in self.conversation_history[-10:]:
            messages.append(msg)

        messages.append({"role": "user", "content": prompt})

        try:
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            if tools:
                kwargs["tools"] = tools

            response = self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            content = message.content or ""

            # Save to history
            self.conversation_history.append({"role": "user", "content": prompt})
            self.conversation_history.append({"role": "assistant", "content": content})

            result: Dict[str, Any] = {
                "content": content,
                "text": content,
                "model": response.model,
                "finish_reason": response.choices[0].finish_reason,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                }
            }

            if message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments) if tc.function.arguments else {}
                    }
                    for tc in message.tool_calls
                ]

            return result
        except Exception as e:
            logger.error(f"[KimiLLM] Chat error: {e}")
            if self.model == DEFAULT_KIMI_MODEL:
                for fb_model in FALLBACK_KIMI_MODELS:
                    try:
                        logger.info(f"[KimiLLM] Retrying with fallback model: {fb_model}")
                        self.model = fb_model
                        return self.chat(prompt, system_prompt, temperature, max_tokens, tools)
                    except Exception:
                        continue
            return {"error": str(e)}

    def clear_history(self):
        """Clear session conversation history to refresh cache."""
        self.conversation_history.clear()


kimi_llm_instance = KimiLLM()
