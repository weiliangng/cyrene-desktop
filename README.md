# Cyrene Desktop

Private Windows desktop companion combining a customized Open-LLM-VTuber desktop client, its Python backend, and the user's Cyrene Live2D model.

## Run locally

Double-click **Start Cyrene Desktop.cmd**. Cyrene starts in transparent pet mode, asleep. Hover her to wake her; she returns to sleep after five seconds away from the model and text box. Input focus, an unsent message, or an active conversation keeps her awake. Position and size are automatically remembered after dragging or resizing, and restored on startup. Preferences are mirrored to `tmp/cyrene-desktop-state/pet-layout.json`. The lavender text box fades/slides with wake and sleep. Its header can be dragged. Use the expression dropdown for facial presets, or type in the input for keyboard tapping.

After a reboot, OpenClaw may need to recover interrupted sessions. The launcher waits up to four minutes, reports progress, and reuses a gateway that is already starting. Overlapping launches wait on an OS lock instead of starting duplicate gateway/backend processes.

Spoken replies are disabled (`character_config.tts_config.speech_enabled: false` in the local config). Replies and notifications remain text, expressions remain active, and independent sound cues are available.

Right-click Cyrene or the tray icon to change modes, toggle input visibility or mouse passthrough, and exit. The original watermark-hiding preset and the heart-layer corrections remain applied. The original model ZIP is unchanged.

OpenClaw is available as a pinned, project-local runtime with a Cyrene plugin. **Start Cyrene with OpenClaw.cmd** configures chat through OpenClaw and SoCLaaS (`SOCLAAS_API_KEY` in the launch environment). A token-protected local control API and MCP adapter expose event input/output, expressions, speech/subtitles, task lifecycles, wake/sleep, visibility, layout and interruption. See [external connections and examples](docs/CONTROL-API.md). The committed preview configuration remains a credential-free starting point.

## First setup after cloning

Install Node.js/npm and uv, then double-click **Setup Cyrene.cmd**. It creates an isolated Python 3.12 environment, installs locked desktop/backend dependencies, restores FFmpeg and speech-recognition weights when needed, and builds the desktop app. Launch **Start Cyrene Desktop.cmd** afterward.

Equivalent commands from the repository root:

```powershell
uv run --no-project --python 3.12 scripts/setup_windows.py
npm run test
npm run build
npm run package
```

To include OpenClaw on a fresh setup, run `uv run --no-project --python 3.12 scripts/setup_windows.py --with-openclaw`. See the integration guide for the environment key and profile configuration.

Private credentials belong only in the ignored `Open-LLM-VTuber/conf.yaml` and `mcp_servers.json`. Setup initializes these from the committed preview examples and never overwrites an existing local configuration.

## Layout

| Path | Contents |
| --- | --- |
| `Open-LLM-VTuber-Web/` | React/Electron desktop source and custom pet behavior |
| `Open-LLM-VTuber/` | Python backend, prompts, configuration template and browser preview |
| `Open-LLM-VTuber/live2d-models/cyrene/` | Single source copy of the adapted model, textures and 33 expression presets |
| `scripts/` | Windows setup, control CLI, OpenClaw profile launcher and Cubism regression check |
| `integrations/` | Pinned OpenClaw runtime/plugin, persona templates, MCP adapter and optional event examples |
| `runtime-downloads.json` | Upstream versions and speech-model download/hash |

The two upstream projects are ordinary directories in this one Git repository: no nested repositories or Git submodules. The desktop build copies Cyrene assets from the backend's model directory into its packaged resources. The Python backend stays a separate local process, launched automatically by the root launcher. Downloaded ASR weights, FFmpeg, dependencies, packaged executables, logs, caches and chat history are ignored rather than uploaded.

## Customize

- Idle timeout: `Open-LLM-VTuber-Web/src/renderer/src/pet/activity.ts`.
- Sleep/wake expressions: `Open-LLM-VTuber-Web/src/renderer/src/pet/use-cyrene-idle.ts`.
- Text box styling: `Open-LLM-VTuber-Web/src/renderer/src/components/electron/electron-style.tsx`.
- Layout and reveal animation: `Open-LLM-VTuber-Web/src/renderer/src/components/electron/input-subtitle.tsx`.
- Keyboard and hidden-layer parameters: `Open-LLM-VTuber-Web/src/renderer/src/pet/cyrene-runtime.ts`.
- Persona/LLM/voice: local `Open-LLM-VTuber/conf.yaml`.

More notes: [desktop changes](Open-LLM-VTuber-Web/CYRENE-LOCAL.md), [model setup](Open-LLM-VTuber/CYRENE-SETUP.md).

## Verification and provenance

The custom build compiled and launched successfully. Tests cover sleep, hover, timeout, text focus/drafts, conversations, repeated waking, keyboard mapping, and hidden model layers. Cubism checks load the actual moc3, verify facial presets and ensure the seven heart-overlay pieces stay hidden. Mouse behavior still needs visual verification.

The v1.2.1 upstream frontend has 585 TypeScript diagnostics; the customization introduced none in the baseline comparison. `npm run typecheck:comparison` compares against preserved original files in `Open-LLM-VTuber-Web/scripts/upstream-v1.2.1.json`. The Electron main-process typecheck passes independently.

Upstreams: [backend v1.2.1](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/tree/v1.2.1), [desktop v1.2.1](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber-Web/tree/v1.2.1). Their original licenses and Live2D license notices remain in their directories. The browser frontend is the supplied built v1.2.1 frontend plus local Cyrene preview changes; its corresponding editable UI source is included in the desktop project.

Cyrene assets are supplied by the user for private personal use. Keep this repository private. The model creator's notes are retained in the model directory; the software licenses do not grant redistribution rights to these character assets.
