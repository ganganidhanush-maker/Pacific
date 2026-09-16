"""
Pacific / Octopus AI — Computer Use Emergency Watchdog
Monitors hardware keyboard input (ESC key) to guarantee instant emergency stop
of all computer-use actions, mouse movements, keyboard actuation, and scripts.
"""

import sys
import time
import threading
import logging
from typing import Optional, Callable

from .state import desktop_state
from .events import event_bus, ComputerEvent, ComputerEventType

logger = logging.getLogger("ComputerUse.Watchdog")

VK_ESCAPE = 0x1B


class ComputerWatchdog:
    """Background listener that halts all desktop activity the instant ESC is pressed."""
    def __init__(self, poll_interval_sec: float = 0.05):
        self.poll_interval = poll_interval_sec
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._on_abort_callbacks = []

    def register_on_abort(self, callback: Callable[[], None]):
        self._on_abort_callbacks.append(callback)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="ComputerWatchdogThread")
        self._thread.start()
        logger.info("Emergency Stop Watchdog activated (Press ESC anytime to immediately halt computer actions).")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("Emergency Stop Watchdog stopped.")

    def trigger_abort(self, reason: str = "ESC pressed"):
        """Explicitly trigger abort from hotkey, UI button, or API."""
        if not desktop_state.is_aborted:
            desktop_state.trigger_abort()
            logger.warning("🚨 EMERGENCY ABORT TRIGGERED: %s", reason)
            event_bus.emit(ComputerEvent(
                event_type=ComputerEventType.EMERGENCY_ABORT,
                task_id=desktop_state.active_task_id or "system",
                data={"reason": reason},
                message=f"Emergency halt triggered: {reason}",
            ))
            for cb in self._on_abort_callbacks:
                try:
                    cb()
                except Exception as e:
                    logger.error("Error in abort callback: %s", e)

    def reset(self):
        """Reset the abort state for next task."""
        if desktop_state.is_aborted:
            desktop_state.reset_abort()
            logger.info("Emergency abort state reset. Computer use ready.")
            event_bus.emit(ComputerEvent(
                event_type=ComputerEventType.STATE_RESET,
                task_id="system",
                message="Computer use abort state reset.",
            ))

    def _monitor_loop(self):
        """Low-overhead background loop checking for ESC key press on Windows."""
        is_windows = sys.platform == "win32"
        user32 = None
        if is_windows:
            try:
                import ctypes
                user32 = ctypes.windll.user32
            except Exception as e:
                logger.warning("Could not initialize user32 for watchdog: %s", e)

        while self._running:
            try:
                if is_windows and user32:
                    # Check if ESC key is pressed (high bit set)
                    state = user32.GetAsyncKeyState(VK_ESCAPE)
                    if state & 0x8000:
                        # Only trigger once per press
                        if not desktop_state.is_aborted:
                            self.trigger_abort("Hardware ESC key pressed by user")
                            # Debounce keypress
                            time.sleep(0.4)
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.debug("Error in watchdog polling: %s", e)
                time.sleep(0.5)


# Global singleton watchdog
watchdog = ComputerWatchdog()
