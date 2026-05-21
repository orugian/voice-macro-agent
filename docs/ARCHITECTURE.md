# Architecture — voice-macro

Technical reference for contributors and developers.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  main.py  (entrypoint — main thread)                            │
│                                                                  │
│  ┌──────────────┐  ┌─────────────┐  ┌────────────────────────┐  │
│  │  AudioCapture│  │ Transcriber │  │      LLMClient         │  │
│  │  (sounddevice│  │(faster-     │  │  (OpenRouter / openai) │  │
│  │   InputStream│  │ whisper     │  │                        │  │
│  │   + queue)   │  │ lazy VRAM)  │  │                        │  │
│  └──────┬───────┘  └──────┬──────┘  └───────────┬────────────┘  │
│         │                 │                      │               │
│  ┌──────▼─────────────────▼──────────────────────▼────────────┐  │
│  │                    Orchestrator                             │  │
│  │  event_queue (Queue)  ←──────────────────────────┐        │  │
│  │  ┌──────────┐                                    │        │  │
│  │  │  pynput  │ on_press/on_release → PTT_START    │        │  │
│  │  │ Listener │                       PTT_STOP     │        │  │
│  │  │ (thread) │                       QUIT ────────┘        │  │
│  │  └──────────┘                                             │  │
│  │                                                           │  │
│  │  PTT_START → audio.start_recording()                      │  │
│  │  PTT_STOP  → audio.stop_recording()                       │  │
│  │             → stt.transcribe(audio)                       │  │
│  │             → [processors.process(mode, text, llm)]       │  │
│  │             → inject(text)                                │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  TrayIcon  (pystray, daemon thread)                        │  │
│  │  7 states: disabled / loading / idle / recording /         │  │
│  │            processing / done / error                       │  │
│  │  Left-click: toggle enable/disable (loads/unloads VRAM)    │  │
│  │  Right-click: mode submenu + quit                          │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Thread Model

| Thread | Owner | Role |
|--------|-------|------|
| Main | `orchestrator.run()` | Blocking event loop; all heavy work runs here |
| Tray | `pystray.Icon.run()` (daemon) | Win32 message loop for tray icon |
| pynput | `keyboard.Listener` (daemon) | OS keyboard hook; only enqueues events |
| Enable | spawned by `TrayIcon._on_toggle_enable` (daemon) | `transcriber.enable()` (~15 s blocking call) |

**Rule**: pynput callbacks must never do I/O or heavy computation. They only call `event_queue.put()`.

---

## Event Flow (PTT cycle)

```
User presses Ctrl+Shift+R
  → pynput on_press (callback, pynput thread)
    → _normalize_key() converts '\x12' or vk=82 → KeyCode('r')
    → _is_hotkey_complete() = True
    → event_queue.put("PTT_START")

Orchestrator.run() (main thread)
  → dequeues "PTT_START"
  → guard: stt.is_enabled? No → return (silently)
  → Yes → _recording = True
  → tray.set_state("recording")
  → audio.start_recording()

User releases Ctrl+Shift+R
  → pynput on_release (callback, pynput thread)
    → event_queue.put("PTT_STOP")

Orchestrator.run()
  → dequeues "PTT_STOP"
  → _recording = False
  → tray.set_state("processing")
  → audio = audio.stop_recording()    # numpy float32 1D 16 kHz
  → text, lang = stt.transcribe(audio)
  → if mode != DICTATE:
      text = processors.process(mode, text, llm_client)
  → inject(text)                      # clipboard + Ctrl+V
  → tray.set_state("done")
  → sleep(0.5)
  → tray.set_state("idle")
  → _drain_ptt_events()               # discard stale PTT events queued during processing
```

---

## Key Design Decisions

### Lazy VRAM loading
The STT model (~2 GB VRAM) is **not** loaded at startup. The user activates it via the tray icon when entering a work session. This allows the app to run permanently in the background without impacting gaming or other GPU-intensive tasks.

`Transcriber.enable()` is blocking and called in a dedicated thread to keep the tray responsive.

### Single event queue
All inter-thread communication flows through one `queue.Queue`: `PTT_START`, `PTT_STOP`, and `QUIT`. This avoids locks, race conditions, and complex threading coordination. The orchestrator's main loop is the only consumer.

### Key normalization
Windows sends different key representations when modifier keys are held:
- `Ctrl+R` arrives as `KeyCode(char='\x12')` — ASCII control character 18
- `Alt+R` arrives as `KeyCode(vk=82)` — virtual key code without char

`Orchestrator._normalize_key()` converts both to `KeyCode.from_char('r')` for reliable comparison.

### Clipboard injection
Text is injected via `pyperclip.copy() + keyboard.send("ctrl+v")` rather than `keyboard.write()`. This approach:
- Handles PT-BR accented characters correctly (keyboard.write() fails on non-ASCII)
- Works with all standard Windows applications
- Avoids the pynput Listener+Controller conflict (issue #438)

The `pynput Controller.type()` fallback is available for applications that block clipboard paste.

---

## Module Reference

### `app/config/settings.py`
Loads `config.toml` with Python's stdlib `tomllib` and `.env` via `python-dotenv`. Exposes the `CONFIG` dict at module level — imported everywhere.

**Note**: TOML 1.0 has no null type. Language auto-detect uses `language = ""` (empty string), treated as `None` in `Transcriber.transcribe()`.

### `app/audio/capture.py`
Uses `sounddevice.InputStream` with a callback that pushes frames into a `queue.Queue`. `start_recording()` creates a fresh queue to discard stale frames from previous sessions. `stop_recording()` drains the queue and concatenates chunks into a 1D float32 numpy array at 16 kHz.

### `app/stt/transcriber.py`
Wraps `faster_whisper.WhisperModel` with lazy loading. `enable()` loads the model into VRAM; `disable()` deletes the reference and calls `gc.collect()` to force immediate deallocation. The `is_enabled` property guards all PTT activity.

`list(segments)` is called before joining text — the faster-whisper generator is lazy and doesn't execute until iterated.

### `app/llm/client.py`
Thin wrapper around the `openai` SDK pointed at OpenRouter. The `process(system_prompt, text)` method is synchronous and blocking — called from the orchestrator's main thread.

### `app/modes/processors.py`
Maps mode name to a prompt file, lazy-loads prompts into a module-level cache. `process(mode, text, llm_client)` returns the original text for DICTATE, or the LLM-processed result for all other modes. Unknown modes fall back to DICTATE with a warning.

### `app/injection/injector.py`
Primary path: `pyperclip.copy(text)` → 50 ms settle → `keyboard.send("ctrl+v")`. Fallback: `pynput.keyboard.Controller().type(text)`. The `pynput` import is deferred inside `_inject_typing()` to avoid the Listener+Controller conflict on Windows.

### `app/tray/tray_icon.py`
All 7 icon images are pre-rendered as 64×64 RGBA PIL circles at startup. State transitions call `icon.icon` and `icon.title` setters — both are thread-safe (pystray posts Win32 messages internally). `get_current_mode()` is called by the orchestrator on each PTT_STOP.

### `app/orchestration/orchestrator.py`
The pynput `Listener` is started in `__init__` and runs in its own daemon thread. All callbacks are minimal: one `set.add()`, one `set.discard()`, one `_is_hotkey_complete()` check, and a `queue.put()`. The `run()` loop is the single point where all pipeline work happens.

`_drain_ptt_events()` discards queued PTT_START/PTT_STOP events after pipeline completion to prevent "ghost recordings" (a second transcription triggered by keys pressed during the first one).

---

## Model Selection

### STT models (faster-whisper)

| Model | VRAM | WER PT-BR | Speed | Notes |
|-------|------|-----------|-------|-------|
| `large-v3-turbo` | ~2 GB | Excellent | ~0.5–1 s | **Default. Best quality/speed ratio.** |
| `large-v3` | ~3 GB | Excellent | ~1–3 s | Marginally better quality, slower |
| `medium` | ~1.5 GB | Good | ~0.3 s | Noticeably lower PT-BR quality |
| `small` | ~0.5 GB | Fair | ~0.1 s | Acceptable for short commands only |

Change via `config.toml → [stt] model`.

### LLM models (OpenRouter)

For voice-macro operations, typical payload is 50–300 tokens in, 50–300 tokens out. At this scale, cost per operation is under $0.001 even for premium models.

| Model ID | Input $/1M | Output $/1M | PT-BR | Latency | Recommendation |
|----------|-----------|------------|-------|---------|----------------|
| `google/gemini-2.5-flash-lite` | $0.10 | $0.40 | Excellent | < 1 s | **Default — best balance** |
| `google/gemini-flash-1.5-8b` | $0.04 | $0.15 | Good | < 1 s | Budget alternative |
| `google/gemini-2.0-flash-001` | $0.10 | $0.40 | Excellent | < 1 s | Stable fallback |
| `mistralai/mistral-small-3.1-24b` | $0.10 | $0.30 | Good | 1–2 s | Strong multilingual |
| `meta-llama/llama-3.3-70b-instruct` | $0.12 | $0.30 | Good | 1–3 s | High quality, slower |
| `anthropic/claude-haiku-4.5` | $0.80 | $4.00 | Excellent | < 1 s | Overkill for this use case |

**Guidance**: `gemini-2.5-flash-lite` handles all six modes well in PT-BR. Switch to `gemini-flash-1.5-8b` for lower cost with acceptable quality. The `anthropic/claude-haiku-4.5` is 8× more expensive with no meaningful quality improvement for short voice-macro payloads.

Change via `config.toml → [llm] model`.

---

## Adding a New Mode

1. Create `prompts/mymode.txt` with the system prompt.
2. Add `"MYMODE": "mymode.txt"` to `_PROMPT_FILES` in `app/modes/processors.py`.
3. Add `"MYMODE"` to the `MODES` list in `app/tray/tray_icon.py`.
4. Restart the app.

No other changes required. The orchestrator routes any non-DICTATE mode through `processors.process()` automatically.

---

## Configuration Reference (complete)

```toml
[hotkey]
combination = "ctrl+shift+r"
# Format: modifier keys separated by "+", then trigger key.
# Modifiers: ctrl, shift, alt
# Trigger: any single character or function key (f1–f12)

[stt]
model        = "large-v3-turbo"
device       = "cuda"           # "cuda" | "cpu"
compute_type = "float16"        # "float16" | "int8_float16" | "int8"
language     = ""               # "" = auto-detect; "pt" | "en" | "es" | etc.

[llm]
model       = "google/gemini-2.5-flash-lite"
max_tokens  = 1000
temperature = 0.3               # 0.0 = deterministic, 1.0 = creative

[audio]
samplerate           = 16000   # must be 16000 (whisper requirement)
channels             = 1       # mono
max_duration_seconds = 60      # PTT safety limit

[app]
default_mode                  = "DICTATE"
start_enabled                 = false
log_level                     = "INFO"   # DEBUG | INFO | WARNING | ERROR
delete_audio_after_processing = true     # audio never persisted to disk
```
