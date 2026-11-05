# Cyrene preview

Open http://127.0.0.1:12393/cyrene-preview.html while the backend is running.

To start it again, double-click `Start Cyrene.cmd`. The launcher starts the backend in the background and opens the preview. Its process ID is recorded in `preview-server.pid`; logs are under `logs/`.

For the floating desktop client, double-click `../Start Cyrene Desktop.cmd` or `Start Desktop Pet.cmd`. Both now launch the custom source build at `../Open-LLM-VTuber-Web/release/local/win-unpacked/Cyrene Desktop.exe`, directly in Pet Mode. Cyrene starts asleep, wakes on model hover, and sleeps five seconds after activity stops. The lavender input panel animates with wake/sleep; focus, a draft, or a conversation keeps it awake. Keyboard animation also works in this desktop message input. The corrected model is bundled in the desktop build. See `../Open-LLM-VTuber-Web/CYRENE-LOCAL.md` for source and rebuild instructions. The original official client remains at `../Open-LLM-VTuber-Desktop/`. Right-click Cyrene or the tray icon for mode, input visibility, and Exit controls.

Open-LLM-VTuber v1.2.1 is installed here with an isolated Python environment. A portable FFmpeg binary is under `tools/ffmpeg/`; it is added to PATH only for the launched process. No VTube Studio installation is needed.

The supplied model ZIP remains unchanged. The adapted copy is under `live2d-models/cyrene/`, with ASCII paths, registered facial/keyboard expressions, a neutral reset expression, and the standard mouth parameter registered for lip sync. The creator's supplied watermark-hiding parameter is enabled throughout the preview and all expression presets. The heart motion is unregistered. Its five animation-layer parameters (`Param23`, `Param25`, `Param26`, `Param27`, `Param28`) are held at their model-defined hidden state of `-1`; zero would display the overlay layers.

The preview page uses the installed application's own Live2D renderer. Its side panel offers 11 facial presets plus neutral, keyboard tapping while typing in the preview text area, and a manual mouth-opening slider. The watermark is always hidden and the heart animation is disabled; neither has a preview control. Keyboard input is not monitored outside that field. Collaboration/AI chat is not configured; the LLM endpoint is left local with an explicit preview placeholder. MCP is disabled for preview.

The original application configuration is backed up as `conf.original.yaml`. The active model registration is in `model_dict.json`, with Cyrene selected in `conf.yaml`.

The private model assets are for personal use; keep the original creator's terms with them.
