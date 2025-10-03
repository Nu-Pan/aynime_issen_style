# Agent Manifest

## Overview
- Windows-only CustomTkinter tool for capturing still and animated frames from streaming windows and preparing them for Discord-ready delivery.
- Architecture is model-driven: capture context provides raw frames, cache models manage derived assets, and CTk frames act as agents that react to model updates.

## Agent Map
| Agent | Responsibility | Primary modules |
| --- | --- | --- |
| Application shell | bootstraps the UI, enforces single-instance, mounts feature tabs | src/gui/main.py, src/gui/aynime_issen_style_app.py |
| Capture context | enumerates candidate windows and streams pixels via DXGI and dxcam | src/utils/capture_context.py, src/utils/capture_context_windows.py |
| Model and cache | stores raw/derived images, drives resize/export pipelines, issues notifications | src/gui/model/aynime_issen_style.py, src/gui/model/contents_cache.py |
| Window selection | lets the user pick a capture source and preview it | src/gui/frames/window_selection_frame.py, src/gui/widgets/still_label.py |
| Still capture | captures single frames, resizes, exports, and imports via drag and drop | src/gui/frames/still_capture_frame.py, src/gui/widgets/size_pattern_selection_frame.py |
| Animation capture | records sequences, edits timelines, deduplicates frames, exports GIF/ZIP | src/gui/frames/animation_capture_frame.py, src/gui/widgets/animation_label.py, src/gui/widgets/thumbnail_bar.py |
| System integration | clipboard, hotkeys, per-monitor capture, PyInstaller glue | src/utils/windows.py, src/utils/pyinstaller.py |
| Telemetry and metadata | logging, version disclosure, constants, release metadata | src/utils/logging.py, src/gui/frames/version_frame.py, src/utils/constants.py |

## Application shell (src/gui/main.py, src/gui/aynime_issen_style_app.py)
- `src/gui/main.py` sets the CustomTkinter theme, acquires a system wide mutex via `SystemWideMutex` to prevent multiple instances, installs logging with `setup_logging`, logs `COMMIT_HASH` and `BUILD_DATE` from `src/utils/version_constants.py`, and enters the main loop.
- `src/gui/aynime_issen_style_app.py` subclasses both `ctk.CTk` and `TkinterDnD.DnDWrapper`, loads fonts and window metadata, instantiates the shared `AynimeIssenStyleModel`, and wires four tabs: window selection, still capture, animation capture, and version info. Each tab owns its agent frame and shares the model instance.

## Capture context agent (src/utils/capture_context.py, src/utils/capture_context_windows.py)
- The abstract `CaptureContext` interface in `src/utils/capture_context.py` defines the surface for enumerating windows, choosing a target, streaming frames, and releasing DX resources.
- `CaptureContextWindows` implements that surface with Win32 APIs plus `dxgi_probe` and `dxcam_cpp`. It sanitizes window titles via `get_nime_window_text`, promotes titles tagged with `<NIME>`, and falls back to raw titles when sanitization fails.
- Monitor detection is refreshed when the selected window or elapsed time invalidates cached metadata; the agent matches Win32 monitor handles with DXGI adapters and outputs, re-creating the `dxcam` camera as needed and discarding the first all-black grab.
- `capture()` returns an `AISImage` wrapper so downstream agents can request resized variants without re-encoding. The agent also caches the latest frame in case dxcam yields `None`.

## Model and cache agents (src/gui/model/aynime_issen_style.py, src/gui/model/contents_cache.py)
- `AynimeIssenStyleModel` holds the live `CaptureContextWindows` plus three cache models: `window_selection_image`, `still`, and `video`, and tracks the active `PlaybackMode`.
- `src/gui/model/contents_cache.py` supplies the heavy lifting: `CachedContent` manages dirty propagation, `ImageModel` and `VideoModel` manage layered representations (`RAW`, `NIME`, `PREVIEW`, `THUMBNAIL`) and notify handlers, and edit-session helpers (`ImageModelEditSession`, `VideoModelEditSession`) batch updates while emitting model notifications only once.
- Resizing is centralized through `ResizeDesc` descriptors; applying a new size on a layer triggers re-rendering using PIL, producing PhotoImage objects that UI widgets can bind directly.
- Persistence helpers `save_content_model` and `load_content_model` bridge between cache models and disk. Still captures become PNG pairs under `nime/` and `raw/`, while animations generate GIF output plus optional zipped raw frames, all named with encoded `<NIME>` titles and timestamp pairs.
- Utility functions such as `current_time_stamp`, `decode_valid_nime_name`, and SSIM-based helpers support consistent timestamping and duplicate detection.

## Window selection agent (src/gui/frames/window_selection_frame.py, src/gui/widgets/still_label.py)
- `WindowSelectionFrame` maintains a `CTkListbox` of visible windows from `CaptureContextWindows.enumerate_windows()`, prioritizing titles tagged with `<NIME>` and exposing a manual reload action so the user can refresh after changing focus.
- Selecting a list item updates the model's capture target, triggers a capture attempt, and writes the resulting preview into `model.window_selection_image` via `ImageModelEditSession`.
- The east panel uses `StillLabel` to show the scaled preview (`ImageLayer.PREVIEW`) and mirrors the full sanitized title. `StillLabel` listens for preview changes and converts model updates into label image swaps, and pushes resize events back into the model so the preview layer keeps the correct aspect ratio.

## Still capture agent (src/gui/frames/still_capture_frame.py)
- Clicking the preview label or pressing the global `Ctrl+Alt+P` hotkey (provided by `register_global_hotkey_handler` in `src/utils/windows.py`) takes a fresh capture, resolves the `<NIME>` name override, and commits it through `ImageModelEditSession`.
- The integrated `SizePatternSelectionFrame` lets the user pick aspect ratio and target resolution presets; changing either writes a new `ResizeDesc` for the destination layer, which cascades into new preview and export surfaces.
- `export_image()` persists the current still capture via `save_content_model` and places the exported file path on the clipboard with `file_to_clipboard`, while `show_notify` gives inline confirmation.
- Drag-and-drop support accepts a single `.png`, `.gif`, or raw zip created by the app, rehydrates it through `load_content_model`, and seeds the still model with the imported raw image, name, and timestamp.
- The agent resets the model when the override entry is cleared, defaulting the `<NIME>` label to the active capture window when available.

## Animation capture agent (src/gui/frames/animation_capture_frame.py, supportive widgets)
- The output panel combines the live `AnimationLabel` preview, name override entry, aspect/size selectors, playback mode radio buttons, a GIF frame-rate slider backed by `GIF_DURATION_MAP`, and a SAVE button that delegates to `save_content_model` and then sends the GIF path to the clipboard.
- `AnimationLabel` drives playback entirely from model state: it loops, reverses, or reflects according to `model.playback_mode`, skips disabled frames, and adjusts its own preview size when the widget is resized.
- The input panel exposes the `ThumbnailBar` with per-frame `ThumbnailItem` controls. Left-click toggles enablement, right-click deletes frames, and a sentinel row advertises drag-and-drop. As the widget resizes, it updates the thumbnail resize descriptor in the model.
- Recording controls schedule repeated `_record_handler` callbacks that call `model.capture.capture()` every 10 ms, deduplicate identical consecutive frames, and append the collected images once the requested duration (0.5 s to 3.0 s in 0.1 s steps) elapses.
- A duplicate pruning slider maps a custom seed scale to high-precision SSIM thresholds; pressing `DISABLE DUPE` runs pairwise SSIM (`calc_ssim` from `src/utils/image.py`) against the previous enabled frame and disables frames above the threshold. Additional controls mass-enable, mass-disable, purge disabled frames, or wipe the sequence.
- The drag-and-drop handler imports previous exports (GIF or raw ZIP) via `load_content_model`, repopulating frames, enable flags, duration, and metadata in a single `VideoModelEditSession`.

## System integration agents (src/utils/windows.py, src/utils/pyinstaller.py)
- `src/utils/windows.py` centralizes native integration: enumerating DXGI outputs (`enumerate_dxgi_outputs`), sending paths to the Windows clipboard (`file_to_clipboard`), wiring global hotkeys through a message-only window and Tk-safe queue (`register_global_hotkey_handler`), and guarding against double launch with `SystemWideMutex`.
- `src/utils/pyinstaller.py` hides the details of PyInstaller resource lookup so the app icon and other assets resolve correctly whether the app runs from source or a frozen build.
- `src/utils/constants.py` defines shared paths (`nime/`, `raw/`, `log/`), window dimensions, and default font families used throughout the agents.

## Telemetry and metadata agents (src/utils/logging.py, src/gui/frames/version_frame.py)
- `setup_logging` installs a midnight-rotating file handler under `log/latest.log`, mirrors stdout/stderr into the logger, captures `warnings`, hooks thread and asyncio exception handlers, and installs a Tk-specific exception hook that shows a dialog pointing to the log directory.
- The logging tee preserves console output when available, so standalone execution remains debuggable while builds still collect logs for support.
- `VersionFrame` lazily generates `src/utils/version_constants.py` when the file is missing (useful in development), loads the current `COMMIT_HASH` and `BUILD_DATE`, and renders author links, manual links, and promotional URLs inside a read-only `CTkTextbox` with clickable hyperlinks.

## Data products and folders
- Still exports land in `nime/` (processed PNG) and `raw/` (original capture) using the naming pattern `<encoded-nime-name>__<timestamp>.png`.
- Animated exports create a GIF in `nime/` and, when raw frames exist, a ZIP companion in `raw/` containing sequential PNGs suffixed with `_e` (enabled) or `_d` (disabled).
- Logs accumulate under `log/` with gzip-compressed rotations managed by `src/utils/logging.py`.

## Extending the agents
- To add another capture pipeline, instantiate the new agent inside `AynimeIssenStyleApp` and give it the shared `AynimeIssenStyleModel`; reuse the edit-session helpers so downstream widgets receive consistent notifications.
- Platform-specific changes should extend `CaptureContext` and `src/utils/windows.py` rather than altering UI agents; this keeps window selection and capture logic abstracted.
- Any new persistence format should plug into `save_content_model` and `load_content_model` so both still and animation agents automatically gain the capability.
