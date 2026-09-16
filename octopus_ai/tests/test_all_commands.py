"""
Pacific / Octopus AI — Comprehensive All-Command Verification Script
Verifies every tool, orchestrator command, and API handler in the platform.
"""

import os
import sys
import asyncio
import unittest
from pathlib import Path

# Setup paths
this_dir = Path(__file__).resolve().parent.parent
parent_dir = this_dir.parent
for p in [str(this_dir), str(parent_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Guarantee package alias
if "octopus_ai" not in sys.modules:
    import types
    mod = types.ModuleType("octopus_ai")
    mod.__path__ = [str(this_dir)]
    sys.modules["octopus_ai"] = mod

from computer_use import (
    computer_agent_instance, computer_router,
    windows_use_adapter, clacky_adapter,
    policy_engine, watchdog, desktop_state,
    ComputerAction
)
from octopus_ai.agent.orchestrator import master_orchestrator_instance
from server.app import classify_intent, AVAILABLE_AGENTS


class TestAllPlatformCommands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        watchdog.reset()

    # -------------------------------------------------------------------------
    # 1. Computer Use Adapter & Router Commands
    # -------------------------------------------------------------------------
    def test_cmd_observe(self):
        """Test 'observe' command."""
        res = computer_router.execute(ComputerAction(tool="observe", params={}))
        self.assertTrue(res.success)
        self.assertIn("screen_size", res.output)

    def test_cmd_read_tree(self):
        """Test 'read_tree' UI Automation command."""
        res = computer_router.execute(ComputerAction(tool="read_tree", params={"max_elements": 10}))
        self.assertTrue(res.success)
        self.assertIsInstance(res.output, list)

    def test_cmd_list_windows(self):
        """Test 'list_windows' command."""
        res = computer_router.execute(ComputerAction(tool="list_windows", params={}))
        self.assertTrue(res.success)
        self.assertIsInstance(res.output, list)

    def test_cmd_powershell(self):
        """Test 'powershell' command."""
        res = computer_router.execute(ComputerAction(
            tool="powershell",
            params={"command": "Write-Output 'PACIFIC_CMD_TEST_OK'"}
        ))
        self.assertTrue(res.success)
        self.assertIn("PACIFIC_CMD_TEST_OK", res.output)

    def test_cmd_file_operation(self):
        """Test 'file_operation' command."""
        test_p = os.path.join(os.environ.get("TEMP", "."), "pacific_cmd_test.txt")
        # Write
        w_res = computer_router.execute(ComputerAction(
            tool="file_operation",
            params={"operation": "write", "path": test_p, "content": "CMD_VERIFY"}
        ))
        self.assertTrue(w_res.success)

        # Read
        r_res = computer_router.execute(ComputerAction(
            tool="file_operation",
            params={"operation": "read", "path": test_p}
        ))
        self.assertTrue(r_res.success)
        self.assertEqual(r_res.output, "CMD_VERIFY")

        # Cleanup
        if os.path.exists(test_p):
            os.remove(test_p)

    def test_cmd_point_to(self):
        """Test Clacky 'point_to' command."""
        res = computer_router.execute(ComputerAction(
            tool="point_to",
            params={"x": 500, "y": 400, "label": "Test Marker"}
        ))
        self.assertTrue(res.success)

    def test_cmd_routines(self):
        """Test Clacky routine recording, retrieval, and replay."""
        # Start
        res1 = computer_router.execute(ComputerAction(
            tool="start_routine_recording",
            params={"name": "test_e2e_routine", "description": "Verification routine"}
        ))
        self.assertTrue(res1.success)

        # Step
        clacky_adapter.record_step("point_to", {"x": 200, "y": 200}, "Point at coordinate")

        # Stop
        res2 = computer_router.execute(ComputerAction(
            tool="stop_routine_recording",
            params={}
        ))
        self.assertTrue(res2.success)

        # Run routine
        res3 = computer_router.execute(ComputerAction(
            tool="run_routine",
            params={"name": "test_e2e_routine"}
        ))
        self.assertTrue(res3.success)

    def test_cmd_emergency_stop_and_reset(self):
        """Test emergency abort and reset commands."""
        watchdog.trigger_abort("E2E Test")
        self.assertTrue(desktop_state.is_aborted)

        # Confirm actions are blocked
        blocked_res = computer_router.execute(ComputerAction(tool="observe", params={}))
        self.assertFalse(blocked_res.success)

        # Reset
        watchdog.reset()
        self.assertFalse(desktop_state.is_aborted)

    # -------------------------------------------------------------------------
    # 2. MasterOrchestrator Intent Routing Commands
    # -------------------------------------------------------------------------
    def test_orchestrator_intents(self):
        """Test MasterOrchestrator decomposition across all agent intents."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # 1. Computer intent
            plan1 = loop.run_until_complete(
                master_orchestrator_instance.optimize_and_decompose("Open Notepad and write lecture notes")
            )
            self.assertTrue(plan1.get("requires_computer"))

            # 2. Web / WhatsApp intent
            plan2 = loop.run_until_complete(
                master_orchestrator_instance.optimize_and_decompose("Send WhatsApp broadcast to parents group about PTM")
            )
            self.assertTrue(plan2.get("requires_web"))

            # 3. Research intent
            plan3 = loop.run_until_complete(
                master_orchestrator_instance.optimize_and_decompose("Create a research presentation outline on quantum computing")
            )
            self.assertTrue(plan3.get("requires_research"))
        finally:
            loop.close()

    # -------------------------------------------------------------------------
    # 3. UI Classifier & Agent Commands
    # -------------------------------------------------------------------------
    def test_ui_intent_classifier(self):
        """Test slash commands and intent classification."""
        self.assertEqual(classify_intent("/computer"), "computer")
        self.assertEqual(classify_intent("/web"), "web")
        self.assertEqual(classify_intent("/desktop"), "desktop")
        self.assertEqual(classify_intent("/research"), "research")
        self.assertEqual(classify_intent("/chat"), "chatbot")
        self.assertEqual(classify_intent("/main"), "main")

        # Natural language classifications
        self.assertEqual(classify_intent("launch calculator app"), "desktop")
        self.assertEqual(classify_intent("send whatsapp message to mom"), "web")


if __name__ == "__main__":
    unittest.main()
