import asyncio
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest

import httpx
from fastapi import HTTPException
from src.open_llm_vtuber.ui_relay import UIRelay
from src.open_llm_vtuber.chat_history_manager import get_history


class Socket:
    def __init__(self): self.messages = []
    async def send_text(self, text): self.messages.append(json.loads(text))


class Stream(httpx.AsyncByteStream):
    def __init__(self, parts, block=False):
        self.parts, self.block, self.closed = parts, block, False
        self.started = asyncio.Event()
    async def __aiter__(self):
        for part in self.parts:
            yield part.encode('utf-8')
        self.started.set()
        if self.block: await asyncio.Event().wait()
    async def aclose(self): self.closed = True


def delta(text):
    return 'data: ' + json.dumps({'choices': [{'delta': {'content': text}}]}, ensure_ascii=False) + '\n\n'


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.old_cwd = os.getcwd()
        self.temp = tempfile.TemporaryDirectory()
        os.chdir(self.temp.name)
        self.socket = Socket()
        settings = NS(base_url='http://gateway.test/v1', llm_api_key='local-test-token', model='openclaw/cyrene')
        self.context = NS(history_uid='', character_config=NS(conf_uid='test-ui', character_name='Cyrene', avatar='',
            persona_prompt='THIS MUST NEVER BE SENT', agent_config=NS(llm_configs=NS(openai_compatible_llm=settings))), agent_engine=None)
        self.handler = NS(client_connections={'pet': self.socket}, client_contexts={'pet': self.context}, current_conversation_tasks={}, control_hub=None)
        self.requests = []
        self.stream = Stream([delta('  [happy] **Hello**\n昔涟  '), 'data: [DONE]\n\n'])
        async def handle(request):
            self.requests.append(request)
            return httpx.Response(200, stream=self.stream)
        self.relay = UIRelay(self.handler, httpx.MockTransport(handle))

    async def asyncTearDown(self):
        await self.relay.interrupt('pet')
        os.chdir(self.old_cwd)
        self.temp.cleanup()

    async def send(self, text):
        await self.relay.submit('pet', {'type': 'text-input', 'text': text})
        await self.handler.current_conversation_tasks['pet']

    async def test_verbatim_message_response_and_no_prompt_injection(self):
        text = '  Please read this:\n"C:\\work\\a b.txt"\n  '
        await self.send(text)
        body = json.loads(self.requests[0].content)
        self.assertEqual(body, {'model': 'openclaw/cyrene', 'stream': True, 'messages': [{'role': 'user', 'content': text}]})
        self.assertEqual(self.requests[0].headers['x-openclaw-session-key'], self.relay.session_key('pet'))
        output = ''.join(m['text'] for m in self.socket.messages if m['type'] == 'chat.delta')
        self.assertEqual(output, '  [happy] **Hello**\n昔涟  ')
        history = get_history('test-ui', self.context.history_uid)
        self.assertEqual([m['content'] for m in history], [text, output])
        self.assertTrue(self.stream.closed)

    async def test_ui_history_never_replayed_but_session_continues(self):
        await self.send('first')
        key = self.requests[-1].headers['x-openclaw-session-key']
        await self.send('second')
        self.assertEqual(json.loads(self.requests[-1].content)['messages'], [{'role': 'user', 'content': 'second'}])
        self.assertEqual(self.requests[-1].headers['x-openclaw-session-key'], key)
        old = self.context.history_uid
        await self.relay.select_history('pet')
        self.assertNotEqual(self.relay.session_key('pet'), key)
        await self.relay.select_history('pet', old)
        self.assertEqual(self.relay.session_key('pet'), key)

    async def test_interrupt_closes_upstream_and_retains_partial_response(self):
        self.stream = Stream([delta('partial [wink]')], block=True)
        await self.relay.submit('pet', {'type': 'text-input', 'text': 'long task'})
        await asyncio.wait_for(self.stream.started.wait(), 1)
        with self.assertRaises(HTTPException): await self.relay.submit('pet', {'type': 'text-input', 'text': 'duplicate'})
        with self.assertRaises(HTTPException): await self.relay.select_history('pet')
        await self.relay.interrupt('pet')
        self.assertTrue(self.stream.closed)
        self.assertEqual(self.socket.messages[-1]['status'], 'cancelled')
        self.assertEqual(get_history('test-ui', self.context.history_uid)[-1]['content'], 'partial [wink]')
        self.stream = Stream(['data: [DONE]\n\n'])
        await self.send('can send again')
        self.assertEqual(self.socket.messages[-1]['status'], 'completed')

    async def test_unfinished_stream_is_failure_not_success(self):
        self.stream = Stream([delta('partial')])
        await self.send('hello')
        self.assertEqual(self.socket.messages[-1]['status'], 'failed')
        self.assertIn('unexpectedly', self.socket.messages[-1]['message'])

    async def test_gateway_error_is_reported(self):
        async def handle(request): return httpx.Response(503)
        self.relay.transport = httpx.MockTransport(handle)
        await self.send('hello')
        self.assertEqual(self.socket.messages[-1]['status'], 'failed')
        self.assertIn('503', self.socket.messages[-1]['message'])

    async def test_audio_proactive_and_automatic_screenshots_rejected(self):
        for data in [{'type': 'mic-audio-end'}, {'type': 'ai-speak-signal'},
                     {'type': 'text-input', 'text': 'hello', 'images': ['secret screenshot']}]:
            with self.assertRaises(HTTPException): await self.relay.submit('pet', data)
        self.assertFalse(self.requests)

    async def test_unregistered_client_cannot_run_agent(self):
        self.handler.control_hub = NS(clients={})
        with self.assertRaises(HTTPException) as error:
            await self.relay.submit('pet', {'type': 'text-input', 'text': 'hello'})
        self.assertEqual(error.exception.status_code, 401)
        self.handler.control_hub = None

    async def test_existing_history_loaded_without_agent_memory_engine(self):
        await self.send('old text')
        uid = self.context.history_uid
        self.socket.messages.clear()
        await self.relay.select_history('pet', uid)
        self.assertIsNone(self.context.agent_engine)
        self.assertEqual(self.socket.messages[0]['history_uid'], uid)
        self.assertEqual(self.socket.messages[0]['messages'][0]['content'], 'old text')


class PresentationContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_cold_start_and_cache_do_not_initialize_agent_or_speech_input(self):
        from unittest.mock import patch, AsyncMock
        from src.open_llm_vtuber.config_manager import read_yaml, validate_config
        from src.open_llm_vtuber.service_context import ServiceContext
        from src.open_llm_vtuber.websocket_handler import WebSocketHandler
        config = validate_config(read_yaml('conf.yaml'))
        config.system_config.ui_only = True
        config.character_config.tts_config.speech_enabled = False
        cache = ServiceContext()
        handler = WebSocketHandler(cache, ui_only=True)
        self.assertIsNotNone(handler.ui_relay, 'cold cache must support constructing a UI server')
        with patch.object(cache, 'init_live2d'), patch.object(cache, 'init_asr') as asr, patch.object(cache, 'init_vad') as vad, patch.object(cache, 'init_agent', new_callable=AsyncMock) as agent, patch.object(cache, 'init_translate') as translate, patch.object(cache, '_init_mcp_components', new_callable=AsyncMock) as mcp:
            await cache.load_from_config(config)
        for method in [asr, vad, agent, translate, mcp]: method.assert_not_called()
        self.assertIsNone(cache.agent_engine)
        self.assertIsNone(cache.system_prompt)
        self.assertFalse(cache.tts_engine.speech_enabled)
        session = ServiceContext()
        with patch.object(session, '_init_mcp_components', new_callable=AsyncMock) as mcp:
            await session.load_cache(config, config.system_config, config.character_config, None, None, cache.tts_engine, None, None, None)
        mcp.assert_not_called()


if __name__ == '__main__': unittest.main()
