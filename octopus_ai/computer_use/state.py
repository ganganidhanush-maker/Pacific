"""
Pacific / Octopus AI — Computer Use State & Observation Models
Defines immutable data models for desktop state, accessibility tree elements,
window descriptors, actions, and execution results.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import time


@dataclass
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)

    @property
    def center(self) -> Tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)

    def to_dict(self) -> Dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class UIElement:
    """Represents an actionable control from the Windows UI Automation tree."""
    name: str
    control_type: str
    automation_id: str = ""
    class_name: str = ""
    rect: Optional[Rect] = None
    is_enabled: bool = True
    is_offscreen: bool = False
    supported_patterns: List[str] = field(default_factory=list)
    element_id: int = 0  # Numeric index for clean LLM referencing

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.element_id,
            "name": self.name,
            "type": self.control_type,
            "auto_id": self.automation_id,
            "class": self.class_name,
            "rect": self.rect.to_dict() if self.rect else None,
            "enabled": self.is_enabled,
            "patterns": self.supported_patterns,
        }


@dataclass
class WindowInfo:
    """Metadata for an open desktop application window."""
    hwnd: int
    title: str
    process_name: str
    pid: int
    rect: Optional[Rect] = None
    is_active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hwnd": self.hwnd,
            "title": self.title,
            "process": self.process_name,
            "pid": self.pid,
            "rect": self.rect.to_dict() if self.rect else None,
            "active": self.is_active,
        }


@dataclass
class Observation:
    """Full snapshot of the desktop environment at a given moment."""
    timestamp: float = field(default_factory=time.time)
    active_window: Optional[WindowInfo] = None
    open_windows: List[WindowInfo] = field(default_factory=list)
    elements: List[UIElement] = field(default_factory=list)
    screen_size: Tuple[int, int] = (1920, 1080)
    cursor_pos: Tuple[int, int] = (0, 0)
    screenshot_path: Optional[str] = None

    def to_dict(self, include_elements: bool = True) -> Dict[str, Any]:
        data = {
            "timestamp": self.timestamp,
            "active_window": self.active_window.to_dict() if self.active_window else None,
            "open_windows_count": len(self.open_windows),
            "screen_size": list(self.screen_size),
            "cursor_pos": list(self.cursor_pos),
            "screenshot_path": self.screenshot_path,
        }
        if include_elements:
            data["elements"] = [el.to_dict() for el in self.elements[:150]]  # Cap for context size
        return data


@dataclass
class ComputerAction:
    """A proposed or pending computer-use action."""
    tool: str
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    task_id: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class ActionResult:
    """Result of an executed desktop action."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    action: Optional[ComputerAction] = None
    duration_ms: float = 0.0
    verified: bool = False
    observation_after: Optional[Observation] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": str(self.output) if self.output is not None else None,
            "error": self.error,
            "tool": self.action.tool if self.action else None,
            "duration_ms": round(self.duration_ms, 2),
            "verified": self.verified,
        }


class ComputerState:
    """Tracks current desktop execution state, active task, and history."""
    def __init__(self):
        self.active_task_id: Optional[str] = None
        self.last_observation: Optional[Observation] = None
        self.history: List[ActionResult] = []
        self._aborted: bool = False

    @property
    def is_aborted(self) -> bool:
        return self._aborted

    def trigger_abort(self):
        self._aborted = True

    def reset_abort(self):
        self._aborted = False

    def update_observation(self, obs: Observation):
        self.last_observation = obs

    def record_result(self, result: ActionResult):
        self.history.append(result)
        if len(self.history) > 100:
            self.history.pop(0)


# Global singleton state
desktop_state = ComputerState()
