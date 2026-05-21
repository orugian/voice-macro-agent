import sys
import os
from pathlib import Path

# Add nvidia CUDA DLL dirs to PATH before any import — ctranslate2 uses dynamic LoadLibrary
_venv_root = Path(__file__).parent.parent / ".venv" / "Lib" / "site-packages" / "nvidia"
if _venv_root.exists():
    _extra_paths = []
    for _cuda_pkg in _venv_root.iterdir():
        _bin = _cuda_pkg / "bin"
        if _bin.exists():
            _extra_paths.append(str(_bin))
            os.add_dll_directory(str(_bin))
    if _extra_paths:
        os.environ["PATH"] = os.pathsep.join(_extra_paths) + os.pathsep + os.environ.get("PATH", "")

import truststore

# Inject Windows certificate store into Python's ssl module (fixes httpx SSL on Windows)
truststore.inject_into_ssl()

import numpy as np

print(f"Python: {sys.version}")
print("Testando imports...")

import sounddevice
print(f"  sounddevice {sounddevice.__version__} OK")

import pystray
print(f"  pystray OK")

import keyboard
print(f"  keyboard OK")

import pynput
print(f"  pynput OK")

import pyperclip
print(f"  pyperclip OK")

print("\nCarregando modelo faster-whisper large-v3-turbo via CUDA...")
print("(primeiro uso faz download ~1.5GB para ~/.cache/huggingface/hub)")

from faster_whisper import WhisperModel

model = WhisperModel(
    "large-v3-turbo",
    device="cuda",
    compute_type="float16",
    num_workers=1,
)

print("Modelo carregado. Device: cuda, compute_type: float16")

# Transcrever silêncio sintético (0.5s de zeros)
silence = np.zeros(16000 // 2, dtype=np.float32)
segments, info = model.transcribe(
    silence,
    language=None,
    vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=500),
)
segment_list = list(segments)
text = " ".join(s.text for s in segment_list).strip()

print(f"Transcrição de silêncio: '{text}' (esperado: vazio)")
print(f"Idioma detectado: {info.language} ({info.language_probability:.2%})")
print("\nValidação CUDA concluída com sucesso.")
