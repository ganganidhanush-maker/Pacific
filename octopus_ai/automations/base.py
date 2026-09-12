"""
Octopus AI - Modular Automations Architecture

Defines the base classes, categories, task steps, and registry
for all agent automations (Web, Desktop, and Workflows).
"""

import time
import asyncio
from enum import Enum
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime


class AutomationCategory(str, Enum):
    WEB = "web"
    DESKTOP = "desktop"
    WORKFLOW = "workflow"


class AutomationStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class TaskStep:
    step_number: int
    title: str
    description: str
    status: str = "pending"  # pending, running, done, error
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))
    details: Optional[Dict[str, Any]] = None


@dataclass
class AutomationResult:
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    execution_time_sec: float = 0.0
    steps: List[TaskStep] = field(default_factory=list)


class BaseAutomation:
    """
    Abstract base class for all Octopus AI automations.
    """
    id: str = "base"
    name: str = "Base Automation"
    category: AutomationCategory = AutomationCategory.WEB
    description: str = ""
    icon: str = "zap"
    
    def __init__(self, driver=None, preview_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.driver = driver
        self.preview_callback = preview_callback
        self.status: AutomationStatus = AutomationStatus.IDLE
        self.steps: List[TaskStep] = []
        self._stop_requested: bool = False
        self._paused: bool = False

    def emit_step(self, step_num: int, title: str, description: str, status: str = "running", details: Optional[Dict[str, Any]] = None):
        """Record and broadcast a step update to the Agent Preview."""
        step = TaskStep(
            step_number=step_num,
            title=title,
            description=description,
            status=status,
            details=details
        )
        # Update existing step if same number, or append
        existing = next((s for s in self.steps if s.step_number == step_num), None)
        if existing:
            existing.title = title
            existing.description = description
            existing.status = status
            existing.details = details or existing.details
            step = existing
        else:
            self.steps.append(step)

        if self.preview_callback:
            self.preview_callback({
                "automation_id": self.id,
                "automation_name": self.name,
                "category": self.category.value,
                "status": self.status.value,
                "current_step": asdict(step),
                "steps": [asdict(s) for s in self.steps]
            })

    async def run(self, params: Optional[Dict[str, Any]] = None) -> AutomationResult:
        """Execute the automation with given parameters."""
        raise NotImplementedError("Subclasses must implement run()")

    def stop(self):
        """Request the automation to stop gracefully."""
        self._stop_requested = True
        self.status = AutomationStatus.STOPPED

    def pause(self):
        self._paused = True
        self.status = AutomationStatus.PAUSED

    def resume(self):
        self._paused = False
        self.status = AutomationStatus.RUNNING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "icon": self.icon,
            "status": self.status.value
        }


class AutomationRegistry:
    """
    Central registry for discovering, grouping, and launching automations.
    """
    def __init__(self):
        self._automations: Dict[str, BaseAutomation] = {}

    def register(self, automation: BaseAutomation):
        self._automations[automation.id] = automation

    def get(self, automation_id: str) -> Optional[BaseAutomation]:
        return self._automations.get(automation_id)

    def list_all(self) -> List[Dict[str, Any]]:
        return [auto.to_dict() for auto in self._automations.values()]

    def list_by_category(self, category: AutomationCategory) -> List[Dict[str, Any]]:
        return [auto.to_dict() for auto in self._automations.values() if auto.category == category]

    def get_grouped(self) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {
            AutomationCategory.WEB.value: [],
            AutomationCategory.DESKTOP.value: [],
            AutomationCategory.WORKFLOW.value: []
        }
        for auto in self._automations.values():
            grouped[auto.category.value].append(auto.to_dict())
        return grouped
