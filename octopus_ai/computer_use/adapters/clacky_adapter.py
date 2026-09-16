"""
Pacific / Octopus AI — Clacky Desktop Companion Adapter
Integrates Clacky's companion capabilities:
- DPI-aware coordinate normalization across monitors
- Element pointing and visual pulse feedback
- Routine / skill learning & replay engine
- Screen capture for multimodal fallback
"""

import os
import json
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

from ..events import event_bus, ComputerEvent, ComputerEventType
from ..state import Rect, desktop_state

logger = logging.getLogger("ComputerUse.ClackyAdapter")


@dataclass
class RoutineStep:
    tool: str
    params: Dict[str, Any]
    description: str = ""


@dataclass
class Routine:
    name: str
    description: str
    steps: List[RoutineStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "steps": [{"tool": s.tool, "params": s.params, "description": s.description} for s in self.steps],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Routine":
        steps = [RoutineStep(tool=s["tool"], params=s.get("params", {}), description=s.get("description", "")) for s in data.get("steps", [])]
        return cls(name=data["name"], description=data.get("description", ""), steps=steps, created_at=data.get("created_at", time.time()))


class ClackyAdapter:
    """Desktop companion layer adapted from Clacky."""

    def __init__(self, routines_storage_path: Optional[str] = None):
        if routines_storage_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.routines_file = os.path.join(base_dir, "routines.json")
        else:
            self.routines_file = routines_storage_path

        self._active_recording: Optional[Routine] = None
        self._routines: Dict[str, Routine] = {}
        self._load_routines()

    # =========================================================================
    # 1. Coordinate Normalization & DPI Awareness
    # =========================================================================

    def normalize_coords(self, norm_x: float, norm_y: float) -> Tuple[int, int]:
        """Convert normalized (0.0 - 1.0) coordinates to absolute desktop pixel coordinates."""
        try:
            import pyautogui
            size = pyautogui.size()
            width, height = size.width, size.height
        except Exception:
            width, height = (1920, 1080)

        pixel_x = int(max(0.0, min(1.0, norm_x)) * width)
        pixel_y = int(max(0.0, min(1.0, norm_y)) * height)
        return (pixel_x, pixel_y)

    def denormalize_coords(self, pixel_x: int, pixel_y: int) -> Tuple[float, float]:
        """Convert pixel coordinates to normalized (0.0 - 1.0) range."""
        try:
            import pyautogui
            size = pyautogui.size()
            width, height = size.width, size.height
        except Exception:
            width, height = (1920, 1080)

        norm_x = round(max(0, min(width, pixel_x)) / max(1, width), 4)
        norm_y = round(max(0, min(height, pixel_y)) / max(1, height), 4)
        return (norm_x, norm_y)

    # =========================================================================
    # 2. Visual Pointing & Highlight Feedback
    # =========================================================================

    def point_to(self, x: int, y: int, label: str = "", duration_sec: float = 2.0, color: str = "#00E5FF") -> Dict[str, Any]:
        """
        Emit a visual pointing event so the UI overlay renders a highlight ring / pointer
        at the specified coordinate. Does not steal or freeze the user's mouse.
        """
        logger.info("Visual Pointing at (%d, %d): '%s' [%.1fs]", x, y, label, duration_sec)
        norm_x, norm_y = self.denormalize_coords(x, y)
        event_data = {
            "x": x,
            "y": y,
            "norm_x": norm_x,
            "norm_y": norm_y,
            "label": label,
            "duration": duration_sec,
            "color": color,
        }

        event_bus.emit(ComputerEvent(
            event_type=ComputerEventType.POINTING_EVENT,
            task_id=desktop_state.active_task_id or "system",
            data=event_data,
            message=f"Highlighting {label} at ({x}, {y})",
        ))

        return {"success": True, "pointing": event_data}

    def point_element(self, rect: Rect, label: str = "", duration_sec: float = 2.0) -> Dict[str, Any]:
        """Highlight a UI element given its bounding rectangle."""
        cx, cy = rect.center
        return self.point_to(cx, cy, label=label or "Target Element", duration_sec=duration_sec)

    # =========================================================================
    # 3. Screen Capture for Multimodal Vision Fallback
    # =========================================================================

    def capture_screen(self, output_path: Optional[str] = None) -> Optional[str]:
        """Capture full screen image for vision inspection if UIA is unavailable."""
        if output_path is None:
            import tempfile
            output_path = os.path.join(tempfile.gettempdir(), f"pacific_screen_{int(time.time()*1000)}.png")

        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab(all_screens=True)
            screenshot.save(output_path, "PNG")
            logger.info("Desktop screenshot saved to: %s", output_path)
            return output_path
        except Exception as e:
            logger.error("Failed to capture screen: %s", e)
            return None

    # =========================================================================
    # 4. Routine Learning & Automation Sequences
    # =========================================================================

    def start_recording(self, routine_name: str, description: str = "") -> bool:
        """Start recording a sequence of actions into a reusable routine."""
        self._active_recording = Routine(name=routine_name, description=description)
        logger.info("Started recording routine: %s", routine_name)
        return True

    def record_step(self, tool: str, params: Dict[str, Any], description: str = ""):
        """Record an executed step if recording is active."""
        if self._active_recording is not None:
            self._active_recording.steps.append(RoutineStep(tool=tool, params=params, description=description))

    def stop_recording(self) -> Optional[Routine]:
        """Stop recording and save the routine."""
        if self._active_recording is None:
            return None
        routine = self._active_recording
        self._active_recording = None
        self._routines[routine.name] = routine
        self._save_routines()
        logger.info("Saved routine '%s' with %d steps", routine.name, len(routine.steps))
        return routine

    def get_routine(self, name: str) -> Optional[Routine]:
        return self._routines.get(name)

    def list_routines(self) -> List[Dict[str, Any]]:
        return [{"name": r.name, "description": r.description, "steps_count": len(r.steps)} for r in self._routines.values()]

    def _load_routines(self):
        if os.path.exists(self.routines_file):
            try:
                with open(self.routines_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._routines = {k: Routine.from_dict(v) for k, v in data.items()}
            except Exception as e:
                logger.warning("Could not load routines from %s: %s", self.routines_file, e)

    def _save_routines(self):
        try:
            with open(self.routines_file, "w", encoding="utf-8") as f:
                json.dump({k: v.to_dict() for k, v in self._routines.items()}, f, indent=2)
        except Exception as e:
            logger.error("Failed to save routines to %s: %s", self.routines_file, e)


# Global singleton adapter instance
clacky_adapter = ClackyAdapter()
