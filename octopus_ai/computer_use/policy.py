"""
Pacific / Octopus AI — Computer Use Safety Policy Engine
Enforces 3-tier safety boundaries:
- SAFE: Instant autonomous execution (read tree, click element, typing, app focus)
- CONFIRM: Requires explicit user approval before execution (file overwrite/delete, scripts)
- HIGH_RISK: Strictly blocked by default (destructive formatting, registry edits, system credential tampering)
"""

import re
import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .events import event_bus, ComputerEvent, ComputerEventType
from .state import ComputerAction

logger = logging.getLogger("ComputerUse.Policy")


class SafetyLevel(str, Enum):
    SAFE = "safe"
    CONFIRM = "confirm"
    HIGH_RISK = "high_risk"


class ExecutionMode(str, Enum):
    STRICT = "strict"        # Always asks confirmation for any system-changing action
    BALANCED = "balanced"    # Standard production mode: SAFE is automatic, destructive actions require confirmation
    AUTONOMOUS = "autonomous"# Allows automated scripts and file edits, only strictly HIGH_RISK is blocked


@dataclass
class PolicyDecision:
    allowed: bool
    requires_confirmation: bool
    safety_level: SafetyLevel
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "requires_confirmation": self.requires_confirmation,
            "safety_level": self.safety_level.value,
            "reason": self.reason,
        }


# High-risk patterns in shell or filesystem commands that must NEVER run autonomously
HIGH_RISK_COMMAND_PATTERNS = [
    r"\bformat\b",
    r"\brmdir\s+/[sS]",
    r"\bremove-item\s+.*-recurse\s+[cC]:[\\/]",
    r"\bdel\s+/[fF]\s+/[sS]\s+/[qQ]\s+[cC]:[\\/]",
    r"\breg\s+(add|delete|copy|restore)\b",
    r"\bregedit\b",
    r"\bvssadmin\b",
    r"\bbcdedit\b",
    r"\bdiskpart\b",
    r"\bnet\s+user\b",
    r"\bnet\s+localgroup\b",
    r"\bpowershell(\.exe)?\s+.*-enc(odedcommand)?\b",
    r"\b-(enc|encodedcommand)\b",
    r"\b(curl|wget|iwr|invoke-webrequest).*\|\s*(iex|invoke-expression)\b",
    r"\bshutdown\b",
    r"\brestart-computer\b",
]

# Sensitive system paths where write or delete is prohibited
RESTRICTED_SYSTEM_PATHS = [
    r"^[a-zA-Z]:\\windows",
    r"^[a-zA-Z]:\\program files",
    r"^[a-zA-Z]:\\system volume information",
    r"^[a-zA-Z]:\\boot",
]


class ComputerPolicyEngine:
    def __init__(self, mode: ExecutionMode = ExecutionMode.BALANCED):
        self.mode = mode
        self._pending_confirmations: Dict[str, ComputerAction] = {}

    def set_mode(self, mode: ExecutionMode):
        self.mode = mode
        logger.info("Computer Policy execution mode set to: %s", mode.value)

    def evaluate(self, action: ComputerAction) -> PolicyDecision:
        tool = action.tool.lower()
        params = action.params

        # 1. Inspect tool type
        if tool in ["observe", "read_tree", "get_window", "get_mouse", "screenshot", "get_system_info", "scrape"]:
            return PolicyDecision(allowed=True, requires_confirmation=False, safety_level=SafetyLevel.SAFE, reason="Read-only observation")

        if tool in ["click", "double_click", "right_click", "move_mouse", "scroll", "type_text", "key_press", "shortcut", "point_element"]:
            return PolicyDecision(allowed=True, requires_confirmation=False, safety_level=SafetyLevel.SAFE, reason="Standard UI interaction")

        if tool in ["launch_app", "focus_window", "minimize_window", "maximize_window"]:
            app_name = str(params.get("app_name", "")).lower()
            if any(forbidden in app_name for forbidden in ["cmd.exe", "powershell.exe", "regedit.exe"]):
                if self.mode == ExecutionMode.STRICT:
                    return PolicyDecision(allowed=True, requires_confirmation=True, safety_level=SafetyLevel.CONFIRM, reason=f"Launching shell {app_name} requires confirmation")
            return PolicyDecision(allowed=True, requires_confirmation=False, safety_level=SafetyLevel.SAFE, reason=f"Application lifecycle: {app_name}")

        if tool == "file_operation":
            op = str(params.get("operation", "")).lower()
            path = str(params.get("path", "")).strip()

            # Check sensitive paths
            for restricted in RESTRICTED_SYSTEM_PATHS:
                if re.search(restricted, path, re.IGNORECASE):
                    return PolicyDecision(allowed=False, requires_confirmation=False, safety_level=SafetyLevel.HIGH_RISK, reason=f"Access to protected system path denied: {path}")

            if op in ["read", "list", "exists", "stat"]:
                return PolicyDecision(allowed=True, requires_confirmation=False, safety_level=SafetyLevel.SAFE, reason="Read-only file operation")

            if op in ["delete", "remove"]:
                if self.mode != ExecutionMode.AUTONOMOUS:
                    return PolicyDecision(allowed=True, requires_confirmation=True, safety_level=SafetyLevel.CONFIRM, reason=f"Deleting file requires confirmation: {path}")
                return PolicyDecision(allowed=True, requires_confirmation=False, safety_level=SafetyLevel.SAFE, reason="Autonomous file deletion")

            if op in ["write", "overwrite"]:
                return PolicyDecision(allowed=True, requires_confirmation=False, safety_level=SafetyLevel.SAFE, reason="Standard file creation/write")

        if tool in ["shell", "powershell", "execute_command"]:
            cmd = str(params.get("command", "")).strip()

            # Check high-risk command patterns
            for pattern in HIGH_RISK_COMMAND_PATTERNS:
                if re.search(pattern, cmd, re.IGNORECASE):
                    logger.warning("HIGH RISK COMMAND BLOCKED: %s", cmd)
                    event_bus.emit(ComputerEvent(
                        event_type=ComputerEventType.POLICY_BLOCKED,
                        task_id=action.task_id,
                        data={"command": cmd, "pattern": pattern},
                        message=f"Blocked high-risk command matching '{pattern}'",
                    ))
                    return PolicyDecision(
                        allowed=False,
                        requires_confirmation=False,
                        safety_level=SafetyLevel.HIGH_RISK,
                        reason=f"Dangerous command pattern detected: {pattern}",
                    )

            # Check safe read commands
            safe_read_commands = [r"^dir\b", r"^ls\b", r"^echo\b", r"^type\b", r"^cat\b", r"^get-date\b", r"^get-process\b", r"^ipconfig\b", r"^whoami\b", r"^hostname\b"]
            if any(re.search(p, cmd, re.IGNORECASE) for p in safe_read_commands):
                return PolicyDecision(allowed=True, requires_confirmation=False, safety_level=SafetyLevel.SAFE, reason="Safe diagnostic command")

            if self.mode == ExecutionMode.STRICT:
                return PolicyDecision(allowed=True, requires_confirmation=True, safety_level=SafetyLevel.CONFIRM, reason=f"Strict mode requires confirmation for shell command: {cmd}")

            return PolicyDecision(allowed=True, requires_confirmation=False, safety_level=SafetyLevel.SAFE, reason="Shell command permitted in balanced mode")

        # Fallback default
        return PolicyDecision(allowed=True, requires_confirmation=False, safety_level=SafetyLevel.SAFE, reason="Default action rule")

    def register_pending_confirmation(self, confirmation_id: str, action: ComputerAction):
        self._pending_confirmations[confirmation_id] = action
        event_bus.emit(ComputerEvent(
            event_type=ComputerEventType.POLICY_CONFIRMATION_REQUIRED,
            task_id=action.task_id,
            data={"confirmation_id": confirmation_id, "action": action.tool, "params": action.params},
            message=f"Action '{action.tool}' requires confirmation before proceeding",
        ))

    def resolve_confirmation(self, confirmation_id: str, approved: bool) -> Optional[ComputerAction]:
        action = self._pending_confirmations.pop(confirmation_id, None)
        if action and not approved:
            logger.info("Confirmation for action %s was rejected by user", action.tool)
            return None
        return action


# Global singleton policy engine
policy_engine = ComputerPolicyEngine()
