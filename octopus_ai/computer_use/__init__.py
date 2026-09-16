"""
Pacific / Octopus AI — Computer Use Package
Unified integration of Clacky + Windows-Use capabilities.
"""

import sys

from .computer_agent import ComputerAgent, computer_agent_instance
from .router import ComputerUseRouter, computer_router
from .policy import ComputerPolicyEngine, policy_engine, SafetyLevel, ExecutionMode, PolicyDecision
from .state import (
    Rect, UIElement, WindowInfo, Observation,
    ComputerAction, ActionResult, ComputerState, desktop_state
)
from .events import ComputerEventType, ComputerEvent, EventEmitter, event_bus
from .watchdog import ComputerWatchdog, watchdog
from .adapters.windows_use_adapter import WindowsUseAdapter, windows_use_adapter
from .adapters.clacky_adapter import ClackyAdapter, clacky_adapter, Routine, RoutineStep

# Aliasing so both `import computer_use` and `import octopus_ai.computer_use` resolve identically
if "octopus_ai.computer_use" not in sys.modules:
    sys.modules["octopus_ai.computer_use"] = sys.modules[__name__]

__all__ = [
    "ComputerAgent",
    "computer_agent_instance",
    "ComputerUseRouter",
    "computer_router",
    "ComputerPolicyEngine",
    "policy_engine",
    "SafetyLevel",
    "ExecutionMode",
    "PolicyDecision",
    "Rect",
    "UIElement",
    "WindowInfo",
    "Observation",
    "ComputerAction",
    "ActionResult",
    "ComputerState",
    "desktop_state",
    "ComputerEventType",
    "ComputerEvent",
    "EventEmitter",
    "event_bus",
    "ComputerWatchdog",
    "watchdog",
    "WindowsUseAdapter",
    "windows_use_adapter",
    "ClackyAdapter",
    "clacky_adapter",
    "Routine",
    "RoutineStep",
]
