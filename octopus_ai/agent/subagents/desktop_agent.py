"""
Desktop Agent for Octopus AI
Handles all local OS and filesystem operations:
- Finding files on Desktop, Documents, Downloads, and Workspace
- Organizing, moving, touching, and reading local files
- Opening files in default Windows applications
- Executing local Python scripts safely
"""

import os
import sys
import glob
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger("DesktopAgent")

# Registry of standard Windows desktop applications
WINDOWS_APPS = {
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "taskmgr": "taskmgr.exe",
    "task manager": "taskmgr.exe",
    "taskmanager": "taskmgr.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "powershell.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "files": "explorer.exe",
    "settings": "ms-settings:",
    "control panel": "control.exe",
    "snipping tool": "snippingtool.exe",
    "wordpad": "write.exe"
}


class DesktopAgent:
    def __init__(self):
        self.user_profile = os.environ.get("USERPROFILE", "")
        self.standard_search_dirs = [
            os.path.join(self.user_profile, "Desktop"),
            os.path.join(self.user_profile, "Documents"),
            os.path.join(self.user_profile, "Downloads"),
            os.path.join(self.user_profile, "OneDrive", "Documents"),
            os.path.join(self.user_profile, "OneDrive", "Desktop"),
            str(Path(__file__).resolve().parent.parent.parent)
        ]

    def find_local_files(
        self,
        query: str = "",
        extensions: Optional[List[str]] = None,
        max_results: int = 25
    ) -> List[Dict[str, Any]]:
        """
        Search user's local directories for matching files.
        Example: query='lecture' or extensions=['.pdf', '.py']
        """
        results = []
        clean_exts = [e.lower() if e.startswith(".") else f".{e.lower()}" for e in (extensions or [])]
        query_lower = query.lower().strip()

        seen_paths = set()

        for search_dir in self.standard_search_dirs:
            if not os.path.exists(search_dir):
                continue

            try:
                # Walk with depth limit of 3 for fast response
                for root, dirs, files in os.walk(search_dir):
                    rel = os.path.relpath(root, search_dir)
                    depth = len(rel.split(os.sep)) if rel != "." else 0
                    if depth > 3:
                        dirs.clear()  # Don't recurse deeper
                        continue

                    # Filter out hidden or cache directories
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["node_modules", "__pycache__", "venv", ".venv"]]

                    for file in files:
                        filepath = os.path.join(root, file)
                        if filepath in seen_paths:
                            continue

                        name_lower = file.lower()
                        ext = os.path.splitext(name_lower)[1]

                        # Check extension filter
                        if clean_exts and ext not in clean_exts:
                            continue

                        # Check query substring
                        if query_lower and (query_lower not in name_lower):
                            continue

                        try:
                            stat = os.stat(filepath)
                            size_kb = round(stat.st_size / 1024, 1)
                            seen_paths.add(filepath)
                            results.append({
                                "name": file,
                                "path": filepath,
                                "size_kb": size_kb,
                                "extension": ext,
                                "directory": root
                            })
                            if len(results) >= max_results:
                                return results
                        except Exception:
                            pass
            except Exception as walk_err:
                logger.debug(f"Search warning in {search_dir}: {walk_err}")

        return results

    def touch_file(self, target_path: str, content: str = "") -> Dict[str, Any]:
        """Create a new file or write initial template code."""
        p = Path(target_path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "path": str(p), "message": f"Created file {p.name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_file(self, src: str, dst_folder: str) -> Dict[str, Any]:
        """Move a file to a designated folder."""
        try:
            src_p = Path(src)
            if not src_p.exists():
                return {"success": False, "error": f"Source file {src} does not exist"}

            dst_p = Path(dst_folder)
            dst_p.mkdir(parents=True, exist_ok=True)
            target = dst_p / src_p.name

            shutil.move(str(src_p), str(target))
            return {"success": True, "new_path": str(target), "message": f"Moved {src_p.name} to {dst_p.name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def organize_files(self, file_paths: List[str], target_folder_name: str) -> Dict[str, Any]:
        """Organize a list of files into a single project folder on the Desktop or Documents."""
        dest_dir = os.path.join(self.user_profile, "Desktop", target_folder_name)
        os.makedirs(dest_dir, exist_ok=True)
        moved = []
        errors = []

        for fp in file_paths:
            res = self.move_file(fp, dest_dir)
            if res.get("success"):
                moved.append(res.get("new_path"))
            else:
                errors.append(res.get("error"))

        return {
            "success": len(moved) > 0,
            "target_directory": dest_dir,
            "moved_count": len(moved),
            "moved_files": moved,
            "errors": errors
        }

    def open_file(self, target_path: str) -> Dict[str, Any]:
        """Open a file in its native Windows default viewer."""
        try:
            if not os.path.exists(target_path):
                return {"success": False, "error": f"File {target_path} not found"}
            if hasattr(os, "startfile"):
                os.startfile(target_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target_path])
            else:
                subprocess.Popen(["xdg-open", target_path])
            return {"success": True, "message": f"Opened {os.path.basename(target_path)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def execute_python_script(self, script_path: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run a local python script and capture its output."""
        try:
            if not os.path.exists(script_path):
                return {"success": False, "error": f"Script {script_path} does not exist"}

            python_exe = sys.executable
            cmd = [python_exe, script_path] + (args or [])
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return {
                "success": res.returncode == 0,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "returncode": res.returncode
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # APPLICATION LAUNCHING & WINDOWS CONTROL
    # =========================================================================
    def launch_application(self, app_key_or_name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Launch a native desktop application (e.g. Calculator, Notepad, Paint, Explorer).
        Uses non-blocking subprocess spawning.
        """
        key = app_key_or_name.lower().strip()
        target = WINDOWS_APPS.get(key, app_key_or_name)

        try:
            if sys.platform == "win32":
                if target.startswith("ms-settings:"):
                    subprocess.Popen(f"start {target}", shell=True)
                else:
                    cmd = [target] + (args or [])
                    subprocess.Popen(cmd, shell=True)
            elif sys.platform == "darwin":
                mac_app_map = {
                    "calculator": "Calculator",
                    "notepad": "TextEdit",
                    "paint": "Preview",
                    "terminal": "Terminal"
                }
                app_name = mac_app_map.get(key, "TextEdit")
                subprocess.Popen(["open", "-a", app_name] + (args or []))
            else:
                linux_app_map = {
                    "calculator": "gnome-calculator",
                    "notepad": "gedit",
                    "paint": "drawing",
                    "terminal": "gnome-terminal"
                }
                bin_name = linux_app_map.get(key, "nano")
                subprocess.Popen([bin_name] + (args or []))

            display_name = app_key_or_name.replace(".exe", "").capitalize()
            return {
                "success": True,
                "action": "launch_app",
                "app": target,
                "message": f"Opened {display_name} on your desktop."
            }
        except Exception as e:
            logger.error(f"Failed to launch application '{app_key_or_name}': {e}")
            return {
                "success": False,
                "action": "launch_app",
                "error": str(e),
                "message": f"Could not open {app_key_or_name}: {e}"
            }

    def generate_python_assignment(self, topic: str = "Python Core & Data Structures") -> str:
        """
        Generate a structured, educational Python assignment file complete with
        instructions, problem statements, starter templates, and unit test assertions.
        """
        return f'''"""
================================================================================
PYTHON PROGRAMMING ASSIGNMENT
Topic: {topic}
Generated by: Octopus AI Desktop Agent
Student Name: __________________________     Date: ________________________
================================================================================

INSTRUCTIONS:
1. Complete each of the problem functions below.
2. Ensure your code handles edge cases (empty inputs, negative numbers, etc.).
3. Run this script in Python to verify your answers against the test assertions.
================================================================================
"""

from typing import List, Dict, Any, Optional


# ------------------------------------------------------------------------------
# PROBLEM 1: Word Frequency Counter
# ------------------------------------------------------------------------------
def word_frequency(text: str) -> Dict[str, int]:
    """
    Given a paragraph of text, return a dictionary mapping each lowercased word
    to the number of times it appears in the text. Strip out common punctuation
    marks (.,!?:;).
    
    Example:
        word_frequency("Hello world! Hello Python.")
        -> {{'hello': 2, 'world': 1, 'python': 1}}
    """
    clean_text = ""
    for ch in text.lower():
        if ch.isalnum() or ch.isspace():
            clean_text += ch
    
    counts = {{}}
    for word in clean_text.split():
        counts[word] = counts.get(word, 0) + 1
    return counts


# ------------------------------------------------------------------------------
# PROBLEM 2: Valid Palindrome (Ignoring Non-Alphanumerics)
# ------------------------------------------------------------------------------
def is_palindrome(s: str) -> bool:
    """
    Return True if the input string is a palindrome considering only alphanumeric
    characters and ignoring cases. Otherwise, return False.
    
    Example:
        is_palindrome("A man, a plan, a canal: Panama") -> True
        is_palindrome("race a car") -> False
    """
    filtered = [ch.lower() for ch in s if ch.isalnum()]
    return filtered == filtered[::-1]


# ------------------------------------------------------------------------------
# PROBLEM 3: Merge Two Sorted Lists
# ------------------------------------------------------------------------------
def merge_sorted_lists(list1: List[int], list2: List[int]) -> List[int]:
    """
    Merge two sorted integer lists into one continuous sorted list in O(n + m) time.
    Do NOT simply concatenate and call .sort().
    
    Example:
        merge_sorted_lists([1, 3, 5], [2, 4, 6]) -> [1, 2, 3, 4, 5, 6]
    """
    result = []
    i, j = 0, 0
    while i < len(list1) and j < len(list2):
        if list1[i] <= list2[j]:
            result.append(list1[i])
            i += 1
        else:
            result.append(list2[j])
            j += 1
    result.extend(list1[i:])
    result.extend(list2[j:])
    return result


# ------------------------------------------------------------------------------
# PROBLEM 4: Fibonacci Sequence Generator (Memoized / Iterative)
# ------------------------------------------------------------------------------
def fibonacci(n: int) -> int:
    """
    Return the n-th Fibonacci number (0-indexed).
    fib(0) = 0, fib(1) = 1, fib(2) = 1, fib(3) = 2, ...
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n in (0, 1):
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


# ==============================================================================
# SELF-TESTING & VERIFICATION SUITE
# Run this file with `python <filename>` to grade your assignment!
# ==============================================================================
if __name__ == "__main__":
    print("Running assignment verification tests...")
    
    # Test Problem 1
    freq = word_frequency("Python is great, and Python is easy.")
    assert freq.get("python") == 2, f"Expected 2 python, got {{freq.get('python')}}"
    print("  ✓ Problem 1 (Word Frequency): PASS")
    
    # Test Problem 2
    assert is_palindrome("A man, a plan, a canal: Panama") is True
    assert is_palindrome("hello world") is False
    print("  ✓ Problem 2 (Palindrome): PASS")
    
    # Test Problem 3
    merged = merge_sorted_lists([1, 4, 7], [2, 3, 8, 9])
    assert merged == [1, 2, 3, 4, 7, 8, 9], f"Unexpected merge: {{merged}}"
    print("  ✓ Problem 3 (Merge Sorted): PASS")
    
    # Test Problem 4
    assert fibonacci(10) == 55, f"Expected fib(10) == 55, got {{fibonacci(10)}}"
    print("  ✓ Problem 4 (Fibonacci): PASS")
    
    print("\\n🎉 ALL ASSIGNMENT TESTS PASSED SUCCESSFULLY! Excellent work!")
'''

    def create_and_open_notepad(self, content: str = "", filename: str = "python_assignment.py") -> Dict[str, Any]:
        """
        Create a file on the Desktop/Documents and immediately open it in Windows Notepad.
        """
        target_dir = os.path.join(self.user_profile, "Desktop")
        if not os.path.exists(target_dir):
            target_dir = os.path.join(self.user_profile, "Documents")
        if not os.path.exists(target_dir):
            target_dir = str(Path(__file__).resolve().parent.parent.parent)

        file_path = os.path.join(target_dir, filename)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Launch Notepad with this file
            if sys.platform == "win32":
                subprocess.Popen(["notepad.exe", file_path], shell=True)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "TextEdit", file_path])
            else:
                subprocess.Popen(["gedit", file_path])

            return {
                "success": True,
                "action": "open_notepad_with_content",
                "path": file_path,
                "filename": filename,
                "message": f"Created '{filename}' and opened it in Notepad."
            }
        except Exception as e:
            logger.error(f"Failed to create and open notepad for {file_path}: {e}")
            return {
                "success": False,
                "action": "open_notepad_with_content",
                "error": str(e),
                "message": f"Could not create and open file in Notepad: {e}"
            }

    # =========================================================================
    # UNIFIED TASK ENTRYPOINT
    # =========================================================================
    async def execute_task(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """General task entrypoint for Desktop Agent with natural language interpretation."""
        params = params or {}
        cmd_lower = command.lower().strip()

        # 1. Notepad + Assignment / Content Creation
        if "notepad" in cmd_lower:
            if any(w in cmd_lower for w in ["assignment", "python", "code", "write"]):
                topic = "Python Fundamentals & Data Structures"
                assignment = self.generate_python_assignment(topic=topic)
                return self.create_and_open_notepad(content=assignment, filename="python_assignment.py")
            else:
                return self.launch_application("notepad")

        # 2. Calculator
        if any(w in cmd_lower for w in ["calc", "calculator"]):
            return self.launch_application("calculator")

        # 3. Paint / Drawing
        if any(w in cmd_lower for w in ["paint", "mspaint"]):
            return self.launch_application("paint")

        # 4. Task Manager
        if any(w in cmd_lower for w in ["task manager", "taskmgr"]):
            return self.launch_application("taskmgr")

        # 5. Terminal / Command Prompt / PowerShell
        if any(w in cmd_lower for w in ["cmd", "command prompt"]):
            return self.launch_application("cmd")
        if any(w in cmd_lower for w in ["powershell", "terminal"]):
            return self.launch_application("powershell")

        # 6. File Explorer / My Computer
        if any(w in cmd_lower for w in ["explorer", "file explorer", "this pc", "my computer"]):
            return self.launch_application("explorer")

        # 7. Windows Settings
        if "settings" in cmd_lower and any(w in cmd_lower for w in ["open", "launch", "windows"]):
            return self.launch_application("settings")

        # 8. Find / Search Local Files
        if "find" in cmd_lower or "search" in cmd_lower:
            exts = params.get("extensions")
            if not exts:
                detected = []
                for ext in [".pdf", ".py", ".pptx", ".docx", ".txt", ".png", ".jpg"]:
                    if ext.replace(".", "") in cmd_lower or ext in cmd_lower:
                        detected.append(ext)
                exts = detected or None
            query = params.get("query", "")
            if not query:
                q_clean = cmd_lower
                for kw in ["find", "search", "for", "files", "file", "all", "my"]:
                    q_clean = q_clean.replace(kw, "")
                query = q_clean.strip()
            files = self.find_local_files(query=query, extensions=exts)
            return {
                "success": True,
                "action": "find_files",
                "count": len(files),
                "files": files,
                "summary": f"Found {len(files)} matching local files on your computer."
            }

        # 9. Organize / Move Files
        if "organize" in cmd_lower or "move" in cmd_lower:
            folder = params.get("target_folder", "Organized_Materials")
            fps = params.get("file_paths", [])
            return self.organize_files(fps, folder)

        # 10. Open specific file or application
        if "open" in cmd_lower or "launch" in cmd_lower:
            fp = params.get("path") or params.get("file_path")
            if fp and os.path.exists(fp):
                return self.open_file(fp)

            for app_key in WINDOWS_APPS:
                if app_key in cmd_lower:
                    return self.launch_application(app_key)

            search_query = cmd_lower.replace("open", "").replace("launch", "").strip()
            matches = self.find_local_files(query=search_query, max_results=1)
            if matches:
                return self.open_file(matches[0]["path"])

            return {"success": False, "error": f"Could not find an application or file matching '{command}'"}

        # 11. Create / Touch File
        if "create" in cmd_lower or "touch" in cmd_lower:
            fp = params.get("path", "script.py")
            content = params.get("content", "# Created by Octopus AI Desktop Agent\n")
            return self.touch_file(fp, content)

        # 12. Run Python Script
        if "run" in cmd_lower and ".py" in cmd_lower:
            words = command.split()
            for w in words:
                if w.endswith(".py") and os.path.exists(w):
                    return self.execute_python_script(w)

        return {"success": False, "message": f"Unrecognized desktop command: {command}"}


desktop_agent_instance = DesktopAgent()
