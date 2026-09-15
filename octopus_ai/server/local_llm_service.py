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
    "You are Octopus AI, an exceptionally intelligent, insightful, and adaptable desktop AI assistant "
    "created for Dhanush. You possess deep expertise across computer science, automation, reasoning, "
    "mathematics, science, literature, and general knowledge.\n\n"
    "MULTILINGUAL & TELUGU FLUENCY:\n"
    "- You are fully multilingual and can understand and converse fluently in ANY language.\n"
    "- You have native, fluent mastery of TELUGU (తెలుగు) as well as Telugu-English blend (Tanglish) and English.\n"
    "- If the user asks in Telugu (either Telugu script or Romanized like 'ela unnav', 'enti bro', 'cheppu', 'namaskaram') "
    "or asks you to speak in Telugu, respond naturally, warmly, and with high intelligence in authentic Telugu (తెలుగు script).\n"
    "- If the user speaks in English, Hindi, or any other language, respond fluently in that same language.\n\n"
    "RESPONSE STYLE & INTELLIGENCE:\n"
    "- Provide intelligent, thoughtful, and articulate explanations with genuine depth, avoiding shallow one-liners unless asked.\n"
    "- Keep the tone confident, friendly, and natural.\n"
    "- Format answers cleanly for spoken reading (avoid markdown asterisks, raw code blocks, or emojis unless asked)."
)


class LocalLLMService:
    _instance: Optional["LocalLLMService"] = None

    def __init__(self):
        self.base_url = OLLAMA_BASE_URL
        self.model = DEFAULT_MODEL
        self.available_models: List[str] = []
        self.is_connected = False
        self.process: Optional[subprocess.Popen] = None
        self.max_history = 10
        # Restore persistent conversation history from SQLite across restarts
        try:
            from octopus_ai.memory.persistent_memory import persistent_memory_instance
            self.persistent_memory = persistent_memory_instance
            self.conversation_history: List[Dict[str, str]] = self.persistent_memory.get_recent_history(limit=self.max_history)
        except Exception:
            self.persistent_memory = None
            self.conversation_history: List[Dict[str, str]] = []

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
        Generate chat response using high-intelligence reasoning.
        Prioritizes:
        1. Kimi K3 ("Kiwi") / Moonshot AI (ultra-fast, 256K context, deep coding & educational reasoning)
        2. Groq Cloud LLM (fastest inference, native multilingual/Telugu)
        3. Local Ollama LLM (GPU-accelerated, offline private)
        4. Rule-based conversational fallback
        """
        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            return "How can I help you today?"

        sys_msg = system_override or SYSTEM_PROMPT
        loop = asyncio.get_event_loop()

        # Check NotebookLM persistent knowledge base for grounded source excerpts
        try:
            if self.persistent_memory:
                grounded_chunks = self.persistent_memory.query_knowledge_base(cleaned_prompt, top_k=2)
                if grounded_chunks:
                    sources_text = "\n\n".join([f"[{c['title']} (chunk {c['chunk_index']})]: {c['excerpt']}" for c in grounded_chunks])
                    sys_msg = (
                        f"{sys_msg}\n\n"
                        f"[NOTEBOOKLM GROUNDED KNOWLEDGE BASE SOURCES]:\n{sources_text}\n"
                        f"Ground your answer directly in the above notes/sources when relevant, mentioning the source title."
                    )
        except Exception as kb_err:
            logger.debug(f"[LocalLLM] Knowledge base grounding notice: {kb_err}")

        # 1. Kimi K3 ("Kiwi") Moonshot Engine Integration (From Open Interpreter Blueprint)
        try:
            from octopus_ai.agent.kimi_llm import KimiLLM
            kimi = KimiLLM()
            if kimi.is_available and kimi.client:
                messages = [{"role": "system", "content": sys_msg}]
                if add_to_history:
                    for msg in self.conversation_history[-self.max_history:]:
                        messages.append(msg)
                messages.append({"role": "user", "content": cleaned_prompt})

                def _call_kimi():
                    resp = kimi.client.chat.completions.create(
                        model=kimi.model,
                        messages=messages,
                        temperature=0.6,
                        max_tokens=1000
                    )
                    return resp.choices[0].message.content

                kimi_reply = await loop.run_in_executor(None, _call_kimi)
                if kimi_reply and kimi_reply.strip():
                    clean_reply = sanitize_speech_response(kimi_reply.strip())
                    self._record_turn(cleaned_prompt, clean_reply, add_to_history)
                    return clean_reply
        except Exception as kimi_err:
            logger.info(f"[LocalLLM] Kimi K3 engine notice ({kimi_err}), checking Groq Cloud...")

        # 2. High-Intelligence Groq Cloud Inference (fastest, most intelligent, native multilingual/Telugu)
        try:
            from octopus_ai.agent.groq_llm import GroqLLM
            groq = GroqLLM()
            if groq.is_available and groq.client:
                messages = [{"role": "system", "content": sys_msg}]
                if add_to_history:
                    for msg in self.conversation_history[-self.max_history:]:
                        messages.append(msg)
                messages.append({"role": "user", "content": cleaned_prompt})

                def _call_groq():
                    resp = groq.client.chat.completions.create(
                        model=groq.model,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=800,
                        top_p=0.95
                    )
                    return resp.choices[0].message.content

                groq_reply = await loop.run_in_executor(None, _call_groq)
                if groq_reply and groq_reply.strip():
                    clean_reply = sanitize_speech_response(groq_reply.strip())
                    self._record_turn(cleaned_prompt, clean_reply, add_to_history)
                    return clean_reply
        except Exception as groq_err:
            logger.info(f"[LocalLLM] Groq inference notice ({groq_err}), trying local Ollama...")

        # 3. Local Ollama LLM with GPU acceleration
        try:
            is_ready = await loop.run_in_executor(None, self.ensure_server_running)
            if is_ready:
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
                        "num_predict": 1024
                    }
                }

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
                    clean_reply = sanitize_speech_response(reply)
                    self._record_turn(cleaned_prompt, clean_reply, add_to_history)
                    return clean_reply
        except Exception as ollama_err:
            logger.error(f"[LocalLLM] Error querying Ollama: {ollama_err}")

        # 4. Graceful fallback
        fallback_reply = self._fallback_chat(cleaned_prompt)
        self._record_turn(cleaned_prompt, fallback_reply, add_to_history)
        return fallback_reply

    def _record_turn(self, user_text: str, assistant_text: str, add_to_history: bool = True):
        """Record user and assistant turns to RAM history and persistent SQLite store."""
        if not add_to_history:
            return
        self.conversation_history.append({"role": "user", "content": user_text})
        self.conversation_history.append({"role": "assistant", "content": assistant_text})
        if len(self.conversation_history) > self.max_history * 2:
            self.conversation_history = self.conversation_history[-self.max_history * 2:]
        if self.persistent_memory:
            try:
                self.persistent_memory.add_message("user", user_text)
                self.persistent_memory.add_message("assistant", assistant_text)
            except Exception as e:
                logger.debug(f"[LocalLLM] Save persistent turn notice: {e}")

    def _fallback_chat(self, prompt: str) -> str:
        """Fallback to Groq chat helper, or conversational response if unreachable."""
        try:
            from octopus_ai.agent.groq_llm import GroqLLM
            groq = GroqLLM()
            if groq.is_available:
                resp = groq.chat(prompt, system_prompt=SYSTEM_PROMPT)
                content = resp.get("text") or resp.get("content") or resp.get("response", "")
                if content:
                    return sanitize_speech_response(content.strip())
        except Exception as e:
            logger.debug(f"[LocalLLM] Groq fallback notice: {e}")

        p_lower = prompt.lower()
        if any(w in p_lower for w in ["who are you", "what are you", "nuvvu evaru"]):
            return "I am Octopus AI, your personal desktop AI assistant running with full intelligence on your computer."
        elif any(w in p_lower for w in ["hello", "hi", "hey", "namaskaram", "namaste"]):
            return "Hello Dhanush! I am online and ready to assist you in English, Telugu, or any other language."
        elif "how are you" in p_lower or "ela unnav" in p_lower:
            return "I am running smoothly with full hardware acceleration, ready for any question or task."
        return f"I understand your request regarding '{prompt}'. How would you like to proceed?"

    def clear_history(self):
        """Reset conversation memory."""
        self.conversation_history.clear()


def sanitize_speech_response(text: str) -> str:
    """
    Ensure the avatar always speaks natural, clean conversational language.
    Strips out raw JSON, python code, dictionary brackets, and internal prompt leaks.
    Supports English, Telugu (తెలుగు), and all multilingual scripts.
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
                for key in ["text", "spoken_summary", "response", "message", "content", "summary", "answer"]:
                    val = parsed.get(key)
                    if isinstance(val, str) and val.strip():
                        return sanitize_speech_response(val)
        except Exception:
            pass

        # Regex fallback for JSON fields (including 'text')
        m = re.search(r'"(?:text|spoken_summary|response|message|content|summary|answer)"\s*:\s*"([^"]+)"', cleaned)
        if m:
            return sanitize_speech_response(m.group(1))

        # If it's raw JSON without identifiable fields, strip the JSON block
        cleaned = (cleaned[:start] + " " + cleaned[end+1:]).strip()

    # Remove markdown code blocks and inline code
    cleaned = re.sub(r'```[\s\S]*?```', '', cleaned)
    cleaned = re.sub(r'`[^`]*`', '', cleaned)

    # Clean markdown formatting characters while preserving all Unicode language scripts (Telugu, Hindi, etc.)
    cleaned = cleaned.replace("*", "").replace("#", "").replace("_", " ").replace(">", "")
    cleaned = re.sub(r'[ \t]+', ' ', cleaned).strip()

    if not cleaned or cleaned.startswith("{"):
        return "I am ready. How can I help you today?"
    return cleaned


# Global singleton instance
local_llm_instance = LocalLLMService.get_instance()
# Clear any polluted history on startup
local_llm_instance.clear_history()
