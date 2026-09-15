import sys
import unittest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

repo_dir = Path(__file__).resolve().parent.parent / "octopus_ai"
parent_dir = repo_dir.parent
for p in [str(parent_dir), str(repo_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from octopus_ai.agent.subagents.desktop_agent import DesktopAgent, desktop_agent_instance, WINDOWS_APPS


class TestDesktopAgent(unittest.TestCase):
    def setUp(self):
        self.agent = DesktopAgent()

    def test_windows_apps_registry(self):
        self.assertIn("calculator", WINDOWS_APPS)
        self.assertIn("notepad", WINDOWS_APPS)
        self.assertIn("paint", WINDOWS_APPS)
        self.assertIn("taskmgr", WINDOWS_APPS)
        self.assertIn("explorer", WINDOWS_APPS)
        self.assertEqual(WINDOWS_APPS["calculator"], "calc.exe")
        self.assertEqual(WINDOWS_APPS["notepad"], "notepad.exe")

    def test_generate_python_assignment(self):
        content = self.agent.generate_python_assignment(topic="Test Data Structures")
        self.assertIn("PYTHON PROGRAMMING ASSIGNMENT", content)
        self.assertIn("Topic: Test Data Structures", content)
        self.assertIn("def word_frequency", content)
        self.assertIn("def is_palindrome", content)
        self.assertIn("def merge_sorted_lists", content)
        self.assertIn("def fibonacci", content)
        self.assertIn("__main__", content)

        compiled = compile(content, "<test_assignment>", "exec")
        self.assertIsNotNone(compiled)

    @patch("subprocess.Popen")
    def test_launch_application_calc(self, mock_popen):
        res = self.agent.launch_application("calculator")
        self.assertTrue(res["success"])
        self.assertEqual(res["action"], "launch_app")
        mock_popen.assert_called()

    @patch("subprocess.Popen")
    def test_launch_application_notepad(self, mock_popen):
        res = self.agent.launch_application("notepad")
        self.assertTrue(res["success"])
        self.assertEqual(res["action"], "launch_app")
        mock_popen.assert_called()

    @patch("subprocess.Popen")
    def test_execute_task_calculator(self, mock_popen):
        res = asyncio.run(self.agent.execute_task("open calculator"))
        self.assertTrue(res["success"])
        self.assertEqual(res["action"], "launch_app")
        self.assertIn("Calculator", res["message"])

    @patch("subprocess.Popen")
    def test_execute_task_notepad_assignment(self, mock_popen):
        res = asyncio.run(self.agent.execute_task("open new notepad and write the Python Assignment there"))
        self.assertTrue(res["success"])
        self.assertEqual(res["action"], "open_notepad_with_content")
        self.assertIn("python_assignment.py", res["filename"])
        self.assertIn("Notepad", res["message"])
        if res.get("path") and Path(res["path"]).exists():
            Path(res["path"]).unlink()

    def test_find_local_files(self):
        files = self.agent.find_local_files(query="", extensions=[".py"], max_results=5)
        self.assertIsInstance(files, list)
        self.assertGreater(len(files), 0)

    def test_expanded_windows_apps_registry(self):
        self.assertIn("chrome", WINDOWS_APPS)
        self.assertIn("edge", WINDOWS_APPS)
        self.assertIn("camera", WINDOWS_APPS)
        self.assertIn("vscode", WINDOWS_APPS)
        self.assertIn("word", WINDOWS_APPS)
        self.assertIn("excel", WINDOWS_APPS)

    def test_get_system_info(self):
        res = self.agent.get_system_info()
        self.assertTrue(res["success"])
        self.assertIn("cpu_percent", res)
        self.assertIn("ram_percent", res)
        self.assertIn("disk_percent", res)
        self.assertIn("System Status", res["message"])

    @patch("PIL.ImageGrab.grab")
    def test_take_screenshot(self, mock_grab):
        mock_img = MagicMock()
        mock_grab.return_value = mock_img
        res = self.agent.take_screenshot("test_screen.png")
        self.assertTrue(res["success"])
        self.assertEqual(res["action"], "screenshot")
        self.assertIn("test_screen.png", res["filename"])
        mock_img.save.assert_called()

    @patch("PIL.ImageGrab.grab")
    def test_execute_task_screenshot(self, mock_grab):
        mock_img = MagicMock()
        mock_grab.return_value = mock_img
        res = asyncio.run(self.agent.execute_task("take a screenshot"))
        self.assertTrue(res["success"])
        self.assertEqual(res["action"], "screenshot")

    def test_execute_task_system_info(self):
        res = asyncio.run(self.agent.execute_task("show system info and battery"))
        self.assertTrue(res["success"])
        self.assertEqual(res["action"], "system_info")

    @patch("ctypes.windll.user32.LockWorkStation", create=True)
    def test_execute_task_lock_workstation(self, mock_lock):
        res = asyncio.run(self.agent.execute_task("lock computer"))
        self.assertTrue(res["success"])
        self.assertEqual(res["action"], "lock_workstation")


if __name__ == "__main__":
    unittest.main()

