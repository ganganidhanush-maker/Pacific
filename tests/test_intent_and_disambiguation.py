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
        self.assertEqual(classify_intent('activate whatsapp'), 'web')
        self.assertEqual(classify_intent('start whatsapp auto responder'), 'web')
        self.assertEqual(classify_intent('stop whatsapp auto responder'), 'web')
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

    @patch('server.app.start_whatsapp_auto_responder')
    @patch('server.app.generate_speech_file', new_callable=AsyncMock)
    def test_activate_whatsapp_command(self, mock_speech, mock_start):
        mock_speech.return_value = '/assets/audio_cache/test.mp3'
        mock_start.return_value = (True, "WhatsApp Auto-Responder started.")

        from fastapi import BackgroundTasks
        bg = BackgroundTasks()

        req = ChatRequest(message='activate whatsapp', agent='main')
        res = asyncio.run(chat_endpoint(req, bg))

        self.assertTrue(res['success'])
        self.assertEqual(res['current_agent'], 'web')
        self.assertEqual(res['action']['action'], 'auto_responder_activated')
        self.assertIn('25 seconds', res['response'])
        mock_start.assert_called_once()

    @patch('server.app.stop_whatsapp_auto_responder')
    @patch('server.app.generate_speech_file', new_callable=AsyncMock)
    def test_stop_whatsapp_command(self, mock_speech, mock_stop):
        mock_speech.return_value = '/assets/audio_cache/test.mp3'
        mock_stop.return_value = (True, "WhatsApp Auto-Responder stopped.")

        from fastapi import BackgroundTasks
        bg = BackgroundTasks()

        req = ChatRequest(message='stop whatsapp', agent='web')
        res = asyncio.run(chat_endpoint(req, bg))

        self.assertTrue(res['success'])
        self.assertEqual(res['action']['action'], 'auto_responder_stopped')
        self.assertIn('stopped', res['response'].lower())
        mock_stop.assert_called_once()

    def test_whatsapp_auto_responder_endpoints(self):
        client = TestClient(app)
        res = client.get('/api/whatsapp/auto-responder/status')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['inactivity_limit_seconds'], 25.0)

    def test_avatar_mode_endpoints(self):
        client = TestClient(app)
        # Test GET /api/avatar/mode
        res = client.get('/api/avatar/mode')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('mode', data)
        self.assertIn(data['mode'], ['3d_vrm', 'video'])

        # Test POST /api/avatar/mode valid
        res_post = client.post('/api/avatar/mode', json={'mode': 'video'})
        self.assertEqual(res_post.status_code, 200)
        self.assertEqual(res_post.json()['mode'], 'video')

        res_get = client.get('/api/avatar/mode')
        self.assertEqual(res_get.json()['mode'], 'video')

        # Switch back to 3d_vrm
        res_post2 = client.post('/api/avatar/mode', json={'mode': '3d_vrm'})
        self.assertEqual(res_post2.status_code, 200)
        self.assertEqual(res_post2.json()['mode'], '3d_vrm')

        # Test invalid mode
        res_bad = client.post('/api/avatar/mode', json={'mode': 'invalid_mode'})
        self.assertEqual(res_bad.status_code, 400)

    def test_avatar_motion_profile_endpoint(self):
        client = TestClient(app)
        res = client.get('/api/avatar/motion-profile')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('physics_and_procedural', data)
        self.assertIn('audio_viseme_mapping', data)

    def test_avatar_models_and_upload(self):
        client = TestClient(app)
        res = client.get('/api/avatar/models')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('models', data)

        # Test invalid upload extension
        res_bad_file = client.post(
            '/api/avatar/upload-vrm',
            files={'file': ('fake.txt', b'dummy content', 'text/plain')}
        )
        self.assertEqual(res_bad_file.status_code, 400)

        # Test valid VRM upload
        res_upload = client.post(
            '/api/avatar/upload-vrm',
            files={'file': ('test_model.vrm', b'fake vrm bytes', 'application/octet-stream')}
        )
        self.assertEqual(res_upload.status_code, 200)
        data_up = res_upload.json()
        self.assertTrue(data_up['success'])
        self.assertEqual(data_up['filename'], 'test_model.vrm')

        # Clean up test uploaded model
        test_file = repo_dir / 'assets' / 'avatars' / 'test_model.vrm'
        if test_file.exists():
            test_file.unlink()


if __name__ == '__main__':
    unittest.main()


