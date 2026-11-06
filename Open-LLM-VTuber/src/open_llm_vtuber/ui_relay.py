"""Presentation-only OpenClaw transport. Never builds a prompt or replays UI history."""
import asyncio
import contextlib
import json
from uuid import uuid4

import httpx
from loguru import logger
from fastapi import HTTPException

from .chat_history_manager import create_new_history, get_history, store_message


async def sse_data(lines):
    """Decode SSE events, including multiline data and comments, without editing content."""
    data = []
    async for line in lines:
        if line == "":
            if data:
                yield "\n".join(data)
                data = []
        elif line.startswith("data:"):
            value = line[5:]
            data.append(value[1:] if value.startswith(" ") else value)
    if data:
        yield "\n".join(data)


class UIRelay:
    def __init__(self, handler, transport=None):
        self.handler = handler
        self.transport = transport  # Injectable transport for real streaming/cancellation tests.
        self.turns = {}

    def settings(self, uid):
        return self.handler.client_contexts[uid].character_config.agent_config.llm_configs.openai_compatible_llm

    def session_key(self, uid):
        context = self.handler.client_contexts[uid]
        # Each UI thread has one stable OpenClaw session; UI logs never become model history.
        return f"agent:cyrene:desktop:{context.history_uid}"

    async def send(self, uid, message):
        await self.handler.client_connections[uid].send_text(json.dumps(message, ensure_ascii=False))

    async def emit(self, uid, event, data, conversation_id):
        if self.handler.control_hub:
            await self.handler.control_hub.bus.emit(event, data, client_id=uid, conversation_id=conversation_id)

    async def select_history(self, uid, history_uid=None):
        running = self.handler.current_conversation_tasks.get(uid)
        if running and not running.done():
            raise HTTPException(409, 'Stop the current turn before changing conversations')
        context = self.handler.client_contexts[uid]
        # get_history validates path components. Unknown/empty selections create a fresh thread.
        from .chat_history_manager import _get_safe_history_path
        from pathlib import Path
        if history_uid and Path(_get_safe_history_path(context.character_config.conf_uid, history_uid)).is_file():
            context.history_uid = history_uid
            await self.send(uid, {'type': 'history-data', 'history_uid': history_uid,
                                  'messages': get_history(context.character_config.conf_uid, history_uid)})
        else:
            context.history_uid = create_new_history(context.character_config.conf_uid)
            await self.send(uid, {'type': 'new-history-created', 'history_uid': context.history_uid})

    async def submit(self, uid, data):
        if data.get('type') != 'text-input':
            raise HTTPException(422, 'UI mode accepts typed text and explicit external events; microphone/proactive triggers are disabled')
        if self.handler.control_hub and uid not in self.handler.control_hub.clients:
            raise HTTPException(401, 'Register the desktop before submitting messages')
        text = data.get('text')
        if not isinstance(text, str) or not text.strip() or len(text) > 100000:
            raise HTTPException(422, 'Message must contain 1–100000 characters')
        if data.get('images'):
            raise HTTPException(422, 'Automatic media capture is disabled; add a file path to the draft instead')
        running = self.handler.current_conversation_tasks.get(uid)
        if running and not running.done():
            raise HTTPException(409, 'A turn is already running; stop it before sending another message')
        context = self.handler.client_contexts[uid]
        if not context.history_uid:
            await self.select_history(uid)
        turn_id = data.get('cyrene_command_id') or str(uuid4())
        self.turns[uid] = turn_id
        task = asyncio.create_task(self.run(uid, text, turn_id, context.history_uid, self.session_key(uid)))
        self.handler.current_conversation_tasks[uid] = task

    async def interrupt(self, uid):
        task = self.handler.current_conversation_tasks.get(uid)
        if task and not task.done():
            # Closing the streaming HTTP response triggers the gateway's client-disconnect
            # AbortController, cancelling the actual agent run, not just hiding its reply.
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def run(self, uid, text, turn_id, history_uid, session_key):
        context = self.handler.client_contexts[uid]
        settings = self.settings(uid)
        result = ''
        status = 'completed'
        error = None
        try:
            store_message(context.character_config.conf_uid, history_uid, 'human', text)
            await self.send(uid, {'type': 'chat.started', 'command_id': turn_id, 'history_uid': history_uid, 'text': text})
            await self.emit(uid, 'input.received', {'text': text, 'session_key': session_key}, turn_id)
            headers = {'Authorization': f'Bearer {settings.llm_api_key}', 'x-openclaw-session-key': session_key}
            # Deliberately no VTuber system/persona prompt, history, temperature, tools,
            # translation, sentence splitting, emotion parsing or TTS preprocessing.
            body = {'model': settings.model, 'stream': True,
                    'messages': [{'role': 'user', 'content': text}]}
            async with asyncio.timeout(1800):
                async with httpx.AsyncClient(transport=self.transport, timeout=httpx.Timeout(None, connect=10), trust_env=False) as client:
                    async with client.stream('POST', settings.base_url.rstrip('/') + '/chat/completions', headers=headers, json=body) as response:
                        if response.status_code != 200:
                            raise RuntimeError(f'OpenClaw returned HTTP {response.status_code}')
                        finished = False
                        async for event in sse_data(response.aiter_lines()):
                            if event == '[DONE]':
                                finished = True
                                break
                            chunk = json.loads(event)
                            if chunk.get('error'):
                                raise RuntimeError('OpenClaw reported an error during the response')
                            for choice in chunk.get('choices', []):
                                delta = choice.get('delta', {}).get('content')
                                if isinstance(delta, str) and delta:
                                    result += delta
                                    await self.send(uid, {'type': 'chat.delta', 'command_id': turn_id, 'text': delta})
                                    await self.emit(uid, 'output.delta', {'text': delta}, turn_id)
                                if choice.get('finish_reason') is not None:
                                    finished = True
                        if not finished:
                            raise RuntimeError('OpenClaw response ended unexpectedly; partial text was retained')
        except asyncio.CancelledError:
            status = 'cancelled'
        except Exception as exc:
            status, error = 'failed', str(exc) or type(exc).__name__
        finally:
            if result:
                try:
                    store_message(context.character_config.conf_uid, history_uid, 'ai', result,
                                  name=context.character_config.character_name, avatar=context.character_config.avatar)
                except Exception:
                    logger.warning('Could not save the UI transcript; OpenClaw retains its own session')
                    status, error = 'failed', 'Could not save the local display transcript'
            with contextlib.suppress(Exception):
                await self.send(uid, {'type': 'chat.finished', 'command_id': turn_id, 'status': status, 'message': error})
            with contextlib.suppress(Exception):
                await self.emit(uid, 'output.completed', {'text': result, 'status': status, 'error': error}, turn_id)
            if self.turns.get(uid) == turn_id:
                self.turns.pop(uid, None)
            hub = self.handler.control_hub
            if hub and hub.conversations.get(uid) == turn_id:
                hub.conversations.pop(uid, None)
