"""
Pacific / Octopus AI — Computer Use Bridge Client
Allows FastAPI routes and MasterOrchestrator to invoke computer actions seamlessly,
with automatic in-process fast path or HTTP IPC communication.
"""

import time
import logging
from typing import Dict, Any, Optional

from .protocol import BridgeRequest, BridgeResponse, BridgeMessageType
from ..computer_agent import computer_agent_instance
from ..state import desktop_state

logger = logging.getLogger("ComputerUse.BridgeClient")


class ComputerBridgeClient:
    """Client for controlling the computer-use subsystem from backend or API services."""

    def __init__(self, bridge_url: Optional[str] = None):
        self.bridge_url = bridge_url  # None indicates in-process execution

    async def execute_task(self, goal: str, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute a full multi-step computer task."""
        return await computer_agent_instance.run_task(goal, task_id=task_id)

    def execute_action(self, tool: str, params: Dict[str, Any], description: str = "") -> Dict[str, Any]:
        """Execute a single atomic computer-use action."""
        res = computer_agent_instance.execute_action(tool=tool, params=params, description=description)
        return res.to_dict()

    def observe(self, include_elements: bool = True) -> Dict[str, Any]:
        """Capture live desktop snapshot."""
        obs = computer_agent_instance.observe(include_elements=include_elements)
        return obs.to_dict(include_elements=include_elements)

    def emergency_stop(self, reason: str = "API Request") -> Dict[str, Any]:
        """Trigger immediate emergency stop."""
        computer_agent_instance.watchdog.trigger_abort(reason=reason)
        return {"success": True, "message": "Emergency stop triggered.", "aborted": True}

    def reset_state(self) -> Dict[str, Any]:
        """Reset abort state for new tasks."""
        computer_agent_instance.watchdog.reset()
        return {"success": True, "message": "Desktop state reset.", "aborted": False}

    def get_status(self) -> Dict[str, Any]:
        """Query current execution status."""
        return {
            "active_task_id": desktop_state.active_task_id,
            "is_aborted": desktop_state.is_aborted,
            "last_action": desktop_state.history[-1].to_dict() if desktop_state.history else None,
            "history_count": len(desktop_state.history),
        }


# Global bridge client instance
bridge_client = ComputerBridgeClient()
