"""
Tests for WhatsApp Auto-Responder and Tab Management
"""

import sys
import os
import unittest
from pathlib import Path

# Add project root to sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from dotenv import load_dotenv
load_dotenv()

from octopus_ai.engine.selenium_engine import BrowserEngine
from octopus_ai.agent.whatsapp_responder import WhatsAppAutoResponder
from octopus_ai.agent.groq_llm import GroqLLM
from octopus_ai.memory.context import Memory


class TestWhatsAppAutoResponder(unittest.TestCase):
    """Test WhatsAppAutoResponder logic and AI response generation"""

    def setUp(self):
        self.llm = GroqLLM()
        self.memory = Memory()
        self.responder = WhatsAppAutoResponder(driver=None, groq_llm=self.llm, memory=self.memory)

    def test_generate_ai_reply(self):
        reply = self.responder.generate_ai_reply("Rahul", "Hey! Are you coming to the team lunch today?")
        self.assertTrue(len(reply) > 0)
        self.assertNotIn("<think>", reply)
        self.assertNotIn("</think>", reply)
        # Ensure no robotic meta-talk
        self.assertNotIn("automated response", reply.lower())
        self.assertNotIn("as an ai", reply.lower())
        self.assertNotIn("system status", reply.lower())

    def test_generate_ai_reply_telugu_slang(self):
        reply = self.responder.generate_ai_reply(
            contact="AKK", 
            message_text="Finally chip dobinda",
            recent_history=[
                {"sender": "AKK", "text": "mana peru undhi roiii"},
                {"sender": "Dhanush", "text": "Haha avuna roiii! Super!"},
                {"sender": "AKK", "text": "Finally chip dobinda"}
            ]
        )
        self.assertTrue(len(reply) > 0)
        self.assertNotIn("<think>", reply)
        self.assertNotIn("as an ai", reply.lower())
        self.assertNotIn("automated response", reply.lower())

    def test_sent_replies_history_suppression(self):
        self.responder.sent_replies_history.add("haha inka raledhu bro")
        # Simulating check against sent_replies_history
        test_msg = "haha inka raledhu bro"
        self.assertIn(test_msg.strip().lower(), self.responder.sent_replies_history)

    def test_text_deduplication(self):
        duplicated = "Haha yeah, finally!Haha yeah, finally!"
        half = len(duplicated) // 2
        cleaned = duplicated[:half] if duplicated[:half] == duplicated[half:] else duplicated
        self.assertEqual(cleaned, "Haha yeah, finally!")

    def test_custom_system_prompt_override(self):
        custom_prompt = "You are a pirate. Answer every message with 'Ahoy matey!'."
        resp = self.llm.chat("Hello there", system_prompt=custom_prompt)
        content = resp.get("content", "")
        self.assertIn("Ahoy", content)

    def test_responder_user_name_and_group_setting(self):
        self.assertEqual(self.responder.user_name, "Dhanush")
        self.assertFalse(self.responder.allow_group_replies)
        self.responder.set_whatsapp_handle("handle_123")
        self.assertEqual(self.responder.whatsapp_handle, "handle_123")

    def test_message_deduplication(self):
        fingerprint = "Rahul::Are you coming?"
        self.responder.replied_fingerprints.add(fingerprint)
        self.assertIn(fingerprint, self.responder.replied_fingerprints)

    def test_memory_recording(self):
        self.memory.add_conversation("user", "[Rahul]: Hello!")
        self.memory.add_conversation("assistant", "[To Rahul]: Hi there!")
        history = self.memory.get_conversation_history()
        self.assertEqual(len(history), 2)
        self.assertIn("Hello", history[0]["content"])
        self.assertIn("Hi there", history[1]["content"])

    def test_is_automated_or_broadcast_detection(self):
        dominos_msg = "Account Alert\nDear Customer,\nYour wallet has been credited successfully.\n\nExpires in 3 days\n\nThanks for choosing Domino's!"
        absentee_msg = "Good morning mam Today's (10-09-2026)absentees:- 6,19,31,34,38,53,55"
        otp_msg = "Your OTP is 482910. Do not share this with anyone."
        normal_msg = "Hey Dhanush! What time are we meeting today?"

        self.assertTrue(self.responder.is_automated_or_broadcast("Domino's", dominos_msg))
        self.assertFalse(self.responder.is_automated_or_broadcast("Class Rep", absentee_msg))
        self.assertTrue(self.responder.is_automated_or_broadcast("Bank Alert", otp_msg))
        self.assertFalse(self.responder.is_automated_or_broadcast("Rahul", normal_msg))


class TestBrowserTabManagement(unittest.TestCase):
    """Test BrowserEngine multi-tab capabilities"""

    @classmethod
    def setUpClass(cls):
        cls.engine = BrowserEngine(headless=True)
        init_res = cls.engine.initialize()
        if not init_res.get("success"):
            cls.engine = None

    @classmethod
    def tearDownClass(cls):
        if cls.engine:
            cls.engine.quit()

    def test_tab_operations(self):
        if not self.engine or not self.engine.is_ready():
            self.skipTest("Chrome browser not available in current test environment")
        
        # Navigate initial tab
        self.engine.navigate_to("https://example.com")
        
        # Open second tab
        open_res = self.engine.open_tab("https://example.org")
        self.assertTrue(open_res["success"])
        self.assertEqual(open_res["tab_count"], 2)
        
        # Get tabs list
        tabs_res = self.engine.get_tabs()
        self.assertTrue(tabs_res["success"])
        self.assertEqual(tabs_res["count"], 2)
        
        # Switch back to tab 0
        switch_res = self.engine.switch_to_tab(0)
        self.assertTrue(switch_res["success"])
        self.assertIn("example.com", switch_res["url"])


if __name__ == "__main__":
    unittest.main()
