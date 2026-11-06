# Cyrene external connections

The desktop is a presentation-only UI (`system_config.ui_only: true`). OpenClaw owns reasoning, tools and memory; SoCLaaS supplies its model. Commands target the registered desktop WebSocket session, so an automation does not create an invisible second avatar/session.

## Start and configure

From the repository root, install the pinned OpenClaw runtime once:

```powershell
npm.cmd ci --prefix integrations/openclaw --omit=optional --maxsockets=2 --no-audit --no-fund
```

Set `SOCLAAS_API_KEY` in the launch environment, then run **Start Cyrene with OpenClaw.cmd**. This creates a project profile, backs up the previous local VTuber config to `tmp/openclaw/conf.before-openclaw.yaml`, connects desktop chat to the gateway, and launches the pet. Once connected, **Start Cyrene Desktop.cmd** also starts the gateway automatically.

After reboot, the launcher waits for saved-session recovery and prints progress every 15 seconds. A gateway that is alive but not ready is reused. Cross-process startup locks prevent parallel launchers from spawning competing gateways or backends; these locks are automatically released by Windows after a crash/reboot. The readiness deadline is four minutes, and timing out leaves OpenClaw running so a second launch can continue waiting.

The runtime is pinned to OpenClaw 2026.11.1. Node 24.16+ within Node 24, or Node 26.1+, is required by this version. The Windows native helper is explicitly pinned to avoid its slower .NET fallback.

- Gateway: `http://127.0.0.1:18789`, token authenticated. Its OpenAI-compatible endpoint selects `model: openclaw/cyrene`.
- SoCLaaS: `https://soclaas-api.comp.nus.edu.sg/v1`, `qwen3.8:27b`; native tool calls verified. Model declaration uses a 131072-token context and 8192 output limit.
- Settings, gateway token, sessions, writable agent workspace and logs: `tmp/openclaw/`, ignored by Git.
- Persona/workspace templates: `integrations/openclaw/workspace/`; copied on first configure. Edit the live `tmp/openclaw/workspace/SOUL.md` after configuration.
- Local plugin: `integrations/openclaw/cyrene-plugin/`.
- `OpenClaw.cmd <arguments>` runs the CLI with this profile, without changing your global OpenClaw configuration. For example: `OpenClaw.cmd plugins list`.

Additional plugins can be installed/enabled in this profile with the normal OpenClaw CLI. The runtime supports its normal plugins; they are not all installed or connected automatically. This profile exposes the normal full tool profile and has no external messaging channels configured.

Open-LLM-VTuber relays the current user message to OpenClaw and streams response text verbatim. It does not initialize a conversation agent, ASR/VAD, translation, MCP tool loop or persona prompt. It does not trim the submitted text, capture media on send, split sentences, interpret expression tags, inject system messages, or replay local history into a model request. OpenClaw owns context, instructions, tool execution, session compaction and memory.

Each UI conversation maps to an explicit `x-openclaw-session-key: agent:cyrene:desktop:<history_uid>`. Reopening a UI conversation reuses its OpenClaw session; creating a new conversation selects a new session. The app resumes the last selected conversation on reconnect/relaunch. Its saved transcript is a display cache only; deleting a local transcript does not erase OpenClaw's own session records. Old pre-relay transcripts remain viewable but are not imported into new agent sessions.

User input is forwarded as `{"model":"openclaw/cyrene","stream":true,"messages":[{"role":"user","content":"<exact draft>"}]}`. The gateway emits SSE; the UI receives `chat.started`, `chat.delta` and `chat.finished` with the same turn ID. Responses and partial responses are retained unchanged. Stop closes the upstream HTTP stream, triggering OpenClaw's client-disconnect abort signal. A second input or thread change is rejected while the current turn runs; there are no silent input queues or automatic retries.

Drag files onto the pet/window or use the paperclip in either input panel. Electron supplies absolute paths, which are visibly JSON-quoted and appended to the editable draft. Files are not uploaded, read, or automatically sent by dropping them. Shift+Enter adds a newline; Enter sends. OpenClaw can inspect those files using its normal local tools when the user sends the request.

For a fresh full setup, `scripts/setup_windows.py --with-openclaw` installs and configures this integration too. A plain setup retains the existing preview behavior/config.

Spoken replies are disabled by the user preference `character_config.tts_config.speech_enabled: false`. UI-only chat has no synthesis stage. This also disables synthesis for explicit speech commands and converts `speech.say` to text even when a caller requests `speak:true`; its receipt reports `speech_enabled:false`. Text, expressions and independent sound cues remain available. Set this preference to `true` and restart the app to restore voice.

## REST and events

Base URL: `http://127.0.0.1:12393/api/cyrene`. All endpoints except `/health` require `Authorization: Bearer <token>`. The token is created by the backend in `tmp/cyrene-control/token`. Keep it in the caller's local configuration, not in a prompt or committed file. Both servers bind to loopback. Desktop registration also requires the control token; the packaged app obtains it through its local preload bridge, so an anonymous legacy chat connection cannot claim the active pet.

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Backend availability and registered client count |
| `GET /state` | Clients/readiness, layout, expressions, task leases, capabilities, event cursor and epoch |
| `POST /commands` | Send a validated command |
| `GET /events?after=0&wait=25` | Replay/long poll, `wait` 0–30 seconds |
| `WS /events/ws?after=0` | Same batches over a WebSocket; send the bearer header during the handshake |

Command envelope:

```json
{
  "name": "expression.set",
  "data": { "name": "wink", "duration_ms": 3000 },
  "source": "my-automation",
  "request_id": "unique-retry-key",
  "client_id": "optional-explicit-desktop-id"
}
```

Omitting `client_id` targets the most recently registered client. Use an explicit ID when multiple clients are running. `GET /state` reports `ready:true` after model textures load. A command receipt means **accepted/dispatched**, not completed. `command.applied` or `command.failed` carries the same `command_id` after the renderer handles it. Speech has its own playback lifecycle; applying/enqueuing speech is not playback completion. Backend-only input commands emit input/conversation events instead of renderer acknowledgements. Task/expression state can be set without a connected pet and is included in its next state snapshot; transient presentation commands require a client to take effect.

Repeated identical `request_id` values return the prior receipt; changing the command under the same ID returns HTTP 409. The last 256 receipts are retained in memory. There are no automatic command retries after a backend restart.

| Command | `data` |
| --- | --- |
| `input.submit` | `{ "text": "..." }` sends chat through the **active desktop's** agent session |
| `input.event` | `{ "event": "download.completed", "payload": {...}, "invoke_agent": false }` records a structured event; set `invoke_agent:true` to run the agent; optional `prompt` is forwarded unchanged, otherwise event name/payload are serialized as JSON |
| `expression.set` | `{ "name": "happy", "duration_ms": 5000 }` overrides the idle expression for a bounded time |
| `speech.say` | `{ "text": "...", "expression": "happy", "speak": true }` uses configured TTS and Live2D lip sync; `speak:false` is silent text |
| `subtitle.set` | `{ "text": "...", "duration_ms": 8000 }` shows a notification without running an LLM |
| `task.start` | `{ "task_id": "download-123", "label": "Downloading", "progress": 0, "timeout_ms": 300000 }` |
| `task.progress` | `{ "task_id": "download-123", "label": "Processing", "progress": 0.5 }` renews the lease |
| `task.end` | `{ "task_id": "download-123", "status": "completed" }`; status can also be `failed` or `cancelled` |
| `ui.visibility` | `{ "visible": true }` shows/hides the desktop without stealing focus |
| `layout.set` | `{ "matrix": [16 numbers] }`; use the current client layout as a starting point; changes persist normally |
| `interrupt` | `{}` cancels active conversation/synthesis and clears/stops desktop audio |

Expressions: `neutral`, `happy`, `playful`, `blush`, `star_eyes`, `cry`, `hurt`, `angry`, `sweat`, `confused`, `wink`. Expression durations default to 5 seconds, captions to 8 seconds; maximum is 1 hour. Zero duration means no persistent override. Task progress is 0–1. Tasks have 5-minute leases by default (1 second to 1 hour allowed), keep the pet awake independently, and expire when abandoned. Ending one task does not end another. At most 100 tasks are retained.

Key output events:

- `client.connected`, `client.ready`, `client.disconnected`
- `command.accepted`, `command.dispatched`, `command.applied`, `command.failed`
- `input.event`, `input.received`, `input.audio`, `input.focused`, `input.blurred`
- `output.delta` (verbatim streamed text), `output.completed` (full text and terminal status); legacy presentation also emits `output.text`
- `speech.synthesizing`, `speech.ready`, `speech.started`, `speech.finished`, `speech.failed`, `speech.cancelled`
- `task.started`, `task.progress`, `task.completed`, `task.failed`, `task.cancelled`, `task.expired`
- `pet.awake`, `pet.sleeping`, `layout.changed`, `ui.visibility`

Events contain `id`, `type`, Unix `time`, `data`, and applicable `client_id`, `command_id` or `conversation_id`. Store the returned cursor and request events after it. The in-memory replay ring retains 512 events. `gap:true` means older events were dropped; reconcile with `/state`. `epoch` changes on backend restart; `reset:true` handles a cursor beyond the new sequence. Reconcile state on any epoch change. The desktop reconnects with bounded backoff after backend loss and restores the current state snapshot. It releases external activity holds while disconnected. The event stream contains conversation text, so treat its local token like a private credential.

External events are **not** fed back into OpenClaw automatically; `invoke_agent` is explicit to prevent event loops. A busy conversation returns 409 for another input; callers should queue or interrupt deliberately. No keylogging, browser click interception, or global screen monitoring is installed.

## Application-owned sleep and expressions

`pet.wake` and `pet.sleep` are no longer accepted commands, and `sleep` is reserved for the app. Hover, focus, an unsent draft, a running conversation/task, explicit notification display and playback hold the pet awake. After those holds end it returns to sleep after five seconds.

An agent expression never wakes the pet. While awake it can display a temporary agent expression. Starting a task clears the previous expression. Completing the final task replaces it with a three-second application reaction (`happy`, `hurt` for failure, `neutral` for cancellation); this reaction overrides new agent expressions until it expires. Ending one task never releases another task's hold or shows a final completion reaction while another task is running. Expired task leases release their hold and clear stale expressions. Sleep always overrides agent expressions. `state.clients` reports observed `sleeping` state; agents report tasks and let the app decide presentation.

## CLI and automation

```powershell
python scripts/cyrene_control.py state
python scripts/cyrene_control.py send expression.set --file expression.json
python scripts/cyrene_control.py watch
```

Use `--file payload.json` for complex command data to avoid Windows JSON quoting issues:

```json
{ "task_id": "example", "label": "Working", "progress": 0 }
```

```powershell
python scripts/cyrene_control.py send task.start --file payload.json
```

Python callers can import `request` from `scripts/cyrene_control.py`; the helper reads the token locally.

`integrations/examples/download_watcher.py` is an optional foreground adapter. It emits `download.completed` after a new/changed file has stayed unchanged for six seconds, ignores files present at startup and common partial-download extensions, and sends metadata only. File stability is a heuristic, not a browser-confirmed completion signal.

```powershell
python integrations/examples/download_watcher.py
python integrations/examples/download_watcher.py --invoke-agent
```

It starts only when explicitly run and stops with Ctrl+C. Other event sources, such as a browser extension or an existing automation service, can send the same `input.event` envelope.

## OpenClaw plugin and MCP

OpenClaw tools: `cyrene_state`, `cyrene_control`, `cyrene_events`. Plugin hooks map `before_agent_run` → task start, `before_tool_call` → task progress, and `agent_end` → completed/failed. They are scoped to agent `cyrene`, use run IDs, and have a 4-second network timeout. A missing pet/API cannot block the assistant indefinitely. Ordinary chat is already displayed by the UI; the plugin instructs the agent not to duplicate it with `speech.say`.

Other MCP clients can run the stdio adapter below; replace the two absolute paths for your checkout:

```json
{
  "mcpServers": {
    "cyrene": {
      "command": "C:/path/cyrene-desktop/Open-LLM-VTuber/.venv/Scripts/python.exe",
      "args": ["C:/path/cyrene-desktop/integrations/cyrene-mcp/server.py"]
    }
  }
}
```

It exposes `cyrene_state`, `cyrene_command`, and `cyrene_events`. The backend/pet must already be running. OpenClaw uses its native plugin, so it does not need a second MCP connection to the pet.

## Verification

Run `npm.cmd test`, `npm.cmd run test:control`, `npm.cmd run test:startup`, `npm.cmd run typecheck:comparison`, and `npm.cmd --prefix Open-LLM-VTuber-Web run typecheck:node`. The backend suite covers verbatim forwarding, prompt/history exclusion, session routing, partial responses, cancellation, stream failures and cold-start engine bypass. Pet/plugin tests cover sleep priority, task reactions, concurrent task holds, lease expiry, HTTP-disconnect cancellation and visible file paths.

Live packaged-app checks verified exact multiline/whitespace input, two-turn memory through OpenClaw, absolute paths from real Chromium files through Electron webUtils, drop-without-send behavior, task/expression priority, return to sleep, microphone blocking and actual gateway cancellation. Plain replies bypass speech entirely; explicit speech commands still honor the disabled-voice preference.

The upstream renderer has existing diagnostics; the comparison checks for new ones. Build with `npm.cmd run build`, package with `npm.cmd run package`. Quit the packaged desktop before overwriting `release/interface/win-unpacked`.

Official contracts used: [OpenClaw plugin SDK](https://docs.openclaw.ai/plugins/building-plugins), [hook reference](https://docs.openclaw.ai/plugins/hooks/reference), [OpenAI-compatible gateway](https://docs.openclaw.ai/gateway/openai-http-api).
