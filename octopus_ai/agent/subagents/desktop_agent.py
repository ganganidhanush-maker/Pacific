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
            os.startfile(target_path)
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

    async def execute_task(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """General task entrypoint for Desktop Agent."""
        params = params or {}
        cmd_lower = command.lower()

        if "find" in cmd_lower or "search" in cmd_lower:
            exts = params.get("extensions")
            if not exts:
                # auto-detect extensions in command
                detected = []
                for ext in [".pdf", ".py", ".pptx", ".docx", ".txt", ".png", ".jpg"]:
                    if ext.replace(".", "") in cmd_lower or ext in cmd_lower:
                        detected.append(ext)
                exts = detected or None
            query = params.get("query", "")
            files = self.find_local_files(query=query, extensions=exts)
            return {
                "success": True,
                "action": "find_files",
                "count": len(files),
                "files": files,
                "summary": f"Found {len(files)} matching local files on your computer."
            }

        elif "organize" in cmd_lower or "move" in cmd_lower:
            folder = params.get("target_folder", "Organized_Materials")
            fps = params.get("file_paths", [])
            return self.organize_files(fps, folder)

        elif "open" in cmd_lower:
            fp = params.get("path") or params.get("file_path")
            if fp:
                return self.open_file(fp)
            return {"success": False, "error": "No file path provided to open"}

        elif "create" in cmd_lower or "touch" in cmd_lower:
            fp = params.get("path", "script.py")
            content = params.get("content", "# Created by Octopus AI Desktop Agent\n")
            return self.touch_file(fp, content)

        return {"success": False, "message": f"Unrecognized desktop command: {command}"}


desktop_agent_instance = DesktopAgent()
