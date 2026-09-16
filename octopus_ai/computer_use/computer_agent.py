"""
Pacific / Octopus AI — First-Class ComputerAgent
Unified autonomous agent for Windows computer use:
- Integrates deterministic low-level Windows actuation (Windows-Use)
- Integrates visual screen pointing, coordinate mapping, and companion feedback (Clacky)
- Driven by Kiwi / Kimi K3 and Groq LLM reasoning
- Strict Observe -> Think -> Act -> Verify execution loop
"""

import json
import time
import logging
import asyncio
from typing import Dict, List, Any, Optional

from .state import (
    ComputerAction, ActionResult, Observation,
    desktop_state
)
from .router import computer_router
from .watchdog import watchdog
from .policy import policy_engine, ExecutionMode
from .events import event_bus, ComputerEvent, ComputerEventType

logger = logging.getLogger("ComputerAgent")


class ComputerAgent:
    """Primary Pacific Computer Agent."""

    def __init__(self):
        self.router = computer_router
        self.watchdog = watchdog
        self.policy = policy_engine
        # Agent Continuity State
        self.last_target_app: Optional[str] = None
        self.last_target_window: Optional[str] = None
        self.last_created_file: Optional[str] = None
        self.last_task_output: Optional[str] = None
        self.context: Dict[str, Any] = {}
        # Ensure watchdog is running for instant ESC emergency stop
        self.watchdog.start()

    def execute_action(self, tool: str, params: Dict[str, Any], description: str = "", task_id: str = "") -> ActionResult:
        """Execute a single structured desktop action and record continuity state."""
        action = ComputerAction(
            tool=tool,
            params=params,
            description=description,
            task_id=task_id or f"task_{int(time.time()*1000)}",
        )
        res = self.router.execute(action)

        # Update continuity memory
        if res.success:
            if tool in ["launch_app", "open_app"]:
                self.last_target_app = params.get("app_name") or params.get("app")
            elif tool in ["focus_window", "switch_window"]:
                self.last_target_window = params.get("title")
            elif tool == "file_operation" and params.get("operation") in ["write", "overwrite", "append"]:
                self.last_created_file = params.get("path")
            if res.output:
                self.last_task_output = str(res.output)[:1000]

        return res

    def observe(self, include_elements: bool = True) -> Observation:
        """Capture current desktop state."""
        return self.router.windows.observe(include_elements=include_elements)

    async def run_task(self, task_goal: str, task_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute an autonomous multi-step computer-use task using Observe -> Think -> Act -> Verify loop,
        with full multi-turn agent continuity.
        """
        if context:
            self.context.update(context)

        if task_id is None:
            task_id = f"cu_{int(time.time()*1000)}"

        desktop_state.active_task_id = task_id
        desktop_state.reset_abort()

        logger.info("Starting ComputerAgent task [%s]: '%s' (Continuity: app=%s, file=%s)",
                    task_id, task_goal, self.last_target_app, self.last_created_file)
        start_time = time.time()
        step_logs: List[Dict[str, Any]] = []

        # Step 1: Initial Desktop Observation
        obs = self.observe(include_elements=True)
        active_win = obs.active_window.title if obs.active_window else "None"
        open_wins = [w.title for w in obs.open_windows[:8]]

        # Step 2: Formulate Multi-step Plan using LLM
        plan_steps = await self._plan_task(task_goal, active_win, open_wins, obs.elements)
        logger.info("ComputerAgent generated %d steps for task '%s'", len(plan_steps), task_goal)

        # Step 3: Execute and Verify Each Step
        overall_success = True
        failed_step = None

        for idx, step in enumerate(plan_steps):
            if desktop_state.is_aborted:
                logger.warning("Task %s aborted before step %d", task_id, idx + 1)
                overall_success = False
                failed_step = "Emergency Stop (ESC)"
                break

            tool = step.get("tool", "")
            params = step.get("params", {})
            desc = step.get("description", f"Step {idx + 1}")

            logger.info("Executing Step %d/%d: %s (%s)", idx + 1, len(plan_steps), tool, desc)

            action = ComputerAction(tool=tool, params=params, description=desc, task_id=task_id)
            result = self.router.execute(action)

            step_record = {
                "step": idx + 1,
                "tool": tool,
                "description": desc,
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "verified": result.verified,
                "duration_ms": result.duration_ms,
            }
            step_logs.append(step_record)

            if not result.success:
                overall_success = False
                failed_step = desc
                logger.warning("Step %d failed: %s", idx + 1, result.error)
                break

            # Brief pause for UI reaction
            await asyncio.sleep(0.4)

        duration = round(time.time() - start_time, 2)
        desktop_state.active_task_id = None

        # Build concise spoken summary for avatar
        if overall_success:
            spoken_summary = f"I've completed your task: {task_goal} in {duration} seconds."
        elif desktop_state.is_aborted:
            spoken_summary = "Computer control was immediately halted by emergency stop."
        else:
            spoken_summary = f"Task could not be completed at: {failed_step}."

        return {
            "task_id": task_id,
            "goal": task_goal,
            "success": overall_success,
            "duration_sec": duration,
            "aborted": desktop_state.is_aborted,
            "steps_executed": len(step_logs),
            "step_logs": step_logs,
            "spoken_summary": spoken_summary,
        }

    async def _plan_task(self, goal: str, active_window: str, open_windows: List[str], elements: List[Any]) -> List[Dict[str, Any]]:
        """Decomposes high-level natural language request into atomic computer-use steps."""
        # Simple heuristic fallback rules for instant response without latency
        goal_lower = goal.lower()

        # 0. Multi-Turn Continuity & Pronoun Resolution ("it", "that", "the app", "the file")
        if ("close" in goal_lower or "exit" in goal_lower or "quit" in goal_lower) and any(w in goal_lower for w in ["it", "app", "window", "that"]):
            target = self.last_target_app or self.last_target_window or "notepad"
            return [{"tool": "close_window", "params": {"title": target}, "description": f"Close {target} window"}]

        if any(act in goal_lower for act in ["type", "write", "paste", "put", "insert"]) and any(w in goal_lower for w in ["it", "there", "in that", "into it", "in it", "in notepad", "in there"]):
            target = self.last_target_app or "notepad"
            content = self.context.get("last_research_text") or "Pacific AI continuing context notes.\n"
            return [
                {"tool": "focus_window", "params": {"title": target}, "description": f"Focus {target}"},
                {"tool": "type_text", "params": {"text": content}, "description": f"Type content into {target}"}
            ]

        if "save" in goal_lower and any(w in goal_lower for w in ["it", "file", "document", "notes"]):
            return [{"tool": "shortcut", "params": {"keys": ["ctrl", "s"]}, "description": "Save active document via Ctrl+S"}]

        if ("delete" in goal_lower or "remove" in goal_lower) and any(w in goal_lower for w in ["it", "file"]) and self.last_created_file:
            return [{"tool": "file_operation", "params": {"operation": "delete", "path": self.last_created_file}, "description": f"Delete {self.last_created_file}"}]

        if "read" in goal_lower and any(w in goal_lower for w in ["it", "file", "document"]) and self.last_created_file:
            return [{"tool": "file_operation", "params": {"operation": "read", "path": self.last_created_file}, "description": f"Read back {self.last_created_file}"}]

        # 1. Notepad workflow
        if "notepad" in goal_lower and ("open" in goal_lower or "launch" in goal_lower or "write" in goal_lower or "notes" in goal_lower):
            self.last_target_app = "notepad"
            steps = [{"tool": "launch_app", "params": {"app_name": "notepad"}, "description": "Open Notepad application"}]
            if "type" in goal_lower or "write" in goal_lower or "notes" in goal_lower:
                text_to_type = "Pacific AI Meeting Notes\n- Task completed autonomously\n- Integration active\n"
                steps.append({"tool": "type_text", "params": {"text": text_to_type}, "description": "Type meeting notes into Notepad"})
            return steps

        # 1b. Calculator workflow
        if any(w in goal_lower for w in ["calculator", "calc"]) and ("open" in goal_lower or "launch" in goal_lower):
            self.last_target_app = "calc"
            return [{"tool": "launch_app", "params": {"app_name": "calc"}, "description": "Launch Windows Calculator"}]

        # 2. PowerShell / Shell diagnostic
        if any(w in goal_lower for w in ["powershell", "run command", "terminal", "system info", "check disk", "cpu"]):
            cmd = "Get-ComputerInfo | Select-Object WindowsProductName, OsArchitecture, TotalPhysicalMemory"
            if "ip" in goal_lower or "network" in goal_lower:
                cmd = "Get-NetIPAddress -AddressFamily IPv4 | Select-Object IPAddress, InterfaceAlias"
            elif "process" in goal_lower:
                cmd = "Get-Process | Sort-Object CPU -Descending | Select-Object -First 5 ProcessName, CPU, WorkingSet64"
            return [{"tool": "powershell", "params": {"command": cmd}, "description": "Execute diagnostic query via PowerShell"}]

        # 3. Window focus
        if "focus" in goal_lower or "switch to" in goal_lower or "bring to front" in goal_lower:
            for w in open_windows:
                # Find matching window title
                words = [wd for wd in w.lower().split() if len(wd) > 3]
                if any(wd in goal_lower for wd in words):
                    return [{"tool": "focus_window", "params": {"title": w}, "description": f"Focus window '{w}'"}]

        # 4. Pointing / Highlight request
        if "highlight" in goal_lower or "point" in goal_lower or "show me" in goal_lower:
            return [{"tool": "point_to", "params": {"x": 960, "y": 540, "label": "Center Focus", "duration": 2.5}, "description": "Visual highlight on screen"}]

        # 5. LLM decomposition via Local LLM / Groq
        try:
            from server.local_llm_service import local_llm_instance
            prompt = (
                f"You are the Pacific Computer Use Planner on Windows 11.\n"
                f"Active Window: {active_window}\n"
                f"Open Windows: {json.dumps(open_windows)}\n"
                f"User Goal: {goal}\n\n"
                f"Decompose into 1-4 atomic steps using tools: [launch_app, focus_window, click, type_text, shortcut, powershell, file_operation, point_to].\n"
                f"Output ONLY a JSON array of objects with keys: 'tool', 'params', 'description'. No markdown fences."
            )
            raw = await local_llm_instance.generate_response(prompt, add_to_history=False)
            clean = raw.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean)
            if isinstance(parsed, list):
                return parsed
        except Exception as e:
            logger.debug("LLM planning fallback: %s", e)

        # Default single step observation fallback
        return [{"tool": "observe", "params": {}, "description": "Inspect desktop environment"}]


# Global singleton computer agent
computer_agent_instance = ComputerAgent()
