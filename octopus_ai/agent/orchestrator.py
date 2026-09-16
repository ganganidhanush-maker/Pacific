"""
Master Multi-Agent Orchestrator for Octopus AI
Acts as the central intelligence behind the Main Agent Avatar:
- Optimizes and decomposes natural student/teacher requests into structured sub-tasks
- Coordinates WebAgent, DesktopAgent, ResearchAgent, and ChatbotAgent
- Handles complex real-world workflows (e.g. Teacher WhatsApp PTM broadcast & contextual auto-reply)
- Synthesizes multi-agent actions into a clean spoken summary for the Avatar
"""

import os
import re
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional

from .subagents.web_agent import web_agent_instance
from .subagents.desktop_agent import desktop_agent_instance
from .subagents.research_agent import research_agent_instance
from .subagents.chatbot_agent import chatbot_agent_instance
from computer_use import computer_agent_instance
from server.local_llm_service import local_llm_instance

logger = logging.getLogger("MasterOrchestrator")


class MasterOrchestrator:
    def __init__(self):
        self.web_agent = web_agent_instance
        self.desktop_agent = desktop_agent_instance
        self.research_agent = research_agent_instance
        self.chatbot_agent = chatbot_agent_instance
        self.computer_agent = computer_agent_instance

    async def optimize_and_decompose(self, raw_prompt: str) -> Dict[str, Any]:
        """
        AI Prompt Optimizer Layer:
        Decomposes user's natural prompt into a structured multi-agent execution plan.
        """
        system_prompt = (
            "You are the Master AI Orchestrator for educational and productivity automation. "
            "Analyze the user's prompt and decompose it into a structured JSON execution plan.\n\n"
            "Identify:\n"
            "1. 'primary_intent': Brief description of goal.\n"
            "2. 'requires_web': true/false (WhatsApp, Canva, Instagram, Google Search).\n"
            "3. 'requires_desktop': true/false (Find local files, move files, create scripts).\n"
            "4. 'requires_research': true/false (Topic research, slide outlines).\n"
            "5. 'requires_chat': true/false (General conversation, question answering).\n"
            "6. 'web_tasks': Array of tasks for Web Agent (e.g. whatsapp_broadcast, canva_design, web_search).\n"
            "7. 'desktop_tasks': Array of tasks for Desktop Agent (e.g. find_files, organize_files, touch_file).\n"
            "8. 'research_tasks': Array of topics to research or outline.\n"
            "9. 'whatsapp_context': { 'groups': [], 'topic': '', 'sender_persona': 'Saiteja', 'filter_unrelated_as_unread': true } if WhatsApp is mentioned.\n"
            "10. 'spoken_summary': A 1-2 sentence spoken acknowledgement for the avatar to say out loud.\n\n"
            "Return ONLY valid JSON matching this structure without Markdown blocks."
        )

        user_content = f"Decompose this request:\n\"{raw_prompt}\""
        
        # Call Local LLM or Groq to optimize the prompt (with history isolated)
        try:
            full_prompt = f"{system_prompt}\n\nUser Request: {raw_prompt}\n\nJSON Output:"
            raw_response = await local_llm_instance.generate_response(full_prompt, add_to_history=False)
            # Clean JSON markdown if model wrapped it in ```json ... ```
            cleaned = re.sub(r"^```json\s*", "", raw_response.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"^```\s*$", "", cleaned.strip(), flags=re.MULTILINE).strip()
            
            # Find the first { and last }
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                return json.loads(cleaned[start:end+1])
        except Exception as e:
            logger.warning(f"[Orchestrator] LLM JSON decomposition fallback: {e}")

        # Rule-based fallback decomposition if LLM output isn't strict JSON
        p_lower = raw_prompt.lower()
        computer_keywords = [
            "notepad", "calculator", "calc", "click", "type", "open app", "launch app",
            "powershell", "terminal", "switch to", "bring to front", "screen", "highlight",
            "pointer", "mouse", "windows", "close app", "shortcut", "press", "active window",
            "minimize", "maximize", "inspect ui", "routine"
        ]
        requires_comp = any(w in p_lower for w in computer_keywords)

        plan = {
            "primary_intent": raw_prompt,
            "requires_web": any(w in p_lower for w in ["whatsapp", "canva", "instagram", "search", "google", "web"]),
            "requires_desktop": any(w in p_lower for w in ["file", "pdf", "touch", "move", "desktop", "script", "folder", "local"]) and not requires_comp,
            "requires_computer": requires_comp,
            "requires_research": any(w in p_lower for w in ["research", "explain", "slide", "ppt", "presentation", "syllabus"]),
            "requires_chat": False,
            "web_tasks": [],
            "desktop_tasks": [],
            "computer_tasks": [raw_prompt] if requires_comp else [],
            "research_tasks": [],
            "whatsapp_context": None,
            "spoken_summary": "I've understood your request and am coordinating the sub-agents now."
        }

        if requires_comp:
            plan["spoken_summary"] = "Computer Agent is controlling the Windows desktop to fulfill your request."

        if "whatsapp" in p_lower or "ptm" in p_lower:
            plan["requires_web"] = True
            plan["whatsapp_context"] = {
                "groups": ["Students Group", "Parents Group"] if "group" in p_lower else ["Parents Group"],
                "topic": "PTM" if "ptm" in p_lower else "important update",
                "sender_persona": "Saiteja" if "saiteja" in p_lower or "sai" in p_lower else "Dhanush",
                "filter_unrelated_as_unread": True
            }
            plan["web_tasks"].append("whatsapp_broadcast")
            plan["spoken_summary"] = "Web Agent is opening WhatsApp to broadcast your update and will manage on-topic replies while marking other chats unread."

        if "canva" in p_lower or "ppt" in p_lower or "presentation" in p_lower:
            plan["requires_web"] = True
            plan["requires_research"] = True
            plan["web_tasks"].append("canva_design")
            plan["research_tasks"].append(raw_prompt)

        if ("pdf" in p_lower or "file" in p_lower) and not requires_comp:
            plan["requires_desktop"] = True
            plan["desktop_tasks"].append("find_files")

        return plan

    async def _execute_web_subtask(self, plan: Dict[str, Any], raw_prompt: str) -> Dict[str, Any]:
        """Execute web automation tasks (WhatsApp, Canva, Instagram, search)."""
        res: Dict[str, Any] = {"results": {}, "bullets": []}
        try:
            wa_ctx = plan.get("whatsapp_context")
            if wa_ctx:
                groups = wa_ctx.get("groups", ["Students Group", "Parents Group"])
                topic = wa_ctx.get("topic", "PTM")
                persona = wa_ctx.get("sender_persona", "Saiteja")
                msg = f"Dear Parents and Students, kindly note that tomorrow's {topic.upper()} will be held as scheduled. Please reach out if you have any questions."
                
                broadcast_res = await self.web_agent.send_whatsapp_broadcast(groups, msg, sender_name=persona)
                res["results"]["web_whatsapp"] = broadcast_res
                res["bullets"].append(f"🌐 Web Agent: Broadcast sent to {len(groups)} group(s) as {persona}.")
                res["bullets"].append(f"💬 Active Filter: Replies on '{topic}' will be answered; unrelated chats marked as unread.")

            elif "canva_design" in plan.get("web_tasks", []):
                topic = plan.get("research_tasks", ["presentation"])[0] if plan.get("research_tasks") else "presentation"
                canva_res = await self.web_agent.open_canva_presentation(topic)
                res["results"]["web_canva"] = canva_res
                res["bullets"].append(f"🎨 Web Agent: Opened Canva presentation templates for '{topic}'.")

            elif any("instagram" in str(t).lower() for t in plan.get("web_tasks", [])):
                ig_res = await self.web_agent.open_instagram()
                res["results"]["web_instagram"] = ig_res
                res["bullets"].append("📸 Web Agent: Opened Instagram notifications.")
        except Exception as e:
            logger.error(f"[Orchestrator] Web subtask error: {e}")
            res["results"]["web_error"] = str(e)
            res["bullets"].append(f"⚠️ Web Agent Notice: {e}")
        return res

    async def _execute_research_subtask(self, plan: Dict[str, Any], raw_prompt: str) -> Dict[str, Any]:
        """Execute academic research & slide outline tasks."""
        res: Dict[str, Any] = {"results": {}, "bullets": []}
        try:
            tasks = plan.get("research_tasks", []) or [raw_prompt]
            for r_task in tasks:
                r_res = await self.research_agent.research_topic(r_task)
                res["results"]["research"] = r_res
                res["bullets"].append(f"🔬 Research Agent: Synthesized knowledge & slide concepts for '{r_task}'.")
        except Exception as e:
            logger.error(f"[Orchestrator] Research subtask error: {e}")
            res["results"]["research_error"] = str(e)
            res["bullets"].append(f"⚠️ Research Agent Notice: {e}")
        return res

    async def _execute_desktop_subtask(self, plan: Dict[str, Any], raw_prompt: str) -> Dict[str, Any]:
        """Execute local filesystem and Open Interpreter code runner tasks."""
        res: Dict[str, Any] = {"results": {}, "bullets": []}
        loop = asyncio.get_event_loop()
        p_lower = raw_prompt.lower()
        try:
            # If prompt requests executing code or running a command
            if any(w in p_lower for w in ["run code", "execute code", "run python", "terminal command", "execute command"]):
                desktop_res = await self.desktop_agent.execute_task(raw_prompt)
                res["results"]["desktop_task"] = desktop_res
                if desktop_res.get("success"):
                    res["bullets"].append(f"💻 Desktop Agent: {desktop_res.get('message', 'Executed command.')}")
                else:
                    res["bullets"].append(f"⚠️ Desktop Agent: {desktop_res.get('error', 'Execution failed.')}")
            else:
                # Local file scan
                exts = [".pdf"] if "pdf" in p_lower else ([".py"] if "python" in p_lower else None)
                d_res = await loop.run_in_executor(
                    None,
                    lambda: self.desktop_agent.find_local_files(query="", extensions=exts, max_results=10)
                )
                res["results"]["desktop_files"] = d_res
                count = len(d_res)
                res["bullets"].append(f"💻 Desktop Agent: Scanned PC and found {count} related local file(s).")
        except Exception as e:
            logger.error(f"[Orchestrator] Desktop subtask error: {e}")
            res["results"]["desktop_error"] = str(e)
            res["bullets"].append(f"⚠️ Desktop Agent Notice: {e}")
        return res

    async def _execute_computer_subtask(self, plan: Dict[str, Any], raw_prompt: str) -> Dict[str, Any]:
        """Execute autonomous Windows computer use actions via ComputerAgent."""
        res: Dict[str, Any] = {"results": {}, "bullets": []}
        try:
            task_res = await self.computer_agent.run_task(raw_prompt)
            res["results"]["computer_task"] = task_res
            if task_res.get("success"):
                res["bullets"].append(
                    f"🖥️ Computer Agent: Successfully completed '{raw_prompt}' in {task_res.get('duration_sec')}s "
                    f"({task_res.get('steps_executed')} action steps)."
                )
            elif task_res.get("aborted"):
                res["bullets"].append("🛑 Computer Agent: Halted immediately by emergency stop (ESC).")
            else:
                res["bullets"].append(f"⚠️ Computer Agent Notice: {task_res.get('spoken_summary')}")
        except Exception as e:
            logger.error(f"[Orchestrator] Computer subtask error: {e}")
            res["results"]["computer_error"] = str(e)
            res["bullets"].append(f"⚠️ Computer Agent Notice: {e}")
        return res

    async def execute_plan(self, plan: Dict[str, Any], raw_prompt: str) -> Dict[str, Any]:
        """
        Execute decomposed subagent tasks concurrently using dynamic parallelism (asyncio.gather).
        Compiles an integrated executive summary for the Avatar Brain to speak aloud.
        """
        execution_report = {
            "plan": plan,
            "subagent_results": {},
            "spoken_response": plan.get("spoken_summary", "Task coordination complete."),
            "summary_bullets": []
        }

        # Collect concurrent subagent coroutines
        coros = []
        labels = []

        if plan.get("requires_web"):
            coros.append(self._execute_web_subtask(plan, raw_prompt))
            labels.append("web")

        if plan.get("requires_research"):
            coros.append(self._execute_research_subtask(plan, raw_prompt))
            labels.append("research")

        if plan.get("requires_desktop"):
            coros.append(self._execute_desktop_subtask(plan, raw_prompt))
            labels.append("desktop")

        if plan.get("requires_computer"):
            coros.append(self._execute_computer_subtask(plan, raw_prompt))
            labels.append("computer")

        # 1. DYNAMIC PARALLEL EXECUTION (Runs independent subagents simultaneously)
        if coros:
            results = await asyncio.gather(*coros, return_exceptions=True)
            for label, res in zip(labels, results):
                if isinstance(res, Exception):
                    logger.error(f"[Orchestrator] Subagent '{label}' threw exception: {res}")
                    execution_report["subagent_results"][f"{label}_error"] = str(res)
                    execution_report["summary_bullets"].append(f"⚠️ {label.title()} Agent encountered an issue: {res}")
                elif isinstance(res, dict):
                    execution_report["subagent_results"].update(res.get("results", {}))
                    execution_report["summary_bullets"].extend(res.get("bullets", []))

        # 2. CHATBOT AGENT (If pure conversational Q&A without tool delegation)
        else:
            chat_res = await self.chatbot_agent.chat(raw_prompt)
            execution_report["spoken_response"] = chat_res.get("response")
            execution_report["subagent_results"]["chat"] = chat_res

        return execution_report


master_orchestrator_instance = MasterOrchestrator()
