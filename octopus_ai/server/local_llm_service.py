"""
Local LLM Service for Octopus AI Desktop Agent
Connects to local Ollama instance (defaulting to llama3.2:latest) for general conversational AI,
reasoning, and task orchestration. Automatically launches Ollama server if not currently running.
"""

import os
import sys
import json
import time
import asyncio
import logging
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger("LocalLLMService")

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.2:latest"
FALLBACK_MODELS = ["llama3:8b", "llama3:latest", "llama3.2"]

SYSTEM_PROMPT = (
    "You are Octopus AI Main Agent, a knowledgeable, direct, and helpful desktop AI assistant "
    "created for Dhanush. Answer naturally, clearly, and concisely in 1 to 3 sentences "
    "unless detailed steps are explicitly requested. Keep the tone friendly and conversational, "
    "formatted well for spoken audio (avoid markdown asterisks, emojis, or bullet points unless asked)."
)


class LocalLLMService:
    _instance: Optional["LocalLLMService"] = None

    def __init__(self):
        self.base_url = OLLAMA_BASE_URL
        self.model = DEFAULT_MODEL
        self.available_models: List[str] = []
        self.is_connected = False
        self.process: Optional[subprocess.Popen] = None
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history = 10

    @classmethod
    def get_instance(cls) -> "LocalLLMService":
        if cls._instance is None:
            cls._instance = LocalLLMService()
        return cls._instance

    def _find_ollama_executable(self) -> Optional[str]:
        """Locate ollama.exe on the system."""
        # Check standard installation paths
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe"),
            "ollama.exe",
            "ollama"
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        # Check if in PATH
        import shutil
        which_path = shutil.which("ollama")
        if which_path:
            return which_path
        return None

    def is_server_listening(self) -> bool:
        """Check if Ollama server responds on 127.0.0.1:11434."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", headers={"User-Agent": "OctopusAI"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    self.available_models = [m["name"] for m in data.get("models", [])]
                    self._resolve_best_model()
                    self.is_connected = True
                    return True
        except Exception:
            pass
        return False

    def _resolve_best_model(self):
        """Pick the best available model on the user's system."""
        if not self.available_models:
            return
        if DEFAULT_MODEL in self.available_models:
            self.model = DEFAULT_MODEL
        else:
            for fb in FALLBACK_MODELS:
                for am in self.available_models:
                    if fb in am:
                        self.model = am
                        return
            self.model = self.available_models[0]

    def ensure_server_running(self) -> bool:
        """Ensure Ollama server is running. If not, launch ollama serve."""
        if self.is_server_listening():
            return True

        ollama_bin = self._find_ollama_executable()
        if not ollama_bin:
            logger.warning("[LocalLLM] ollama.exe not found in standard paths.")
            return False

        logger.info(f"[LocalLLM] Starting Ollama serve in background via {ollama_bin}...")
        try:
            env = os.environ.copy()
            env["OLLAMA_NO_CLOUD"] = "1"
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            self.process = subprocess.Popen(
                [ollama_bin, "serve"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags
            )
            # Wait up to 10 seconds for server to respond
            for _ in range(20):
                time.sleep(0.5)
                if self.is_server_listening():
                    logger.info(f"[LocalLLM] Ollama server ready! Active model: {self.model}")
                    return True
        except Exception as e:
            logger.error(f"[LocalLLM] Failed to start Ollama server: {e}")

        return self.is_server_listening()

    async def generate_response(
        self,
        prompt: str,
        add_to_history: bool = True,
        system_override: Optional[str] = None
    ) -> str:
        """
        Generate chat response using local Ollama LLM.
        Maintains conversational history for user chat, while isolating internal orchestration prompts.
        """
        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            return "How can I help you today?"

        # Ensure server is running
        loop = asyncio.get_event_loop()
        is_ready = await loop.run_in_executor(None, self.ensure_server_running)
        if not is_ready:
            return self._fallback_chat(cleaned_prompt)

        # Build message history
        sys_msg = system_override or SYSTEM_PROMPT
        messages = [{"role": "system", "content": sys_msg}]

        if add_to_history:
            for msg in self.conversation_history[-self.max_history:]:
                messages.append(msg)

        messages.append({"role": "user", "content": cleaned_prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 120
            }
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=req_data,
                headers={"Content-Type": "application/json", "User-Agent": "OctopusAI"}
            )

            def _call_ollama():
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode("utf-8"))

            res_json = await loop.run_in_executor(None, _call_ollama)
            reply = (res_json.get("message") or {}).get("content", "").strip()

            if reply:
                clean_reply = reply.replace("*", "").replace("#", "").strip()
                if add_to_history:
                    self.conversation_history.append({"role": "user", "content": cleaned_prompt})
                    self.conversation_history.append({"role": "assistant", "content": clean_reply})
                return clean_reply
            else:
                return self._fallback_chat(cleaned_prompt)

        except Exception as e:
            logger.error(f"[LocalLLM] Error querying Ollama: {e}")
            return self._fallback_chat(cleaned_prompt)

    def _fallback_chat(self, prompt: str) -> str:
        """Fallback conversational responses if local LLM is temporarily unreachable."""
        p_lower = prompt.lower()
        if any(w in p_lower for w in ["who are you", "what are you"]):
            return "I am Octopus AI, your personal desktop AI assistant running locally on your computer."
        elif any(w in p_lower for w in ["hello", "hi", "hey"]):
            return "Hello Dhanush! I am online and ready to assist you."
        elif "how are you" in p_lower:
            return "I'm running smoothly with full GPU acceleration, ready for any question or task."
        return f"I understand your question about '{prompt}'. How can I help you further with that?"

    def clear_history(self):
        """Reset conversation memory."""
        self.conversation_history.clear()


def sanitize_speech_response(text: str) -> str:
    """
    Ensure the avatar always speaks natural, clean conversational English.
    Strips out raw JSON, python code, dictionary brackets, and internal prompt leaks.
    """
    import re
    if not text:
        return "I am here to help you."
    cleaned = text.strip()

    # If wrapped in JSON or contains JSON structure
    if "{" in cleaned and "}" in cleaned:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        try:
            parsed = json.loads(cleaned[start:end+1])
            if isinstance(parsed, dict):
                for key in ["spoken_summary", "response", "message", "content", "summary", "answer"]:
                    val = parsed.get(key)
                    if isinstance(val, str) and val.strip():
                        return sanitize_speech_response(val)
        except Exception:
            pass

        # Regex fallback for JSON fields
        m = re.search(r'"(?:spoken_summary|response|message|content|summary)"\s*:\s*"([^"]+)"', cleaned)
        if m:
            return sanitize_speech_response(m.group(1))

        # If it's raw JSON without identifiable fields, strip the JSON block
        cleaned = (cleaned[:start] + " " + cleaned[end+1:]).strip()

    # Remove markdown code blocks and inline code
    cleaned = re.sub(r'```[\s\S]*?```', '', cleaned)
    cleaned = re.sub(r'`[^`]*`', '', cleaned)

    # Clean markdown formatting characters
    cleaned = cleaned.replace("*", "").replace("#", "").replace("_", " ").replace(">", "")
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    if not cleaned or cleaned.startswith("{"):
        return "I am ready. How can I help you today?"
    return cleaned


# Global singleton instance
local_llm_instance = LocalLLMService.get_instance()
# Clear any polluted history on startup
local_llm_instance.clear_history()
