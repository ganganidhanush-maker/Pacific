"""
Test FastAPI server endpoints including chat, WhatsApp routing, voice transcribe, and live status.
"""

import unittest
from fastapi.testclient import TestClient
from server.app import app, is_whatsapp_open_request, parse_whatsapp_request


class TestServerEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_index_html(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("responseCard", res.text)
        self.assertIn("voiceRecordingPill", res.text)
        self.assertIn("transcribeWithWhisper", res.text)

    def test_live_status(self):
        res = self.client.get("/api/live-status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "online")
        self.assertIn("boot_id", data)

    def test_voice_transcribe_empty(self):
        res = self.client.post("/api/voice/transcribe", json={})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data.get("success"))

    def test_whatsapp_open_requests(self):
        open_phrases = [
            "open whatsapp",
            "can you open whatsapp",
            "open whatsapp web",
            "launch whatsapp",
            "whatsapp open cheyi",
            "whatsapp web",
            "open my whatsapp"
        ]
        for phrase in open_phrases:
            with self.subTest(phrase=phrase):
                self.assertTrue(is_whatsapp_open_request(phrase), f"Failed for: {phrase}")

    def test_whatsapp_message_parsing(self):
        contact, msg = parse_whatsapp_request("send message to Rahul saying I will reach at 5pm")
        self.assertEqual(contact, "Rahul")
        self.assertEqual(msg, "I will reach at 5pm")

    def test_chat_endpoint_whatsapp_open(self):
        res = self.client.post("/api/chat", json={"message": "can you open whatsapp web"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("WhatsApp", data.get("response", ""))
        self.assertEqual(data.get("action", {}).get("action"), "open")


if __name__ == "__main__":
    unittest.main()
