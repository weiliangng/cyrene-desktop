# Cyrene Desktop local build

Based on official Open-LLM-VTuber-Web v1.2.1, commit 7a2e214c3f266c294541127520dab7fce46787e7.

Start from `../Start Cyrene Desktop.cmd`. This starts the existing local Python backend and opens the custom desktop client directly in pet mode. Right-click Cyrene or its tray icon for Window Mode, input/subtitle visibility, mouse passthrough, and Exit.

The model starts sleeping. Hover the visible model to wake her. After the pointer leaves both the model and input panel, she sleeps again after five seconds. Input focus, an unsent message, listening, or an active conversation keeps her awake. The input panel fades/slides in while awake and hides while asleep. Its position can be dragged from its header; controls and input do not start a drag.

The model and its 33 expression presets are included under the packaged application's `resources/live2d-models/cyrene` directory. A local `cyrene://assets/` protocol loads them without requiring the backend to serve the model. The Python backend remains separate and is still required for conversation, recognition and synthesis. LLM/OpenClaw is not configured yet.

The creator's watermark-hide preset is kept on. The heart motion is unregistered; its five layer parameters are pinned to their hidden value, -1, after physics and expressions every frame. The source ZIP is unchanged. Keyboard reactions now work inside the desktop message input, using the same verified mapping as the browser preview. The expression dropdown exposes the main facial presets. Nothing monitors keyboard input outside this application.

Local settings and renderer diagnostics live in `../tmp/cyrene-desktop-state/`, separate from the official app.

## Customize

- Idle delay and activity rules: `src/renderer/src/pet/activity.ts`.
- Sleep/awake expression selection: `src/renderer/src/pet/use-cyrene-idle.ts`.
- Text box appearance: `src/renderer/src/components/electron/electron-style.tsx`.
- Text box layout and reveal animation: `src/renderer/src/components/electron/input-subtitle.tsx`.
- Layer and keyboard parameter values: `src/renderer/src/pet/cyrene-runtime.ts`.
- Model defaults: `src/renderer/src/pet/cyrene-model.ts`.

## Rebuild

Run from this directory with Node/npm installed:

```text
npm.cmd ci
npm.cmd run build
node node_modules/electron-builder/cli.js --dir --win --x64 --publish never
```

Close the custom client before replacing a running build. Output: `release/local/win-unpacked/Cyrene Desktop.exe`.

Checks: `node scripts/test-cyrene.cjs`, `npm.cmd run typecheck:node`, and `node scripts/check-types.cjs`. The release's full frontend typecheck already has 585 diagnostics in its SDK/application code. The comparison script checks for added diagnostics instead of claiming the full check passes.

This is a private local build containing the user's model assets. Keep the creator's original notes and usage restrictions with the original ZIP; do not publish the packaged model or this build.
