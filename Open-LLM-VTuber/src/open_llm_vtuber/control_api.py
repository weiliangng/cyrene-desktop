"""Local control plane for the active desktop client (not a second chat session)."""
import asyncio
from collections import OrderedDict, deque
import contextlib
import copy
import hmac
import json
import os
from pathlib import Path
import secrets
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .agent.output_types import Actions, DisplayText
from .utils.stream_audio import prepare_audio_payload

EXPRESSIONS = ('neutral', 'happy', 'playful', 'blush', 'star_eyes', 'cry', 'hurt', 'angry', 'sweat', 'confused', 'sleep', 'wink')
COMMANDS = ('expression.set', 'speech.say', 'subtitle.set', 'task.start', 'task.progress', 'task.end',
            'pet.wake', 'pet.sleep', 'ui.visibility', 'layout.set', 'input.submit', 'input.event', 'interrupt')


class ControlCommand(BaseModel):
    name: str = Field(max_length=64)
    data: dict = Field(default_factory=dict)
    client_id: str | None = Field(default=None, max_length=128)
    request_id: str | None = Field(default=None, max_length=128)
    source: str = Field(default='external', max_length=80)


class EventBus:
    def __init__(self, capacity=512):
        self.events = deque(maxlen=capacity)
        self.sequence = 0
        self.epoch = str(uuid4())
        self.changed = asyncio.Condition()

    async def emit(self, name, data=None, **metadata):
        self.sequence += 1
        event = {'id': self.sequence, 'type': name, 'time': time.time(), 'data': copy.deepcopy(data or {}), **metadata}
        self.events.append(event)
        async with self.changed:
            self.changed.notify_all()
        return event

    def read(self, after=0):
        reset = after > self.sequence
        if reset: after = 0
        oldest = self.events[0]['id'] if self.events else self.sequence + 1
        return {'events': [event for event in self.events if event['id'] > after],
                'cursor': self.sequence, 'epoch': self.epoch, 'reset': reset, 'oldest_id': oldest, 'gap': bool(after and after < oldest - 1)}

    async def wait(self, after, timeout):
        async with self.changed:
            if self.sequence == after:
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self.changed.wait_for(lambda: self.sequence > after), timeout)
        return self.read(after)


class ControlHub:
    def __init__(self, ws_handler, state_dir=None, token=None):
        self.handler = ws_handler
        self.clients = OrderedDict()
        self.tasks = OrderedDict()
        self.receipts = OrderedDict()
        self.bus = EventBus()
        self.jobs = {}
        self.conversations = {}
        self.tts_slots = asyncio.Semaphore(2)
        root = Path(__file__).resolve().parents[3]
        self.state_dir = Path(state_dir or root / 'tmp' / 'cyrene-control')
        self.state_dir.mkdir(parents=True, exist_ok=True)
        token_file = self.state_dir / 'token'
        if token is None:
            if not token_file.exists():
                token_file.write_text(secrets.token_urlsafe(32), encoding='utf-8')
            token = token_file.read_text(encoding='utf-8').strip()
        self.token = token
        self.expression = None
        self.command_lock = asyncio.Lock()
        self.sweeper = None

    async def start(self):
        async def sweep():
            while True:
                await asyncio.sleep(1)
                for task in list(self.tasks.values()):
                    if task['status'] == 'running' and task['expires_at'] <= time.time():
                        task['status'] = 'expired'
                        await self.bus.emit('task.expired', dict(task))
        self.sweeper = asyncio.create_task(sweep())

    async def close(self):
        pending = list(self.jobs.values())
        if self.sweeper: pending.append(self.sweeper)
        for job in pending: job.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    def authorized(self, authorization):
        return hmac.compare_digest(authorization or '', 'Bearer ' + self.token)

    async def authenticate(self, request: Request):
        if not self.authorized(request.headers.get('authorization')):
            raise HTTPException(401, 'A Cyrene control token is required')

    async def register(self, uid, metadata):
        token = metadata.get("token")
        if not isinstance(token, str) or not self.authorized("Bearer " + token):
            return False
        self.clients[uid] = {'id': uid, 'kind': metadata.get('kind', 'desktop'), 'connected_at': time.time(), 'ready': False}
        await self.bus.emit('client.connected', self.clients[uid], client_id=uid)
        await self.send(uid, {'type': 'cyrene-state', 'state': self.state()})

    async def disconnect(self, uid):
        self.conversations.pop(uid, None)
        if self.clients.pop(uid, None) is not None:
            await self.bus.emit('client.disconnected', client_id=uid)
        for task_id, job in list(self.jobs.items()):
            if task_id.startswith(uid + ':'):
                job.cancel()

    def active_client(self, requested=None):
        if requested:
            if requested not in self.clients:
                raise HTTPException(404, 'Desktop client not connected')
            return requested
        return next(reversed(self.clients), None) if self.clients else None

    async def send(self, uid, message):
        connection = self.handler.client_connections.get(uid)
        if not connection:
            return False
        try:
            await connection.send_text(json.dumps(message))
            return True
        except Exception:
            await self.disconnect(uid)
            return False

    def state(self):
        now = time.time()
        tasks = [dict(task, status='expired') if task['status'] == 'running' and task['expires_at'] < now else task
                 for task in self.tasks.values()]
        return {'version': 1, 'active_client_id': self.active_client(), 'clients': list(self.clients.values()),
                'tasks': tasks, 'expression': self.expression, 'expressions': list(EXPRESSIONS),
                'commands': list(COMMANDS), 'event_cursor': self.bus.sequence, 'event_epoch': self.bus.epoch}

    async def client_event(self, uid, message):
        if uid not in self.clients:
            return
        name = message.get('event', '')
        if name not in ('command.applied', 'command.failed', 'speech.started', 'speech.finished', 'speech.failed',
                        'client.ready', 'output.subtitle', 'speech.cancelled', 'pet.awake', 'pet.sleeping', 'layout.changed', 'input.focused', 'input.blurred', 'ui.visibility'):
            return
        data = message.get('data', {})
        if len(json.dumps(data)) > 32768:
            return
        if name == 'client.ready':
            self.clients[uid]['ready'] = True
        if name == 'layout.changed':
            self.clients[uid]['layout'] = data
        if name == 'ui.visibility':
            self.clients[uid]['visible'] = data.get('visible')
        await self.bus.emit(name, data, client_id=uid, command_id=message.get('command_id'))

    def validate(self, command):
        if command.name not in COMMANDS:
            raise HTTPException(422, 'Unknown command')
        data = command.data
        if len(json.dumps(data)) > 32768:
            raise HTTPException(413, 'Command data exceeds 32 KiB')
        if command.name == 'expression.set':
            if data.get('name') not in EXPRESSIONS:
                raise HTTPException(422, 'Unknown facial expression')
        if data.get('expression') is not None and data['expression'] not in EXPRESSIONS:
            raise HTTPException(422, 'Unknown facial expression')
        if command.name in ('speech.say', 'subtitle.set', 'input.submit'):
            if not isinstance(data.get('text'), str) or not data['text'].strip() or len(data['text']) > 10000:
                raise HTTPException(422, 'text must contain 1–10000 characters')
        if 'duration_ms' in data and (not isinstance(data['duration_ms'], (int, float)) or not 0 <= data['duration_ms'] <= 3600000):
            raise HTTPException(422, 'duration_ms must be between 0 and 3600000')
        if 'timeout_ms' in data and (not isinstance(data['timeout_ms'], (int, float)) or not 1000 <= data['timeout_ms'] <= 3600000):
            raise HTTPException(422, 'timeout_ms must be between 1000 and 3600000')
        if 'speak' in data and not isinstance(data['speak'], bool):
            raise HTTPException(422, 'speak must be a boolean')
        if 'label' in data and (not isinstance(data['label'], str) or len(data['label']) > 500):
            raise HTTPException(422, 'label must contain at most 500 characters')
        if command.name.startswith('task.'):
            if not isinstance(data.get('task_id'), str) or not 1 <= len(data['task_id']) <= 128:
                raise HTTPException(422, 'task_id is required')
            if 'progress' in data and (not isinstance(data['progress'], (float, int)) or not 0 <= data['progress'] <= 1):
                raise HTTPException(422, 'progress must be between 0 and 1')
            if command.name != 'task.start' and data['task_id'] not in self.tasks:
                raise HTTPException(404, 'Unknown task_id')
            if command.name == 'task.progress' and self.tasks[data['task_id']]['status'] != 'running':
                raise HTTPException(409, 'Cannot update a finished task; start it again first')
            if command.name == 'task.end' and data.get('status', 'completed') not in ('completed', 'failed', 'cancelled'):
                raise HTTPException(422, 'Invalid terminal task status')
        if command.name == 'layout.set':
            matrix = data.get('matrix')
            import math
            if (not isinstance(matrix, list) or len(matrix) != 16
                    or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in matrix)
                    or not 0 < matrix[0] <= 20 or not 0 < matrix[5] <= 20
                    or abs(matrix[12]) > 100 or abs(matrix[13]) > 100 or matrix[15] != 1):
                raise HTTPException(422, 'Invalid model transform')
        if command.name == 'ui.visibility' and not isinstance(data.get('visible'), bool):
            raise HTTPException(422, 'visible must be a boolean')
        if command.name == 'input.event' and data.get('prompt') is not None and (not isinstance(data['prompt'], str) or len(data['prompt']) > 10000):
            raise HTTPException(422, 'prompt must contain at most 10000 characters')
        if command.name == 'input.event' and (not isinstance(data.get('event'), str) or not 1 <= len(data['event']) <= 128):
            raise HTTPException(422, 'event name is required')

    async def command(self, command: ControlCommand):
        async with self.command_lock:
            return await self._command(command)

    async def _command(self, command: ControlCommand):
        request_id = command.request_id or str(uuid4())
        fingerprint = json.dumps(command.model_dump(exclude={'request_id'}), sort_keys=True)
        if request_id in self.receipts:
            previous = self.receipts[request_id]
            if previous['fingerprint'] != fingerprint:
                raise HTTPException(409, 'request_id was already used for a different command')
            return dict(previous['receipt'], duplicate=True)
        self.validate(command)
        uid = self.active_client(command.client_id)
        name, data = command.name, dict(command.data)
        context = self.handler.client_contexts.get(uid)
        if name == 'speech.say' and not getattr(getattr(context, 'tts_engine', None), 'speech_enabled', True):
            data['speak'] = False
        if name in ('input.submit', 'interrupt') or (name == 'input.event' and data.get('invoke_agent')):
            if not uid:
                raise HTTPException(409, 'No desktop client connected')
        if name == 'input.submit' or (name == 'input.event' and data.get('invoke_agent')):
            running = self.handler.current_conversation_tasks.get(uid)
            if running and not running.done():
                raise HTTPException(409, 'A conversation is already running; interrupt it first')
        if name == 'speech.say' and data.get('speak', True):
            running = self.handler.current_conversation_tasks.get(uid)
            if running and not running.done():
                raise HTTPException(409, 'A conversation is already running; interrupt it before speaking externally')
        if name == 'pet.sleep' and any(task['status'] == 'running' and task['expires_at'] > time.time() for task in self.tasks.values()):
            raise HTTPException(409, 'Finish active tasks before putting the pet to sleep')
        if name == 'speech.say' and data.get('speak', True):
            if not uid:
                raise HTTPException(409, 'No desktop client connected')
            if len(self.jobs) >= 8:
                raise HTTPException(429, 'Speech queue is full')
        if name.startswith('task.'):
            task_id = data['task_id']
            old = self.tasks.get(task_id, {})
            task = {**old, **data, 'task_id': task_id, 'updated_at': time.time(),
                    'status': data.get('status', 'completed') if name == 'task.end' else 'running',
                    'expires_at': time.time() + min(max(data.get('timeout_ms', 300000), 1000), 3600000) / 1000}
            if task_id not in self.tasks and len(self.tasks) >= 100:
                terminal = next((key for key, value in self.tasks.items() if value['status'] != 'running' or value['expires_at'] < time.time()), None)
                if terminal is None:
                    raise HTTPException(429, 'Too many active tasks')
                del self.tasks[terminal]
            self.tasks[task_id] = task
            data = task
            while len(self.tasks) > 100:
                terminal = next((key for key, value in self.tasks.items() if value['status'] != 'running'), None)
                if terminal is None:
                    raise HTTPException(429, 'Too many active tasks')
                del self.tasks[terminal]
        if name == 'expression.set':
            self.expression = {'name': data['name'], 'expires_at': time.time() + data.get('duration_ms', 5000) / 1000}
        await self.bus.emit('command.accepted', {'name': name, 'source': command.source}, command_id=request_id, client_id=uid)
        receipt = {'command_id': request_id, 'name': name, 'status': 'accepted', 'client_id': uid, 'delivered': False}
        if name == 'speech.say': receipt['speech_enabled'] = data.get('speak', True)
        envelope = {'type': 'cyrene-command', 'command_id': request_id, 'name': name, 'data': data}
        if name == 'speech.say' and data.get('speak', True):
            if not uid:
                raise HTTPException(409, 'No desktop client connected')
            key = uid + ':' + request_id
            if len(self.jobs) >= 8:
                raise HTTPException(429, 'Speech queue is full')
            job = asyncio.create_task(self.speak(uid, envelope))
            self.jobs[key] = job
            job.add_done_callback(lambda _: self.jobs.pop(key, None))
        elif name in ('input.submit', 'input.event'):
            text = data.get('text')
            if name == 'input.event':
                await self.bus.emit('input.event', data, command_id=request_id, client_id=uid)
                if data.get('invoke_agent'):
                    text = data.get('prompt') or f"External event {data['event']}: {json.dumps(data.get('payload', {}))}. Respond briefly if useful."
            if name == 'input.submit' or data.get('invoke_agent'):
                await self.handler._route_message(self.handler.client_connections[uid], uid, {'type': 'text-input', 'text': text, 'cyrene_command_id': request_id})
                receipt['delivered'] = True
        else:
            if name == 'interrupt':
                for key, job in list(self.jobs.items()):
                    if key.startswith(uid + ':'):
                        job.cancel()
                await self.handler._route_message(self.handler.client_connections[uid], uid, {'type': 'interrupt-signal', 'text': ''})
            receipt['delivered'] = bool(uid and await self.send(uid, envelope))
        if name.startswith('task.'):
            await self.bus.emit('task.' + ('started' if name == 'task.start' else 'progress' if name == 'task.progress' else data['status']), data, command_id=request_id)
        await self.bus.emit('command.dispatched', receipt, command_id=request_id, client_id=uid)
        self.receipts[request_id] = {'fingerprint': fingerprint, 'receipt': receipt}
        while len(self.receipts) > 256:
            self.receipts.popitem(last=False)
        return receipt

    async def speak(self, uid, envelope):
        command_id = envelope['command_id']
        audio_path = None
        try:
            await self.bus.emit('speech.synthesizing', command_id=command_id, client_id=uid)
            async with self.tts_slots:
                context = self.handler.client_contexts[uid]
                audio_path = await asyncio.wait_for(context.tts_engine.async_generate_audio(
                    envelope['data']['text'], 'cyrene-' + str(uuid4())), 45)
                if not audio_path:
                    raise RuntimeError('The configured TTS provider did not produce audio')
                payload = await asyncio.to_thread(prepare_audio_payload, audio_path, 20,
                    DisplayText(envelope['data']['text'], 'Cyrene'),
                    Actions(expressions=[envelope['data']['expression']] if envelope['data'].get('expression') else None))
                envelope['data']['audio'] = payload
                delivered = await self.send(uid, envelope)
                await self.bus.emit('speech.ready', {'delivered': delivered}, command_id=command_id, client_id=uid)
        except asyncio.CancelledError:
            await self.bus.emit('speech.cancelled', command_id=command_id, client_id=uid)
            raise
        except Exception as error:
            await self.bus.emit('speech.failed', {'message': str(error)}, command_id=command_id, client_id=uid)
            await self.send(uid, {'type': 'cyrene-command', 'command_id': command_id, 'name': 'subtitle.set',
                                  'data': {'text': envelope['data']['text'], 'error': 'Speech synthesis failed'}})
        finally:
            if audio_path:
                with contextlib.suppress(OSError):
                    Path(audio_path).unlink()

    def router(self):
        router = APIRouter(prefix='/api/cyrene', tags=['Cyrene control'])

        @router.get('/health')
        async def health():
            return {'ok': True, 'version': 1, 'desktop_clients': len(self.clients)}

        @router.get('/state', dependencies=[Depends(self.authenticate)])
        async def state():
            return self.state()

        @router.post('/commands', dependencies=[Depends(self.authenticate)])
        async def command(value: ControlCommand):
            return await self.command(value)

        @router.get('/events', dependencies=[Depends(self.authenticate)])
        async def events(after: int = 0, wait: float = 0):
            if after < 0 or not 0 <= wait <= 30:
                raise HTTPException(422, 'after must be nonnegative; wait must be 0–30 seconds')
            return await self.bus.wait(after, wait) if wait else self.bus.read(after)

        @router.websocket('/events/ws')
        async def event_socket(socket: WebSocket):
            if not self.authorized(socket.headers.get('authorization')):
                await socket.close(code=1008)
                return
            await socket.accept()
            try:
                cursor = max(0, int(socket.query_params.get('after', 0)))
                while True:
                    batch = await self.bus.wait(cursor, 15)
                    await socket.send_json(batch)
                    cursor = batch['cursor']
            except (WebSocketDisconnect, ValueError, RuntimeError):
                pass
        return router
