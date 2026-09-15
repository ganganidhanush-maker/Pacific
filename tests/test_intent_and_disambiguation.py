import sys
import unittest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

repo_dir = Path(__file__).resolve().parent.parent / 'octopus_ai'
parent_dir = repo_dir.parent
for p in [str(parent_dir), str(repo_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from server.app import (
    classify_intent,
    parse_whatsapp_request,
    PENDING_SESSION_STATE,
    chat_endpoint,
    ChatRequest,
    get_live_status,
    get_avatar_manifest,
    detect_language_and_voice,
    generate_speech_file,
    app
)
from server.local_llm_service import sanitize_speech_response
from fastapi.testclient import TestClient



class TestIntentAndDisambiguation(unittest.TestCase):
    def test_classify_intent_desktop(self):
        self.assertEqual(classify_intent('open calculator'), 'desktop')
        self.assertEqual(classify_intent('launch calc'), 'desktop')
        self.assertEqual(classify_intent('open notepad'), 'desktop')
        self.assertEqual(classify_intent('open new notepad and write the Python Assignment there'), 'desktop')
        self.assertEqual(classify_intent('open paint'), 'desktop')
        self.assertEqual(classify_intent('find all pdf files on my computer'), 'desktop')
        self.assertEqual(classify_intent('/desktop'), 'desktop')

    def test_classify_intent_web(self):
        self.assertEqual(classify_intent('open whatsapp in web and send message to Harsha'), 'web')
        self.assertEqual(classify_intent('open canva'), 'web')
        self.assertEqual(classify_intent('open instagram'), 'web')
        self.assertEqual(classify_intent('search google for AI news'), 'web')
        self.assertEqual(classify_intent('/web'), 'web')

    def test_classify_intent_research(self):
        self.assertEqual(classify_intent('research quantum computing'), 'research')
        self.assertEqual(classify_intent('presentation outline for AI'), 'research')
        self.assertEqual(classify_intent('/research'), 'research')

    def test_classify_intent_switch_commands(self):
        self.assertEqual(classify_intent('/main'), 'main')
        self.assertEqual(classify_intent('/chat'), 'chatbot')

    def test_parse_whatsapp_request(self):
        contact, msg = parse_whatsapp_request('open Whatsapp in Web and Send Message to Harsha')
        self.assertEqual(contact, 'Harsha')
        self.assertEqual(msg, 'Hello!')

        contact, msg = parse_whatsapp_request('send message to Harsha saying are you coming to college?')
        self.assertEqual(contact, 'Harsha')
        self.assertEqual(msg, 'are you coming to college?')

        contact, msg = parse_whatsapp_request('send message to Harsha: Please check the document')
        self.assertEqual(contact, 'Harsha')
        self.assertEqual(msg, 'Please check the document')

        contact, msg = parse_whatsapp_request('send message to Harsha that class is cancelled')
        self.assertEqual(contact, 'Harsha')
        self.assertEqual(msg, 'class is cancelled')

    @patch('server.app.run_whatsapp_task', new_callable=AsyncMock)
    @patch('server.app.generate_speech_file', new_callable=AsyncMock)
    def test_whatsapp_disambiguation_multi_turn(self, mock_speech, mock_wa):
        mock_speech.return_value = '/assets/audio_cache/test.mp3'
        mock_wa.return_value = MagicMock(
            success=True,
            data={'disambiguation_required': True, 'matches': ['Harsha Vardhan', 'Harsha College']}
        )

        from fastapi import BackgroundTasks
        bg = BackgroundTasks()

        req1 = ChatRequest(message='Send message to Harsha saying are you free?', agent='main')
        res1 = asyncio.run(chat_endpoint(req1, bg))

        self.assertTrue(res1['success'])
        self.assertEqual(res1['current_agent'], 'web')
        self.assertIn('Harsha Vardhan', res1['response'])
        self.assertIn('Harsha College', res1['response'])
        self.assertIn('Which one would you like to message?', res1['response'])
        self.assertEqual(PENDING_SESSION_STATE.get('type'), 'whatsapp_disambiguation')

        mock_wa.return_value = MagicMock(success=True, message='Message sent to Harsha Vardhan')
        req2 = ChatRequest(message='1', agent='web')
        res2 = asyncio.run(chat_endpoint(req2, bg))

        self.assertTrue(res2['success'])
        self.assertEqual(res2['current_agent'], 'web')
        self.assertIn('Harsha Vardhan', res2['response'])
        self.assertNotIn('type', PENDING_SESSION_STATE)
        mock_wa.assert_called_with(contact='', message='are you free?', selected_contact='Harsha Vardhan')

    def test_live_status_endpoint(self):
        res = asyncio.run(get_live_status())
        self.assertEqual(res['status'], 'online')
        self.assertIn('boot_id', res)
        self.assertIn('ui_mtime', res)
        self.assertIn('current_agent', res)

    def test_avatar_manifest_endpoint(self):
        res = asyncio.run(get_avatar_manifest())
        self.assertTrue(res['success'])
        manifest = res['manifest']
        self.assertIn('idle', manifest)
        self.assertIn('thinking', manifest)
        self.assertIn('speaking', manifest)
        self.assertGreaterEqual(len(manifest['idle']), 6)
        self.assertGreaterEqual(len(manifest['thinking']), 3)
        self.assertGreaterEqual(len(manifest['speaking']), 7)

    def test_classify_intent_expanded_desktop_tools(self):
        self.assertEqual(classify_intent('take a screenshot'), 'desktop')
        self.assertEqual(classify_intent('show system info and battery'), 'desktop')
        self.assertEqual(classify_intent('mute master volume'), 'desktop')
        self.assertEqual(classify_intent('lock workstation'), 'desktop')

    def test_detect_language_and_voice(self):
        self.assertEqual(detect_language_and_voice('నమస్కారం ధనుష్!'), 'te-IN-MohanNeural')
        self.assertEqual(detect_language_and_voice('namaskaram bro ela unnav?'), 'te-IN-MohanNeural')
        self.assertEqual(detect_language_and_voice('enti bro em chestunnav'), 'te-IN-MohanNeural')
        self.assertEqual(detect_language_and_voice('नमस्ते धनুষ, आप कैसे हैं?'), 'hi-IN-MadhurNeural')
        self.assertEqual(detect_language_and_voice('வணக்கம் தனுஷ்'), 'ta-IN-ValluvarNeural')
        self.assertEqual(detect_language_and_voice('Open Calculator and Notepad for me'), 'en-IN-PrabhatNeural')

    def test_generate_speech_file_telugu(self):
        url = asyncio.run(generate_speech_file('నమస్కారం! నేను ఆక్టోపస్ ఏఐ.'))
        self.assertIsNotNone(url)
        self.assertTrue(url.startswith('/assets/audio_cache/'))
        self.assertTrue(url.endswith('.mp3') or url.endswith('.wav'))

    def test_sanitize_speech_response_multilingual(self):
        # JSON response with 'text' key
        json_resp = '{"action": "response", "text": "నమస్కారం! నేను మీకు సహాయపడగలను."}'
        clean = sanitize_speech_response(json_resp)
        self.assertEqual(clean, "నమస్కారం! నేను మీకు సహాయపడగలను.")

        # Markdown asterisks stripped while preserving Telugu script
        md_resp = "**నమస్కారం!** నేను *ఆక్టోపస్ ఏఐ*."
        clean_md = sanitize_speech_response(md_resp)
        self.assertEqual(clean_md, "నమస్కారం! నేను ఆక్టోపస్ ఏఐ.")

    def test_cors_and_cache_control_headers(self):
        client = TestClient(app)
        api_res = client.get('/api/live-status')
        self.assertEqual(api_res.status_code, 200)
        self.assertEqual(api_res.headers.get('access-control-allow-origin'), '*')
        self.assertIn('no-cache', api_res.headers.get('cache-control', ''))

        audio_res = client.get('/assets/videos/video_manifest.json')
        self.assertEqual(audio_res.headers.get('access-control-allow-origin'), '*')


if __name__ == '__main__':
    unittest.main()


