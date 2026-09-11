"""
Comprehensive Test Suite for Octopus AI Agent Architecture
"""

import sys
import os
import unittest
import asyncio
from pathlib import Path

# Add project root to sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from octopus_ai import (
    OctopusSystem,
    OctopusAgent,
    BrowserTools,
    ToolRegistry,
    BrowserEngine,
    Memory,
    SafetyLayer,
    PermissionLevel,
    ActionCategory,
    ChatInterface,
    GroqLLM,
    PLATFORM_WORKFLOWS,
    get_platform_workflow,
    create_octopus,
)


class TestImports(unittest.TestCase):
    """Test all package and module imports"""

    def test_subpackage_imports(self):
        import octopus_ai.agent
        import octopus_ai.engine
        import octopus_ai.interface
        import octopus_ai.memory
        import octopus_ai.safety
        import octopus_ai.tools
        self.assertTrue(hasattr(octopus_ai.agent, "OctopusAgent"))
        self.assertTrue(hasattr(octopus_ai.engine, "BrowserEngine"))
        self.assertTrue(hasattr(octopus_ai.interface, "ChatInterface"))
        self.assertTrue(hasattr(octopus_ai.memory, "Memory"))
        self.assertTrue(hasattr(octopus_ai.safety, "SafetyLayer"))
        self.assertTrue(hasattr(octopus_ai.tools, "BrowserTools"))


class TestMemory(unittest.TestCase):
    """Test Memory module context management"""

    def setUp(self):
        self.memory = Memory()

    def test_conversation_history(self):
        self.memory.add_conversation("user", "Hello Octopus")
        self.memory.add_conversation("assistant", "Hello! How can I help?")
        history = self.memory.get_conversation_history(limit=5)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "Hello Octopus")

    def test_action_history_and_aliases(self):
        # Test 2-arg signature
        self.memory.add_action({"tool": "browser.open"}, {"success": True})
        # Test 1-arg signature with result inside
        self.memory.add_action({"action": {"tool": "browser.click"}, "result": {"success": True}})
        
        actions = self.memory.get_action_history(limit=10)
        self.assertEqual(len(actions), 2)
        
        # Test alias get_recent_actions
        recent = self.memory.get_recent_actions(limit=5)
        self.assertEqual(len(recent), 2)

    def test_task_and_location(self):
        self.memory.set_current_task({"goal": "Test WhatsApp"})
        self.assertEqual(self.memory.get_current_task(), {"goal": "Test WhatsApp"})
        
        self.memory.set_current_location("https://web.whatsapp.com", "WhatsApp Web")
        loc = self.memory.get_current_location()
        self.assertEqual(loc["website"], "https://web.whatsapp.com")
        self.assertEqual(loc["page"], "WhatsApp Web")

    def test_clear_alias(self):
        self.memory.add_conversation("user", "Clear test")
        self.memory.clear()
        self.assertEqual(len(self.memory.get_conversation_history()), 0)


class TestSafetyLayer(unittest.TestCase):
    """Test Safety and Permission Layer"""

    def setUp(self):
        self.safety = SafetyLayer()

    def test_automatic_actions(self):
        action = {"tool": "browser.read", "params": {}}
        perm = self.safety.check_permission(action)
        self.assertTrue(perm["allowed"])
        self.assertFalse(perm["requires_confirmation"])

    def test_blocked_domains(self):
        self.safety.add_blocked_domain("malicious-site.com")
        action = {"tool": "browser.open", "params": {"url": "https://malicious-site.com/login"}}
        perm = self.safety.check_permission(action)
        self.assertFalse(perm["allowed"])
        self.assertIn("Domain not allowed", perm["reason"])

    def test_allowed_domains_whitelist(self):
        self.safety.set_allowed_domains(["web.whatsapp.com", "instagram.com"])
        
        allowed_action = {"tool": "browser.open", "params": {"url": "https://web.whatsapp.com"}}
        self.assertTrue(self.safety.check_permission(allowed_action)["allowed"])
        
        blocked_action = {"tool": "browser.open", "params": {"url": "https://random-site.com"}}
        self.assertFalse(self.safety.check_permission(blocked_action)["allowed"])

    def test_confirmation_callback(self):
        self.safety.configure_permission(ActionCategory.COMMUNICATE, PermissionLevel.CONFIRMATION_REQUIRED)
        
        # Without callback -> blocked
        action = {"tool": "browser.type", "url": "https://web.whatsapp.com"}
        self.safety.add_tool_rule("browser.type", PermissionLevel.CONFIRMATION_REQUIRED)
        self.assertFalse(self.safety.check_permission(action)["allowed"])
        
        # With callback returning True -> allowed
        self.safety.set_confirmation_callback(lambda act: True)
        self.assertTrue(self.safety.check_permission(action)["allowed"])


class TestTools(unittest.TestCase):
    """Test Tool Registry and BrowserTools wrapper"""

    def test_tool_registry_listing(self):
        registry = ToolRegistry()
        tools = registry.list_tools()
        self.assertGreaterEqual(len(tools), 10)
        tool_names = [t["name"] for t in tools]
        self.assertIn("browser.open", tool_names)
        self.assertIn("browser.click", tool_names)
        self.assertIn("browser.type", tool_names)
        self.assertIn("browser.screenshot", tool_names)

    def test_browser_tools_execution_without_driver(self):
        browser_tools = BrowserTools()
        # Test error handling when no driver is active
        result = browser_tools.execute_tool_sync("browser.open", url="https://example.com")
        self.assertFalse(result["success"])
        self.assertIn("No browser driver available", result["error"])

    def test_browser_tools_parameter_normalization(self):
        browser_tools = BrowserTools()
        norm = browser_tools._normalize_params("browser.type", {"clear_first": True, "text": "Hi"})
        self.assertIn("clear", norm)
        self.assertNotIn("clear_first", norm)

        norm_wait = browser_tools._normalize_params("browser.wait", {"seconds": 3})
        self.assertEqual(norm_wait["condition"], "seconds")
        self.assertEqual(norm_wait["value"], 3)


class TestGroqLLM(unittest.TestCase):
    """Test Groq LLM integration and fallback logic"""

    def test_fallback_mode_without_key(self):
        llm = GroqLLM(api_key="")
        self.assertFalse(llm.is_available)
        
        # Test WhatsApp intent
        resp_wa = llm.chat("Open WhatsApp Web and send message")
        self.assertEqual(resp_wa.get("action"), "tool_call")
        self.assertEqual(resp_wa.get("tool_name"), "browser.open")
        self.assertEqual(resp_wa.get("parameters", {}).get("url"), "https://web.whatsapp.com")

        # Test Instagram intent
        resp_ig = llm.chat("Check Instagram notifications")
        self.assertEqual(resp_ig.get("action"), "tool_call")
        self.assertEqual(resp_ig.get("tool_name"), "browser.open")
        self.assertEqual(resp_ig.get("parameters", {}).get("url"), "https://instagram.com")

        # Test Canva intent
        resp_canva = llm.chat("Create presentation in Canva")
        self.assertEqual(resp_canva.get("action"), "tool_call")
        self.assertEqual(resp_canva.get("tool_name"), "browser.open")
        self.assertEqual(resp_canva.get("parameters", {}).get("url"), "https://canva.com")

    def test_platform_workflows_config(self):
        self.assertIn("whatsapp", PLATFORM_WORKFLOWS)
        self.assertIn("instagram", PLATFORM_WORKFLOWS)
        self.assertIn("canva", PLATFORM_WORKFLOWS)
        self.assertIsNotNone(get_platform_workflow("whatsapp"))


class TestAgent(unittest.TestCase):
    """Test Octopus Agent orchestration and execution loop"""

    def test_agent_sync_execute_task(self):
        agent = OctopusAgent()
        result = agent.execute_task("Go to Instagram and check notifications")
        self.assertIn("response", result)
        self.assertIn("success", result)

    def test_agent_safety_blocking(self):
        safety = SafetyLayer()
        safety.add_blocked_domain("web.whatsapp.com")
        
        agent = OctopusAgent(safety_layer=safety)
        result = agent.execute_task("Open WhatsApp Web")
        self.assertFalse(result.get("success", True))
        self.assertIn("blocked", result.get("message", "").lower())


class TestChatInterface(unittest.TestCase):
    """Test Chat Interface user interaction"""

    def test_chat_interface_with_callback(self):
        chat = ChatInterface()
        chat.set_message_handler(lambda msg: f"Echo: {msg}")
        resp = chat.receive_user_message("Test message")
        self.assertTrue(resp["success"])
        self.assertEqual(resp["response"], "Echo: Test message")
        self.assertEqual(len(chat.get_history()), 2)

    def test_chat_interface_with_agent(self):
        agent = OctopusAgent()
        chat = ChatInterface(agent=agent)
        resp = chat.receive_user_message("Open Canva")
        self.assertTrue(resp["success"])
        self.assertTrue(len(resp["response"]) > 0)


class TestSystem(unittest.TestCase):
    """Test complete OctopusSystem integration"""

    def test_system_status(self):
        system = OctopusSystem(headless=True)
        status = system.get_status()
        self.assertIn("initialized", status)
        self.assertIn("available_tools", status)
        self.assertGreaterEqual(status["available_tools"], 10)
        
        # Test chat integration
        response = system.chat("Hello Octopus")
        self.assertTrue(len(response) > 0)
        
        system.quit()


if __name__ == "__main__":
    unittest.main()
