# voice-macro

<img width="1942" height="809" alt="ChatGPT Image 22 de mai  de 2026, 19_24_13" src="https://github.com/user-attachments/assets/97165e1b-aca2-4e4a-9aca-cf7002013980" />


Local push-to-talk transcription and AI text processing for Windows. Speak → text appears in any active field, optionally refined by a large language model.

Transcription runs entirely on your GPU via [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (no internet required for DICTATE mode). LLM modes are optional and route through [OpenRouter](https://openrouter.ai) at minimal cost — typically less than $0.001 per operation.

---

## Requirements

| Component | Minimum | Notes |
|-----------|---------|-------|
| OS | Windows 10/11 64-bit | No Linux/macOS support |
| Python | 3.11+ | 3.12 recommended |
| GPU | NVIDIA with 4 GB+ VRAM | Compute Capability 6.1+ (GTX 10xx or newer) |
| CUDA | 12.x | Install from [nvidia.com/cuda](https://developer.nvidia.com/cuda-downloads) |
| Microphone | Any Windows-compatible input | — |
| OpenRouter API key | Optional | Required for CLEAN / SUMMARY / INSTRUCT / REFINE / ACTION / PLAN modes |

> **CPU fallback**: Change `device = "cuda"` to `device = "cpu"` in `config.toml`. Transcription will be significantly slower but functional.

---

## Quick Start

### Step 1 — Environment setup

```powershell
git clone https://github.com/orugian/voice-macro-agent.git
cd voice-macro-agent
python scripts/setup.py
```

`setup.py` creates the virtual environment, installs all dependencies, prompts for your OpenRouter API key (optional), and validates CUDA.

> **Note:** Run `setup.py` from a standard **PowerShell** or **cmd** window — not PowerShell ISE — so the API key prompt masks your input correctly.

### Step 2 — Create shortcuts and configure auto-start

After the environment is ready, double-click **`setup.bat`** in the project root. It will:

1. Generate the dragon tray icon (`assets/icons/voice-macro.ico`) if not yet present
2. Create a **Desktop shortcut** and a **Start Menu entry** (`voice-macro.lnk`)
3. Register voice-macro to **start automatically with Windows** (disabled by default — no VRAM used until you activate)

> To pin to the taskbar: `Win+S` → type `voice-macro` → right-click → **Pin to taskbar**.

### Manual setup (alternative to setup.bat)

```powershell
# Virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Dependencies
pip install -r requirements.txt

# API key (for LLM modes — skip if DICTATE-only)
copy .env.example .env
# Edit .env: OPENROUTER_API_KEY=sk-or-...

# Launch directly
.venv\Scripts\python.exe main.py
# or double-click launch.bat
```

The STT model (~1.5 GB) downloads automatically on first activation and is cached locally.

---

## Usage

| Step | Action | Tray icon |
|------|--------|-----------|
| 1 | Left-click tray icon to enable | Dark dragon → loading → lit dragon |
| 2 | Hold **Ctrl+Shift+R**, speak, release | Lit dragon → pulsing → still → lit |
| 3 | Text appears in whatever field is focused | — |

Right-click the tray icon to switch modes or exit.

### Tray icon states

The tray icon is a pixel-art dragon with two visual variants: **dark** (inactive) and **lit** (active). An on-screen HUD overlay mirrors the current state while recording.

| State | Dragon | Meaning |
|-------|--------|---------|
| `disabled` | Dark / gray | STT model not loaded — VRAM is completely free |
| `loading` | Lit (static) | Loading model into VRAM (~3–15 s depending on cache) |
| `idle` | Lit (static) | Ready, waiting for push-to-talk |
| `recording` | Lit (pulsing) | Capturing audio |
| `processing` | Lit (static) | Transcribing / calling LLM |
| `done` | Lit (static) | Text injected successfully |
| `error` | Dark / gray | See `voice-macro.log` for details |

After each successful transcription, a **Windows toast notification** appears showing the injected text. Requires `winotify`, included in `requirements.txt`.

> **VRAM note:** disabling the tool via the tray icon (`disabled` state) fully unloads the STT model and frees all VRAM. The background process uses only ~60–80 MB of RAM and zero GPU memory while inactive.

### Custom tray icon

Place your own images in `assets/icons/` before first run (or delete the generated files to regenerate):

| File | Used when |
|------|-----------|
| `dragon_off.png` | App disabled or error |
| `dragon_on.png` | App active (all non-disabled states) |

Both files are auto-cropped and resized to fill the tray slot. Transparent backgrounds (RGBA) are supported. If neither file is present, a programmatic fallback icon is generated.

---

## Modes

Select via right-click → **Modo** submenu. The selected mode applies to the next recording.

| Mode | LLM call | Description |
|------|----------|-------------|
| **DICTATE** | No | Raw transcription. Text appears exactly as spoken, with VAD silence filtering. |
| **CLEAN** | Yes | Removes verbal fillers (*"tipo"*, *"né"*, *"hmm"*), fixes punctuation and capitalisation. |
| **SUMMARY** | Yes | Converts speech into structured bullet points (max 8). |
| **INSTRUCT** | Yes | Transforms spoken procedures into numbered, imperative instructions. |
| **REFINE** | Yes | Rewrites with professional clarity, improves argument structure, preserves intent and voice. |
| **ACTION** | Yes | Extracts tasks, decisions, responsible parties, and deadlines from meeting-style speech. |
| **PLAN** | Yes | Structures a verbal idea or objective into an actionable project plan with steps, risks, and next actions. |

---

## Configuration

All settings live in `config.toml`. Changes take effect on next app restart.

```toml
[hotkey]
combination = "ctrl+shift+r"    # push-to-talk hotkey

[stt]
model        = "large-v3-turbo" # whisper model (see docs/ARCHITECTURE.md)
device       = "cuda"           # "cuda" | "cpu"
compute_type = "float16"        # "float16" (>=4 GB VRAM) | "int8_float16" (2-4 GB)
language     = ""               # "" = auto-detect | "pt" | "en" | etc.

[llm]
model       = "google/gemini-2.5-flash-lite"  # OpenRouter model ID
max_tokens  = 1500
temperature = 0.3

[audio]
samplerate           = 16000   # Hz — whisper requires 16 kHz; do not change
channels             = 1       # mono
max_duration_seconds = 60

[app]
default_mode                  = "DICTATE"
start_enabled                 = false   # true = auto-activate STT on launch
log_level                     = "INFO"  # DEBUG | INFO | WARNING | ERROR
delete_audio_after_processing = true
sounds_enabled                = true    # system sounds on state change
hud_enabled                   = true    # on-screen HUD overlay while recording
```

### Changing the hotkey

Edit `combination` in `config.toml`. Format: modifier keys joined by `+`, followed by the trigger key.

```toml
combination = "ctrl+shift+r"   # default
combination = "ctrl+alt+r"     # alternative (avoid in VNC/RDP sessions)
combination = "f9"             # single key
```

### Auto-start with Windows

**Recommended:** run `setup.bat` (covers shortcuts + auto-start in one step).

**Manual:**

```powershell
# Install — registers voice-macro in the user's Startup folder
.venv\Scripts\python.exe scripts\setup_windows_startup.py

# Remove
.venv\Scripts\python.exe scripts\setup_windows_startup.py --remove
```

The app starts in the **disabled** state regardless of `start_enabled` — the STT model is not loaded until you left-click the tray icon, so VRAM stays free at login.

To auto-activate the STT model at launch (loads VRAM immediately on startup), set `start_enabled = true` in `config.toml`.

---

## Privacy

- Audio is captured in memory and **never written to disk**.
- The STT model runs locally on your GPU — **no audio leaves your machine**.
- Transcription text is not logged (only character count and language are recorded).
- LLM modes (CLEAN, SUMMARY, etc.) send only the **transcribed text** (not audio) to OpenRouter.
- To use the app with zero network calls, stay in DICTATE mode and omit the API key.

---

## Troubleshooting

### Tray icon doesn't turn red when holding the hotkey

The hotkey is not being detected by pynput.

- **VNC / RDP session**: `Ctrl+Alt` combinations are often intercepted by the remote client before reaching Windows. Use `ctrl+shift+r` instead (the default).
- **Hotkey conflict**: Another application may have registered the same shortcut. Change `combination` in `config.toml`.
- **Debug**: Run `scripts/debug_keys.py` to see which key events pynput actually receives.

### Empty transcription (no text appears)

1. Check `voice-macro.log` for a line like `STT [pt] 0 chars in X.XXs`. Zero chars = VAD filtered everything as silence.
2. Run `scripts/debug_audio.py` to verify your microphone is detected and has signal above 0.01.
3. Speak closer to the microphone or increase input volume in Windows Sound settings.

### CUDA error on startup

| Error | Fix |
|-------|-----|
| `cublas64_12.dll not found` | `main.py` handles this automatically. Ensure the venv is at `.venv/` inside the project root. |
| `CTranslate2 not compiled with CUDA` | Reinstall: `pip install --force-reinstall ctranslate2` |
| `CUDA out of memory` | Change `compute_type = "float16"` to `"int8_float16"` in `config.toml` |

### SSL / certificate errors

`truststore` is included in `requirements.txt`. Run `pip install truststore` inside the venv if the error persists.

### LLM modes produce no output or error

1. Confirm `OPENROUTER_API_KEY` is set in `.env`.
2. Check `voice-macro.log` for `LLM processing error`.
3. Verify the model ID in `config.toml` is valid on [openrouter.ai/models](https://openrouter.ai/models).

### setup.bat fails or shortcut not created

- Ensure `scripts/setup.py` was run first and `.venv\Scripts\python.exe` exists.
- The shortcut target path is read from the Windows registry (`Shell Folders`) to handle OneDrive and custom Desktop locations automatically.
- Run `scripts/create_shortcut.py` directly for verbose output.

---

## Project Structure

```
voice-macro/
├── app/
│   ├── audio/capture.py          # sounddevice InputStream -> numpy array
│   ├── config/settings.py        # config.toml + .env loader
│   ├── injection/injector.py     # clipboard paste + pynput fallback
│   ├── llm/client.py             # OpenRouter wrapper (openai SDK)
│   ├── logging/logger.py         # file + console logging setup
│   ├── modes/processors.py       # mode dispatcher -> LLM
│   ├── orchestration/
│   │   └── orchestrator.py       # event loop + pynput PTT listener
│   ├── stt/transcriber.py        # faster-whisper wrapper (lazy VRAM loading)
│   ├── tray/tray_icon.py         # pystray icon (pixel-art dragon, 7 states)
│   └── ui/hud.py                 # on-screen HUD overlay (recording indicator)
├── assets/
│   └── icons/                    # tray icon sources and generated cache
│       ├── dragon_off.png        # custom icon: app disabled (replace to customise)
│       ├── dragon_on.png         # custom icon: app active  (replace to customise)
│       └── voice-macro.ico       # multi-size ICO used by shortcuts (auto-generated)
├── docs/
│   ├── PLAN.md                   # implementation plan (all phases)
│   └── ARCHITECTURE.md           # technical reference for contributors
├── prompts/                      # system prompts for each LLM mode
│   ├── clean.txt
│   ├── summary.txt
│   ├── instruct.txt
│   ├── refine.txt
│   ├── action.txt
│   └── plan.txt
├── scripts/
│   ├── setup.py                  # guided setup for new users (recommended first step)
│   ├── create_shortcut.py        # creates Desktop + Start Menu .lnk shortcuts
│   ├── setup_windows_startup.py  # configure auto-start at Windows login
│   ├── debug_keys.py             # diagnose hotkey detection
│   ├── debug_audio.py            # diagnose microphone
│   ├── debug_inject.py           # diagnose text injection
│   └── validate_cuda.py          # validate CUDA + faster-whisper
├── .env.example                  # API key template
├── config.toml                   # all user-facing configuration
├── launch.bat                    # double-click launcher (no terminal needed)
├── setup.bat                     # one-click: create shortcuts + configure auto-start
├── voice-macro.spec              # PyInstaller build spec (produces standalone .exe)
├── main.py                       # entrypoint
└── requirements.txt
```

---

## Building a standalone executable (optional)

A PyInstaller spec is included for users who want a self-contained `.exe` (no Python installation required on the target machine):

```powershell
pip install pyinstaller
pyinstaller voice-macro.spec
```

Output: `dist/voice-macro/voice-macro.exe` (~300 MB folder, models downloaded separately on first run).

> Run the app at least once before building so `assets/icons/voice-macro.ico` is generated.

---

## License

MIT — see [LICENSE](LICENSE) for details.
