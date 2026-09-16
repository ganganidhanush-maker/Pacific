"""
Pacific / Octopus AI — Computer Use Router
Coordinates execution between Windows-Use (low-level OS/UIA actuation) and Clacky (visual companion/pointing),
enforcing safety policies and abort checks before every tool invocation.
"""

import time
import logging
from typing import Dict, Any, Optional

from .state import (
    ComputerAction, ActionResult, Observation,
    desktop_state
)
from .policy import policy_engine, SafetyLevel
from .events import event_bus, ComputerEvent, ComputerEventType
from .adapters.windows_use_adapter import windows_use_adapter
from .adapters.clacky_adapter import clacky_adapter

logger = logging.getLogger("ComputerUse.Router")


class ComputerUseRouter:
    """Dispatches computer actions to the appropriate adapter with safety and observation."""

    def __init__(self):
        self.windows = windows_use_adapter
        self.clacky = clacky_adapter
        self.policy = policy_engine

    def execute(self, action: ComputerAction) -> ActionResult:
        start_time = time.time()
        tool = action.tool.lower().strip()
        params = action.params

        # 1. Emergency Abort Check
        if desktop_state.is_aborted:
            logger.warning("Action '%s' blocked by active emergency abort", tool)
            return ActionResult(
                success=False,
                error="Execution halted by emergency stop (ESC).",
                action=action,
                duration_ms=(time.time() - start_time) * 1000,
            )

        # 2. Safety Policy Evaluation
        decision = self.policy.evaluate(action)
        if not decision.allowed:
            logger.warning("Action '%s' blocked by policy: %s", tool, decision.reason)
            return ActionResult(
                success=False,
                error=f"Action blocked by policy: {decision.reason}",
                action=action,
                duration_ms=(time.time() - start_time) * 1000,
            )

        if decision.requires_confirmation:
            confirmation_id = f"conf_{int(time.time()*1000)}"
            self.policy.register_pending_confirmation(confirmation_id, action)
            return ActionResult(
                success=False,
                error=f"Confirmation required. Pending ID: {confirmation_id}. Reason: {decision.reason}",
                action=action,
                duration_ms=(time.time() - start_time) * 1000,
            )

        # 3. Action Dispatch
        event_bus.emit(ComputerEvent(
            event_type=ComputerEventType.ACTION_STARTED,
            task_id=action.task_id,
            data={"tool": tool, "params": params},
            message=f"Executing tool {tool}",
        ))

        success = False
        output: Any = None
        error: Optional[str] = None
        verified = False

        try:
            # --- Windows & Application Lifecycle ---
            if tool in ["launch_app", "open_app"]:
                app = params.get("app_name") or params.get("app") or params.get("target", "")
                success = self.windows.launch_app(app)
                output = f"Launched application: {app}" if success else f"Failed to launch: {app}"
                verified = self.windows.verify_state("process_running", app.split(".")[0]) or success

            elif tool in ["focus_window", "switch_window"]:
                title = params.get("title", "")
                success = self.windows.focus_window(title)
                output = f"Focused window: {title}" if success else f"Window not found: {title}"
                verified = success

            elif tool == "close_window":
                title = params.get("title", "")
                success = self.windows.close_window(title)
                output = f"Closed window: {title}" if success else f"Could not close: {title}"

            elif tool in ["list_windows", "get_windows"]:
                windows = self.windows.list_windows()
                success = True
                output = [w.to_dict() for w in windows]

            # --- UI Automation Inspection ---
            elif tool in ["read_tree", "get_elements", "inspect_ui"]:
                max_el = params.get("max_elements", 100)
                elements = self.windows.get_ui_elements(max_elements=max_el)
                success = True
                output = [e.to_dict() for e in elements]

            elif tool == "observe":
                obs = self.windows.observe()
                success = True
                output = obs.to_dict()

            # --- Mouse & Keyboard Actuation ---
            elif tool == "click":
                x = params.get("x")
                y = params.get("y")
                double = bool(params.get("double", False))
                button = params.get("button", "left")

                # If element_id or name was provided, find its center coordinate
                if x is None or y is None:
                    name_query = params.get("element_name") or params.get("target_text")
                    if name_query:
                        elements = self.windows.get_ui_elements()
                        for el in elements:
                            if name_query.lower() in el.name.lower() and el.rect:
                                x, y = el.rect.center
                                # Clacky companion visual highlight before clicking
                                self.clacky.point_element(el.rect, label=f"Click: {el.name}", duration_sec=1.5)
                                time.sleep(0.2)
                                break

                if x is not None and y is not None:
                    # Provide visual companion pulse
                    self.clacky.point_to(x, y, label="Click Target", duration_sec=1.0)
                    success = self.windows.click(x=x, y=y, button=button, double=double)
                    output = f"Clicked at ({x}, {y})"
                else:
                    error = "No coordinates or identifiable element found to click."

            elif tool in ["type", "type_text"]:
                text = params.get("text", "")
                interval = float(params.get("interval", 0.02))
                success = self.windows.type_text(text, interval=interval)
                output = f"Typed {len(text)} characters."

            elif tool in ["shortcut", "hotkey"]:
                keys = params.get("keys", [])
                if isinstance(keys, str):
                    keys = [k.strip() for k in keys.split("+")]
                success = self.windows.shortcut(keys)
                output = f"Sent shortcut: {'+'.join(keys)}"

            elif tool == "move_mouse":
                x = params.get("x", 0)
                y = params.get("y", 0)
                success = self.windows.move_mouse(x, y)
                output = f"Moved mouse to ({x}, {y})"

            elif tool == "scroll":
                clicks = params.get("clicks", 3)
                success = self.windows.scroll(clicks)
                output = f"Scrolled {clicks} clicks"

            # --- PowerShell Shell ---
            elif tool in ["shell", "powershell", "execute_command"]:
                command = params.get("command", "")
                timeout = int(params.get("timeout", 15))
                res = self.windows.run_powershell(command, timeout=timeout)
                success = res["success"]
                output = res.get("stdout") or res.get("stderr") or ("Success" if success else "Failed")
                if not success:
                    error = res.get("error") or res.get("stderr")

            # --- Filesystem Operations ---
            elif tool == "file_operation":
                op = params.get("operation", "read")
                path = params.get("path", "")
                content = params.get("content")
                res = self.windows.file_op(op, path, content=content)
                success = res["success"]
                output = res.get("content") or res.get("items") or res.get("path") or res
                if not success:
                    error = res.get("error")

            # --- Clacky Visual Pointing ---
            elif tool in ["point_to", "highlight"]:
                x = params.get("x", 0)
                y = params.get("y", 0)
                label = params.get("label", "")
                duration = float(params.get("duration", 2.0))
                output = self.clacky.point_to(x, y, label=label, duration_sec=duration)
                success = True

            elif tool == "screenshot":
                path = self.clacky.capture_screen()
                success = path is not None
                output = {"screenshot_path": path}

            # --- Routines ---
            elif tool == "start_routine_recording":
                name = params.get("name", f"routine_{int(time.time())}")
                desc = params.get("description", "")
                success = self.clacky.start_recording(name, desc)
                output = f"Recording started for {name}"

            elif tool == "stop_routine_recording":
                routine = self.clacky.stop_recording()
                success = routine is not None
                output = routine.to_dict() if routine else "No active recording"

            elif tool == "run_routine":
                name = params.get("name", "")
                routine = self.clacky.get_routine(name)
                if routine:
                    results = []
                    for step in routine.steps:
                        sub_act = ComputerAction(tool=step.tool, params=step.params, task_id=action.task_id)
                        res = self.execute(sub_act)
                        results.append(res.to_dict())
                        if not res.success:
                            break
                    success = all(r.get("success") for r in results)
                    output = {"steps_executed": len(results), "details": results}
                else:
                    error = f"Routine not found: {name}"

            else:
                error = f"Unknown computer-use tool: {tool}"

            # Clacky routine recording hook
            if success and tool not in ["start_routine_recording", "stop_routine_recording", "observe"]:
                self.clacky.record_step(tool=tool, params=params, description=action.description)

        except Exception as e:
            logger.error("Exception executing tool '%s': %s", tool, e, exc_info=True)
            error = str(e)
            success = False

        duration = (time.time() - start_time) * 1000
        result = ActionResult(
            success=success,
            output=output,
            error=error,
            action=action,
            duration_ms=duration,
            verified=verified,
        )
        desktop_state.record_result(result)

        event_bus.emit(ComputerEvent(
            event_type=ComputerEventType.ACTION_COMPLETED if success else ComputerEventType.ACTION_FAILED,
            task_id=action.task_id,
            data=result.to_dict(),
            message=f"Tool {tool} {'succeeded' if success else 'failed'}",
        ))

        return result


# Global singleton router
computer_router = ComputerUseRouter()
