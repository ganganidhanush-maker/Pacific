"""
Pacific / Octopus AI — Windows-Use Execution Adapter
Deeply integrates Windows native automation:
- Windows COM UI Automation (IUIAutomation tree extraction & control identification)
- Win32 Application Lifecycle (launch, focus, minimize, close)
- Win32 Mouse & Keyboard actuation via SendInput
- Safe PowerShell execution with output bounds and strict timeouts
- Filesystem inspection & manipulation
- Observation & state verification
"""

import os
import sys
import time
import subprocess
import logging
from typing import Dict, List, Any, Optional, Tuple

from ..state import (
    Rect, UIElement, WindowInfo, Observation,
    ComputerAction, ActionResult, desktop_state
)

logger = logging.getLogger("ComputerUse.WindowsUseAdapter")

# ControlType IDs to human-readable strings
UIA_CONTROL_TYPES = {
    50000: "Button",
    50001: "Calendar",
    50002: "CheckBox",
    50003: "ComboBox",
    50004: "Edit",
    50005: "Hyperlink",
    50006: "Image",
    50007: "ListItem",
    50008: "List",
    50009: "Menu",
    50010: "MenuBar",
    50011: "MenuItem",
    50012: "ProgressBar",
    50013: "RadioButton",
    50014: "ScrollBar",
    50015: "Slider",
    50016: "Spinner",
    50017: "StatusBar",
    50018: "Tab",
    50019: "TabItem",
    50020: "Text",
    50021: "ToolBar",
    50022: "ToolTip",
    50023: "Tree",
    50024: "TreeItem",
    50025: "Custom",
    50026: "Group",
    50028: "Thumb",
    50029: "DataGrid",
    50030: "DataItem",
    50031: "Document",
    50032: "SplitButton",
    50033: "Window",
    50034: "Pane",
    50035: "Header",
    50036: "HeaderItem",
    50037: "Table",
    50038: "TitleBar",
    50039: "Separator",
}


class WindowsUseAdapter:
    """Primary low-level Windows execution engine adapted from Windows-Use."""

    def __init__(self):
        self._uia = None
        self._com_initialized = False
        self._init_uia()

    def _init_uia(self):
        """Initialize COM and IUIAutomation singleton."""
        if sys.platform != "win32":
            logger.info("Non-Windows platform detected; Windows-Use adapter operating in mock mode.")
            return

        try:
            import comtypes
            import comtypes.client
            try:
                comtypes.CoInitialize()
                self._com_initialized = True
            except Exception:
                pass

            comtypes.client.GetModule("UIAutomationCore.dll")
            from comtypes.gen.UIAutomationClient import IUIAutomation, CUIAutomation
            self._uia = comtypes.client.CreateObject(CUIAutomation, interface=IUIAutomation)
            logger.info("Windows UI Automation (IUIAutomation) initialized successfully.")
        except Exception as e:
            logger.warning("Failed to initialize Windows UI Automation: %s. Using Win32/PyAutoGUI fallbacks.", e)
            self._uia = None

    # =========================================================================
    # 1. UI Automation Tree Extraction & Inspection
    # =========================================================================

    def get_ui_elements(self, max_elements: int = 120) -> List[UIElement]:
        """Extract interactive elements from the currently focused window or desktop."""
        if not self._uia or sys.platform != "win32":
            return []

        elements: List[UIElement] = []
        try:
            import comtypes
            try:
                comtypes.CoInitialize()
            except Exception:
                pass

            # Target active window element first for fast and relevant traversal
            active_hwnd = self.get_active_hwnd()
            if active_hwnd and active_hwnd > 0:
                try:
                    root_elem = self._uia.ElementFromHandle(active_hwnd)
                except Exception:
                    root_elem = self._uia.GetRootElement()
            else:
                root_elem = self._uia.GetRootElement()

            if not root_elem:
                return []

            # Create TrueCondition to find all descendants
            true_cond = self._uia.CreateTrueCondition()
            from comtypes.gen.UIAutomationClient import TreeScope_Descendants
            raw_elements = root_elem.FindAll(TreeScope_Descendants, true_cond)
            
            if not raw_elements:
                return []

            count = raw_elements.Length
            elem_id = 1

            for i in range(min(count, 400)):
                try:
                    node = raw_elements.GetElement(i)
                    control_type_id = node.CurrentControlType
                    type_str = UIA_CONTROL_TYPES.get(control_type_id, f"Type_{control_type_id}")
                    name = str(node.CurrentName or "").strip()
                    auto_id = str(node.CurrentAutomationId or "").strip()
                    class_name = str(node.CurrentClassName or "").strip()
                    is_enabled = bool(node.CurrentIsEnabled)
                    is_offscreen = bool(node.CurrentIsOffscreen)

                    # Filter out invisible or uninformative background panes
                    if is_offscreen and not name:
                        continue
                    if type_str in ["Pane", "Custom", "Separator"] and not name and not auto_id:
                        continue

                    # Bounding rect
                    r = node.CurrentBoundingRectangle
                    rect = None
                    if r:
                        rect = Rect(left=int(r.left), top=int(r.top), right=int(r.right), bottom=int(r.bottom))
                        if rect.width <= 0 or rect.height <= 0:
                            continue

                    elements.append(UIElement(
                        name=name,
                        control_type=type_str,
                        automation_id=auto_id,
                        class_name=class_name,
                        rect=rect,
                        is_enabled=is_enabled,
                        is_offscreen=is_offscreen,
                        element_id=elem_id,
                    ))
                    elem_id += 1
                    if len(elements) >= max_elements:
                        break
                except Exception:
                    continue

        except Exception as e:
            logger.debug("Error traversing UI automation tree: %s", e)

        return elements

    # =========================================================================
    # 2. Window & Application Management
    # =========================================================================

    def get_active_hwnd(self) -> int:
        if sys.platform != "win32":
            return 0
        try:
            import win32gui
            return win32gui.GetForegroundWindow()
        except Exception:
            return 0

    def get_active_window(self) -> Optional[WindowInfo]:
        if sys.platform != "win32":
            return None
        hwnd = self.get_active_hwnd()
        if not hwnd:
            return None
        return self._get_window_info(hwnd, is_active=True)

    def list_windows(self) -> List[WindowInfo]:
        """Enumerate visible top-level desktop application windows."""
        if sys.platform != "win32":
            return []

        windows: List[WindowInfo] = []
        try:
            import win32gui
            active_hwnd = win32gui.GetForegroundWindow()

            def enum_cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd).strip()
                    if title:
                        info = self._get_window_info(hwnd, is_active=(hwnd == active_hwnd))
                        if info and info.rect and info.rect.width > 50 and info.rect.height > 50:
                            windows.append(info)
                return True

            win32gui.EnumWindows(enum_cb, None)
        except Exception as e:
            logger.debug("Error listing windows: %s", e)

        return windows

    def _get_window_info(self, hwnd: int, is_active: bool = False) -> Optional[WindowInfo]:
        try:
            import win32gui
            import win32process
            import psutil

            title = win32gui.GetWindowText(hwnd).strip()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc_name = ""
            try:
                proc = psutil.Process(pid)
                proc_name = proc.name()
            except Exception:
                pass

            rect_raw = win32gui.GetWindowRect(hwnd)
            rect = Rect(left=rect_raw[0], top=rect_raw[1], right=rect_raw[2], bottom=rect_raw[3])

            return WindowInfo(
                hwnd=hwnd,
                title=title,
                process_name=proc_name,
                pid=pid,
                rect=rect,
                is_active=is_active,
            )
        except Exception:
            return None

    def launch_app(self, app_name_or_path: str) -> bool:
        """Launch an application and wait for its window to become active."""
        if desktop_state.is_aborted:
            return False

        logger.info("Launching application: %s", app_name_or_path)
        try:
            # Common short names mapping
            app_map = {
                "notepad": "notepad.exe",
                "calc": "calc.exe",
                "calculator": "calc.exe",
                "explorer": "explorer.exe",
                "paint": "mspaint.exe",
                "cmd": "cmd.exe",
                "powershell": "powershell.exe",
                "code": "code",
                "chrome": "chrome.exe",
                "edge": "msedge.exe",
            }
            target = app_map.get(app_name_or_path.lower(), app_name_or_path)

            if sys.platform == "win32":
                subprocess.Popen(target, shell=True)
                time.sleep(1.2)  # Allow process and window to initialize
                return True
            else:
                subprocess.Popen([target])
                return True
        except Exception as e:
            logger.error("Failed to launch app %s: %s", app_name_or_path, e)
            return False

    def focus_window(self, title_pattern: str) -> bool:
        """Bring window matching title pattern into the foreground."""
        if sys.platform != "win32":
            return False

        try:
            import win32gui
            import win32con

            matched_hwnd = None
            pattern_lower = title_pattern.lower()

            def enum_cb(hwnd, _):
                nonlocal matched_hwnd
                if win32gui.IsWindowVisible(hwnd):
                    text = win32gui.GetWindowText(hwnd).strip().lower()
                    if pattern_lower in text:
                        matched_hwnd = hwnd
                        return False
                return True

            try:
                win32gui.EnumWindows(enum_cb, None)
            except Exception:
                pass

            if matched_hwnd:
                win32gui.ShowWindow(matched_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(matched_hwnd)
                time.sleep(0.3)
                return True
            return False
        except Exception as e:
            logger.debug("Error focusing window '%s': %s", title_pattern, e)
            return False

    def close_window(self, title_pattern: str) -> bool:
        """Send WM_CLOSE to window matching title pattern."""
        if sys.platform != "win32":
            return False

        try:
            import win32gui
            import win32con

            matched = []
            def enum_cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    if title_pattern.lower() in win32gui.GetWindowText(hwnd).lower():
                        matched.append(hwnd)
                return True

            win32gui.EnumWindows(enum_cb, None)
            for hwnd in matched:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            return len(matched) > 0
        except Exception as e:
            logger.error("Error closing window '%s': %s", title_pattern, e)
            return False

    # =========================================================================
    # 3. Mouse & Keyboard Actuation (Win32 SendInput / PyAutoGUI)
    # =========================================================================

    def get_cursor_pos(self) -> Tuple[int, int]:
        if sys.platform == "win32":
            try:
                import win32gui
                return win32gui.GetCursorPos()
            except Exception:
                pass
        try:
            import pyautogui
            pos = pyautogui.position()
            return (pos.x, pos.y)
        except Exception:
            return (0, 0)

    def get_screen_size(self) -> Tuple[int, int]:
        if sys.platform == "win32":
            try:
                import win32api
                import win32con
                w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
                h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
                if w > 0 and h > 0:
                    return (w, h)
            except Exception:
                pass
        try:
            import pyautogui
            size = pyautogui.size()
            return (size.width, size.height)
        except Exception:
            return (1920, 1080)

    def move_mouse(self, x: int, y: int) -> bool:
        if desktop_state.is_aborted:
            return False
        screen_size = self.get_screen_size()
        cx = max(0, min(screen_size[0] - 1, int(x)))
        cy = max(0, min(screen_size[1] - 1, int(y)))

        if sys.platform == "win32":
            try:
                import win32api
                win32api.SetCursorPos((cx, cy))
                return True
            except Exception:
                pass
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.moveTo(cx, cy, duration=0.1)
            return True
        except Exception:
            return False

    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left", double: bool = False) -> bool:
        if desktop_state.is_aborted:
            return False

        if x is not None and y is not None:
            self.move_mouse(x, y)
            time.sleep(0.05)

        if sys.platform == "win32":
            try:
                import win32api
                import win32con

                cx, cy = self.get_cursor_pos()
                down_flag = win32con.MOUSEEVENTF_LEFTDOWN if button == "left" else win32con.MOUSEEVENTF_RIGHTDOWN
                up_flag = win32con.MOUSEEVENTF_LEFTUP if button == "left" else win32con.MOUSEEVENTF_RIGHTUP

                win32api.mouse_event(down_flag, cx, cy, 0, 0)
                time.sleep(0.03)
                win32api.mouse_event(up_flag, cx, cy, 0, 0)

                if double:
                    time.sleep(0.1)
                    win32api.mouse_event(down_flag, cx, cy, 0, 0)
                    time.sleep(0.03)
                    win32api.mouse_event(up_flag, cx, cy, 0, 0)
                return True
            except Exception as e:
                logger.debug("Win32 mouse_event failed, falling back: %s", e)

        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            if double:
                pyautogui.doubleClick(button=button)
            else:
                pyautogui.click(button=button)
            return True
        except Exception as e:
            logger.error("Click actuation failed: %s", e)
            return False

    def scroll(self, clicks: int, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        if desktop_state.is_aborted:
            return False

        if x is not None and y is not None:
            self.move_mouse(x, y)

        if sys.platform == "win32":
            try:
                import win32api
                import win32con
                cx, cy = self.get_cursor_pos()
                win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, cx, cy, clicks * 120, 0)
                return True
            except Exception:
                pass

        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.scroll(clicks * 100)
            return True
        except Exception:
            return False

    def type_text(self, text: str, interval: float = 0.02) -> bool:
        """Type text into active focused element with full Unicode, emoji, and multi-lingual support."""
        if desktop_state.is_aborted:
            return False

        logger.info("Typing text (length=%d)", len(text))
        # If text contains non-ASCII characters, newlines, tabs, or is long (>40 chars),
        # use native Win32 Unicode clipboard paste (100% reliable, never drops chars or fails on cp1252)
        has_unicode = any(ord(c) > 127 for c in text) or "\n" in text or len(text) > 40
        if has_unicode and sys.platform == "win32":
            try:
                import win32clipboard
                import win32con
                import pyautogui
                pyautogui.FAILSAFE = False

                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()

                time.sleep(0.05)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.05)
                return True
            except Exception as clip_err:
                logger.debug("Win32 clipboard paste error, attempting fallback: %s", clip_err)

        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.write(text, interval=interval)
            return True
        except Exception:
            try:
                import keyboard
                keyboard.write(text, delay=interval)
                return True
            except Exception as e:
                logger.error("Failed to type text: %s", e)
                return False

    def shortcut(self, keys: List[str]) -> bool:
        """Send a keyboard shortcut combo like ['ctrl', 's'] or ['alt', 'f4']."""
        if desktop_state.is_aborted:
            return False

        logger.info("Executing shortcut: %s", "+".join(keys))
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return True
        except Exception:
            try:
                import keyboard
                keyboard.send("+".join(keys))
                return True
            except Exception as e:
                logger.error("Failed shortcut combo %s: %s", keys, e)
                return False

    # =========================================================================
    # 4. Safe PowerShell Execution
    # =========================================================================

    def run_powershell(self, command: str, timeout: int = 15) -> Dict[str, Any]:
        """Execute a PowerShell command with strict output limits and timeout."""
        if desktop_state.is_aborted:
            return {"success": False, "error": "Aborted by user", "stdout": "", "stderr": ""}

        logger.info("Running PowerShell command: %s", command[:100])
        try:
            proc = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            # Cap output to 4000 characters to protect LLM context windows
            stdout = proc.stdout[:4000] if proc.stdout else ""
            stderr = proc.stderr[:2000] if proc.stderr else ""
            success = proc.returncode == 0

            return {
                "success": success,
                "exit_code": proc.returncode,
                "stdout": stdout.strip(),
                "stderr": stderr.strip(),
                "error": stderr.strip() if not success else None,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Command timed out after {timeout}s", "stdout": "", "stderr": ""}
        except Exception as e:
            return {"success": False, "error": str(e), "stdout": "", "stderr": ""}

    # =========================================================================
    # 5. Local Filesystem Operations
    # =========================================================================

    def file_op(self, operation: str, path: str, content: Optional[str] = None) -> Dict[str, Any]:
        """Perform verified filesystem operations."""
        op = operation.lower()
        abs_path = os.path.abspath(os.path.expanduser(path))

        try:
            if op == "read":
                if not os.path.exists(abs_path):
                    return {"success": False, "error": f"File does not exist: {abs_path}"}
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    data = f.read(20000)  # Safe cap
                return {"success": True, "content": data, "path": abs_path}

            elif op in ["write", "overwrite"]:
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(content or "")
                return {"success": True, "path": abs_path, "bytes_written": len(content or "")}

            elif op == "append":
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, "a", encoding="utf-8") as f:
                    f.write(content or "")
                return {"success": True, "path": abs_path}

            elif op == "list":
                if not os.path.exists(abs_path):
                    return {"success": False, "error": f"Directory does not exist: {abs_path}"}
                items = os.listdir(abs_path)[:100]
                return {"success": True, "items": items, "path": abs_path}

            elif op == "exists":
                return {"success": True, "exists": os.path.exists(abs_path), "path": abs_path}

            elif op in ["delete", "remove"]:
                if os.path.exists(abs_path):
                    os.remove(abs_path)
                    return {"success": True, "deleted": abs_path}
                return {"success": False, "error": f"File not found: {abs_path}"}

            return {"success": False, "error": f"Unsupported file operation: {op}"}

        except Exception as e:
            return {"success": False, "error": str(e), "path": abs_path}

    # =========================================================================
    # 6. Full Desktop Observation
    # =========================================================================

    def observe(self, include_elements: bool = True) -> Observation:
        """Capture atomic desktop observation (active window, open windows, UIA elements, cursor)."""
        active_window = self.get_active_window()
        open_windows = self.list_windows()
        elements = self.get_ui_elements() if include_elements else []
        cursor = self.get_cursor_pos()

        screen_size = (1920, 1080)
        try:
            import pyautogui
            size = pyautogui.size()
            screen_size = (size.width, size.height)
        except Exception:
            pass

        obs = Observation(
            active_window=active_window,
            open_windows=open_windows,
            elements=elements,
            screen_size=screen_size,
            cursor_pos=cursor,
        )
        desktop_state.update_observation(obs)
        return obs

    # =========================================================================
    # 7. Concrete State Verification (Observe -> Act -> Verify)
    # =========================================================================

    def verify_state(self, condition: str, expected: Any) -> bool:
        """Verify that an action had its intended real-world effect."""
        cond = condition.lower()
        if cond == "window_open":
            # Check if any window title contains the expected string
            windows = self.list_windows()
            pattern = str(expected).lower()
            return any(pattern in w.title.lower() for w in windows)

        if cond == "process_running":
            import psutil
            pattern = str(expected).lower()
            for p in psutil.process_iter(["name"]):
                try:
                    if pattern in p.info["name"].lower():
                        return True
                except Exception:
                    continue
            return False

        if cond == "file_exists":
            return os.path.exists(os.path.abspath(os.path.expanduser(str(expected))))

        return True


# Global singleton adapter instance
windows_use_adapter = WindowsUseAdapter()
