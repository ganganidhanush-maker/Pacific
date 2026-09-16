"""
Pacific / Octopus AI — Computer Use Automated Verification Suite
Tests:
1. Safety Policy Engine (SAFE, CONFIRM, HIGH_RISK rejection)
2. Emergency Watchdog (Abort & Reset)
3. Windows-Use Adapter (Observation, UIA, PowerShell, Filesystem)
4. Clacky Adapter (Coordinate Normalization, Pointing Events, Routines)
5. ComputerUseRouter (Dispatching, verification)
6. MasterOrchestrator Integration (Decomposition, computer routing)
"""

import os
import sys
import asyncio
import tempfile
import unittest
from pathlib import Path

# Ensure package roots are on sys.path
this_dir = Path(__file__).resolve().parent.parent
parent_dir = this_dir.parent
for p in [str(this_dir), str(parent_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Setup octopus_ai module alias if needed
if "octopus_ai" not in sys.modules:
    import types
    mod = types.ModuleType("octopus_ai")
    mod.__path__ = [str(this_dir)]
    sys.modules["octopus_ai"] = mod

from computer_use import (
    computer_agent_instance, computer_router,
    policy_engine, SafetyLevel, ExecutionMode,
    desktop_state, watchdog,
    windows_use_adapter, clacky_adapter,
    ComputerAction, ComputerEventType, event_bus
)
from octopus_ai.agent.orchestrator import master_orchestrator_instance


class TestComputerUsePolicy(unittest.TestCase):
    def setUp(self):
        policy_engine.set_mode(ExecutionMode.BALANCED)

    def test_safe_read_action(self):
        action = ComputerAction(tool="observe", params={})
        decision = policy_engine.evaluate(action)
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.requires_confirmation)
        self.assertEqual(decision.safety_level, SafetyLevel.SAFE)

    def test_safe_ui_action(self):
        action = ComputerAction(tool="click", params={"x": 100, "y": 100})
        decision = policy_engine.evaluate(action)
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.requires_confirmation)
        self.assertEqual(decision.safety_level, SafetyLevel.SAFE)

    def test_high_risk_command_blocked(self):
        dangerous_commands = [
            "rmdir /s /q C:\\Windows",
            "format D: /fs:NTFS",
            "reg delete HKLM\\Software\\Test",
            "Remove-Item -Recurse C:\\",
        ]
        for cmd in dangerous_commands:
            action = ComputerAction(tool="powershell", params={"command": cmd})
            decision = policy_engine.evaluate(action)
            self.assertFalse(decision.allowed, f"Dangerous command '{cmd}' should be blocked")
            self.assertEqual(decision.safety_level, SafetyLevel.HIGH_RISK)

    def test_confirm_on_file_deletion(self):
        action = ComputerAction(tool="file_operation", params={"operation": "delete", "path": "test.txt"})
        decision = policy_engine.evaluate(action)
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.requires_confirmation)
        self.assertEqual(decision.safety_level, SafetyLevel.CONFIRM)


class TestEmergencyWatchdog(unittest.TestCase):
    def setUp(self):
        watchdog.reset()

    def test_abort_and_reset(self):
        self.assertFalse(desktop_state.is_aborted)
        watchdog.trigger_abort("Test Abort")
        self.assertTrue(desktop_state.is_aborted)

        # Actions should be blocked while aborted
        action = ComputerAction(tool="observe", params={})
        res = computer_router.execute(action)
        self.assertFalse(res.success)
        self.assertIn("emergency stop", res.error.lower())

        # Reset should restore execution
        watchdog.reset()
        self.assertFalse(desktop_state.is_aborted)


class TestWindowsUseAdapter(unittest.TestCase):
    def test_observe_desktop(self):
        obs = windows_use_adapter.observe(include_elements=False)
        self.assertIsNotNone(obs)
        self.assertGreater(obs.screen_size[0], 0)
        self.assertGreater(obs.screen_size[1], 0)
        self.assertIsInstance(obs.open_windows, list)

    def test_powershell_execution(self):
        res = windows_use_adapter.run_powershell("Write-Output 'PACIFIC_WIN_USE_OK'")
        self.assertTrue(res["success"])
        self.assertIn("PACIFIC_WIN_USE_OK", res["stdout"])

    def test_filesystem_operations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test_doc.txt")

            # 1. Write
            w_res = windows_use_adapter.file_op("write", test_file, content="Hello Pacific!")
            self.assertTrue(w_res["success"])

            # 2. Exists
            e_res = windows_use_adapter.file_op("exists", test_file)
            self.assertTrue(e_res["success"])
            self.assertTrue(e_res["exists"])

            # 3. Read
            r_res = windows_use_adapter.file_op("read", test_file)
            self.assertTrue(r_res["success"])
            self.assertEqual(r_res["content"], "Hello Pacific!")

            # 4. Delete
            d_res = windows_use_adapter.file_op("delete", test_file)
            self.assertTrue(d_res["success"])
            self.assertFalse(os.path.exists(test_file))


class TestClackyAdapter(unittest.TestCase):
    def test_coordinate_normalization(self):
        # 0.5 normalized should map to half screen resolution
        px, py = clacky_adapter.normalize_coords(0.5, 0.5)
        self.assertGreater(px, 0)
        self.assertGreater(py, 0)

        nx, ny = clacky_adapter.denormalize_coords(px, py)
        self.assertAlmostEqual(nx, 0.5, delta=0.05)
        self.assertAlmostEqual(ny, 0.5, delta=0.05)

    def test_visual_pointing_event(self):
        received_events = []

        def on_event(evt):
            if evt.event_type == ComputerEventType.POINTING_EVENT:
                received_events.append(evt)

        event_bus.subscribe(ComputerEventType.POINTING_EVENT, on_event)
        try:
            res = clacky_adapter.point_to(500, 400, label="Test Target")
            self.assertTrue(res["success"])
            self.assertGreater(len(received_events), 0)
            self.assertEqual(received_events[-1].data["label"], "Test Target")
        finally:
            event_bus.unsubscribe(ComputerEventType.POINTING_EVENT, on_event)

    def test_routine_learning(self):
        routine_name = "test_routine_1"
        clacky_adapter.start_recording(routine_name, description="Test routine")
        clacky_adapter.record_step("move_mouse", {"x": 100, "y": 100}, "Move cursor")
        routine = clacky_adapter.stop_recording()
        self.assertIsNotNone(routine)
        self.assertEqual(routine.name, routine_name)
        self.assertEqual(len(routine.steps), 1)


class TestMasterOrchestratorIntegration(unittest.TestCase):
    def test_orchestrator_routes_computer_task(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Check prompt decomposition with a computer-use prompt
            prompt = "Open Notepad and type my study notes"
            plan = loop.run_until_complete(master_orchestrator_instance.optimize_and_decompose(prompt))
            self.assertTrue(plan.get("requires_computer"), f"Plan did not detect requires_computer: {plan}")
            self.assertIn("Notepad", plan.get("computer_tasks", [""])[0])
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
