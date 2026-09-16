"""
Pacific / Octopus AI — Computer Use Event System
Provides unified real-time event publishing and subscription for desktop actions,
visual pointing, safety checks, and emergency stops.
"""

import asyncio
import logging
from enum import Enum
from typing import Dict, Any, Callable, List, Optional
from dataclasses import dataclass, field
import time

logger = logging.getLogger("ComputerUse.Events")


class ComputerEventType(str, Enum):
    # Action lifecycle
    ACTION_STARTED = "action_started"
    ACTION_COMPLETED = "action_completed"
    ACTION_FAILED = "action_failed"
    
    # Observation & screen feedback
    OBSERVATION_CAPTURED = "observation_captured"
    POINTING_EVENT = "pointing_event"
    
    # Safety & Policy
    POLICY_EVALUATED = "policy_evaluated"
    POLICY_CONFIRMATION_REQUIRED = "policy_confirmation_required"
    POLICY_BLOCKED = "policy_blocked"
    
    # Emergency Watchdog
    EMERGENCY_ABORT = "emergency_abort"
    STATE_RESET = "state_reset"


@dataclass
class ComputerEvent:
    event_type: ComputerEventType
    task_id: str
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "data": self.data,
            "message": self.message,
        }


class EventEmitter:
    """Async & sync thread-safe event emitter for computer-use events."""
    def __init__(self):
        self._listeners: Dict[ComputerEventType, List[Callable[[ComputerEvent], Any]]] = {
            et: [] for et in ComputerEventType
        }
        self._all_listeners: List[Callable[[ComputerEvent], Any]] = []

    def subscribe(self, event_type: Optional[ComputerEventType], callback: Callable[[ComputerEvent], Any]):
        if event_type is None:
            self._all_listeners.append(callback)
        else:
            self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type: Optional[ComputerEventType], callback: Callable[[ComputerEvent], Any]):
        if event_type is None:
            if callback in self._all_listeners:
                self._all_listeners.remove(callback)
        else:
            if callback in self._listeners[event_type]:
                self._listeners[event_type].remove(callback)

    def emit(self, event: ComputerEvent):
        """Dispatch event to registered callbacks (sync or scheduled async)."""
        logger.debug("Emitting event %s for task %s: %s", event.event_type.value, event.task_id, event.message)
        
        import inspect
        target_listeners = list(self._listeners.get(event.event_type, [])) + list(self._all_listeners)
        for cb in target_listeners:
            try:
                if inspect.iscoroutinefunction(cb):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(cb(event))
                    except RuntimeError:
                        asyncio.run(cb(event))
                else:
                    cb(event)
            except Exception as e:
                logger.error("Error in event callback for %s: %s", event.event_type, e, exc_info=True)


# Global singleton event emitter
event_bus = EventEmitter()
