import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from src.open_llm_vtuber.control_api import ControlHub, ControlCommand, EventBus

class Socket:
    def __init__(self): self.messages = []
    async def send_text(self, message): self.messages.append(json.loads(message))

class Handler:
    def __init__(self):
        self.client_connections = {'pet': Socket()}
        self.client_contexts = {}
        self.current_conversation_tasks = {}
        self.inputs = []
    async def _route_message(self, socket, uid, message): self.inputs.append((uid, message))

class ControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.handler = Handler()
        self.hub = ControlHub(self.handler, state_dir=self.temp.name, token='test-secret')
        await self.hub.register('pet', {'kind':'desktop','token':'test-secret'})

    async def asyncTearDown(self): self.temp.cleanup()

    async def send(self, name, data, request_id=None):
        return await self.hub.command(ControlCommand(name=name, data=data, request_id=request_id))

    async def test_cancelled_run_cannot_restore_thinking_or_override_unrelated_task(self):
        await self.send('task.start', {'task_id':'openclaw:run-a', 'run_id':'run-a', 'session_key':'thread-a', 'label':'Thinking'})
        await self.send('task.start', {'task_id':'openclaw:run-b', 'run_id':'run-b', 'session_key':'thread-b'})
        await self.hub.cancel_run_tasks('pet', 'run-a', 'thread-a')
        self.assertEqual(self.hub.tasks['openclaw:run-a']['status'], 'cancelled')
        self.assertEqual(self.hub.tasks['openclaw:run-b']['status'], 'running')
        for name in ['task.start', 'task.progress', 'task.end']:
            receipt = await self.send(name, {'task_id':'openclaw:run-a','label':'Thinking','status':'failed'})
            self.assertEqual(receipt['status'], 'ignored')
        self.assertEqual(self.hub.tasks['openclaw:run-a']['status'], 'cancelled')

    async def test_cancellation_before_task_hook_arrives(self):
        await self.hub.cancel_run_tasks('pet', 'late-run', 'thread-a')
        receipt = await self.send('task.start', {'task_id':'openclaw:late-run','session_key':'thread-a','label':'Thinking'})
        self.assertEqual(receipt['status'], 'ignored')
        self.assertNotIn('openclaw:late-run', self.hub.tasks)

    async def test_targets_real_session_and_retries_once(self):
        first, second = await asyncio.gather(self.send('input.submit', {'text':'hello'}, 'same'), self.send('input.submit', {'text':'hello'}, 'same'))
        self.assertEqual(len(self.handler.inputs), 1)
        self.assertEqual(first['command_id'], second['command_id'])
        self.assertTrue(second.get('duplicate'))
        with self.assertRaises(HTTPException) as error:
            await self.send('input.submit', {'text':'different'}, 'same')
        self.assertEqual(error.exception.status_code, 409)

    async def test_task_lifecycle_and_terminal_retry(self):
        await self.send('task.start', {'task_id':'one','label':'Working'})
        await self.send('task.start', {'task_id':'two'})
        await self.send('task.progress', {'task_id':'one','progress':0.5}, 'half')
        await self.send('task.end', {'task_id':'one','status':'failed'})
        self.assertTrue((await self.send('task.progress', {'task_id':'one','progress':0.5}, 'half'))['duplicate'])
        with self.assertRaises(HTTPException): await self.send('pet.sleep', {})
        with self.assertRaises(HTTPException): await self.send('task.progress', {'task_id':'one'})
        await self.send('task.end', {'task_id':'two'})
        with self.assertRaises(HTTPException): await self.send('pet.sleep', {})
        self.assertIn('task.failed', [e['type'] for e in self.hub.bus.events])

    async def test_capacity_failure_does_not_mutate(self):
        for i in range(100): await self.send('task.start', {'task_id':str(i)})
        with self.assertRaises(HTTPException): await self.send('task.start', {'task_id':'overflow'})
        self.assertEqual(len(self.hub.tasks), 100)
        self.assertNotIn('overflow', self.hub.tasks)

    async def test_events_require_explicit_agent_invocation(self):
        await self.send('input.event', {'event':'download.completed','payload':{'file':'example.txt'}})
        self.assertFalse(self.handler.inputs)
        await self.send('input.event', {'event':'download.completed','invoke_agent':True,'prompt':'Summarize the download event.'})
        self.assertEqual(self.handler.inputs[0][1]['text'], 'Summarize the download event.')

    async def test_applied_is_distinct_from_accepted(self):
        receipt = await self.send('expression.set', {'name':'wink'})
        self.assertTrue(receipt['delivered'])
        self.assertFalse(any(e['type']=='command.applied' for e in self.hub.bus.events))
        await self.hub.client_event('pet', {'event':'command.applied','command_id':receipt['command_id'],'data':{'name':'expression.set'}})
        self.assertEqual(self.hub.bus.events[-1]['type'], 'command.applied')

    async def test_anonymous_client_cannot_claim_desktop(self):
        await self.hub.register('anonymous', {'kind':'desktop'})
        self.assertNotIn('anonymous',self.hub.clients)
        self.assertEqual(self.hub.active_client(),'pet')

    async def test_events_are_immutable_snapshots(self):
        value = {'task': {'status': 'running'}}
        await self.hub.bus.emit('snapshot',value)
        value['task']['status'] = 'changed'
        self.assertEqual(self.hub.bus.events[-1]['data']['task']['status'],'running')

    async def test_replay_gap_and_longpoll(self):
        bus = EventBus(2)
        for _ in range(4): await bus.emit('tick')
        self.assertTrue(bus.read(1)['gap'])
        waiter = asyncio.create_task(bus.wait(4, 1))
        await asyncio.sleep(0)
        await bus.emit('next')
        self.assertEqual((await waiter)['events'][0]['id'], 5)

    async def test_expired_task_emits_event_and_releases_hold(self):
        await self.send('task.start', {'task_id':'expired'})
        self.hub.tasks['expired']['expires_at'] = 0
        await self.hub.start()
        await asyncio.sleep(1.05)
        self.assertEqual(self.hub.tasks['expired']['status'], 'expired')
        self.assertIn('task.expired', [event['type'] for event in self.hub.bus.events])
        await self.hub.close()

    async def test_cursor_reset_after_restart(self):
        batch = await self.hub.bus.wait(999, 1)
        self.assertTrue(batch['reset'])
        self.assertEqual(batch['cursor'], self.hub.bus.sequence)

    async def test_validation(self):
        for name, data in [('expression.set', {'name':'sleep'}),('expression.set', {'name':'unknown'}),('pet.wake', {}),('task.start',{'task_id':'x','timeout_ms':'bad'}),
            ('task.start',{'task_id':'x','label':{}}), ('layout.set',{'matrix':[0]*16}),
            ('ui.visibility',{'visible':'true'}), ('speech.say',{'text':'hello','speak':'false'})]:
            with self.subTest(name=name, data=data):
                with self.assertRaises(HTTPException): await self.send(name,data)

    async def test_speech_disabled_cannot_be_overridden_by_external_caller(self):
        async def forbidden_audio(*args): raise AssertionError('Speech synthesis must not run')
        self.handler.client_contexts['pet'] = SimpleNamespace(tts_engine=SimpleNamespace(speech_enabled=False,async_generate_audio=forbidden_audio))
        receipt = await self.send('speech.say',{'text':'Text notification','speak':True,'expression':'happy'})
        self.assertFalse(receipt['speech_enabled'])
        self.assertTrue(receipt['delivered'])
        self.assertFalse(self.hub.jobs)
        message=self.handler.client_connections['pet'].messages[-1]
        self.assertEqual(message['name'],'speech.say')
        self.assertFalse(message['data']['speak'])
        self.assertEqual(message['data']['text'],'Text notification')
        self.assertEqual(message['data']['expression'],'happy')

    async def test_tts_failure_is_reported_without_false_success(self):
        async def no_audio(*args): return None
        self.handler.client_contexts['pet'] = SimpleNamespace(tts_engine=SimpleNamespace(async_generate_audio=no_audio))
        receipt = await self.send('speech.say', {'text':'hello'})
        await asyncio.gather(*list(self.hub.jobs.values()))
        events = [e['type'] for e in self.hub.bus.events if e.get('command_id')==receipt['command_id']]
        self.assertIn('speech.failed', events)
        self.assertNotIn('speech.finished', events)
        self.assertEqual(self.handler.client_connections['pet'].messages[-1]['name'], 'subtitle.set')

    async def test_missing_client_has_no_false_acceptance(self):
        await self.hub.disconnect('pet')
        cursor = self.hub.bus.sequence
        with self.assertRaises(HTTPException): await self.send('speech.say', {'text':'hello'})
        self.assertEqual(self.hub.bus.sequence, cursor)

class AudioConversionTests(unittest.TestCase):
    def test_bundled_ffmpeg_does_not_need_ffprobe(self):
        import base64, io, math, os, shutil, struct, subprocess, wave
        from unittest.mock import patch
        from pydub import AudioSegment
        from src.open_llm_vtuber.utils.stream_audio import prepare_audio_payload
        bundled = Path(__file__).resolve().parents[1] / 'tools/ffmpeg/ffmpeg.exe'
        ffmpeg = str(bundled) if bundled.exists() else shutil.which('ffmpeg')
        if not ffmpeg: self.skipTest('FFmpeg is not installed')
        raw = io.BytesIO()
        with wave.open(raw, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
            wav.writeframes(b''.join(struct.pack('<h', int(10000*math.sin(i*0.1))) for i in range(1600)))
        with tempfile.TemporaryDirectory() as directory:
            mp3 = Path(directory) / 'voice.mp3'
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            subprocess.run([ffmpeg,'-v','error','-f','wav','-i','pipe:0',str(mp3)],input=raw.getvalue(),check=True,creationflags=flags)
            with patch.object(AudioSegment,'converter',ffmpeg), patch('pydub.utils.get_prober_name', side_effect=AssertionError('ffprobe must not be required')):
                payload=prepare_audio_payload(str(mp3))
            self.assertTrue(base64.b64decode(payload['audio']).startswith(b'RIFF'))
            self.assertGreater(len(payload['volumes']),0)

class RouteTests(unittest.TestCase):
    def test_auth_and_http_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            hub = ControlHub(Handler(), directory, 'secret')
            app = FastAPI(); app.include_router(hub.router())
            with TestClient(app) as client:
                self.assertEqual(client.get('/api/cyrene/health').status_code,200)
                self.assertEqual(client.get('/api/cyrene/state').status_code,401)
                headers={'Authorization':'Bearer secret'}
                self.assertEqual(client.get('/api/cyrene/state',headers=headers).status_code,200)
                receipt=client.post('/api/cyrene/commands',headers=headers,json={'name':'task.start','data':{'task_id':'test'}})
                self.assertEqual(receipt.status_code,200)
                events=client.get('/api/cyrene/events?after=0',headers=headers).json()
                self.assertIn('task.started',[event['type'] for event in events['events']])

if __name__ == '__main__': unittest.main()
