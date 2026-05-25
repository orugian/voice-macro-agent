# voice-macro.spec — PyInstaller build spec
#
# ANTES DE USAR:
#   pip install pyinstaller
#   pyinstaller voice-macro.spec
#
# AVISO — CUDA:
#   O executável gerado inclui o app mas NÃO inclui os modelos do faster-whisper
#   (~1.5 GB, baixados em ~\.cache\huggingface\hub no primeiro uso).
#   Os DLLs CUDA (nvidia-cublas, nvidia-cudnn) são incluídos automaticamente
#   via collect_dynamic_libs abaixo.
#
# Resultado: dist/voice-macro/voice-macro.exe (one-folder, ~300 MB sem modelos)

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files
import sys

block_cipher = None

# Coleta DLLs CUDA das libs nvidia-* instaladas no venv
nvidia_binaries = collect_dynamic_libs("nvidia")

# Dados adicionais: prompts, config.toml e assets ficam ao lado do exe
# Nota: assets/icons/ é gerado na primeira execução do app;
#       rode o app uma vez antes de fazer o build para que o .ico exista.
added_datas = [
    ("prompts", "prompts"),
    ("config.toml", "."),
    (".env.example", "."),
    ("assets", "assets"),
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=nvidia_binaries,
    datas=added_datas,
    hiddenimports=[
        "pystray._win32",
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        "sounddevice",
        "winsound",
        "winotify",
        "truststore",
        "ctranslate2",
        "faster_whisper",
        "faster_whisper.transcriber",
        "faster_whisper.audio",
        "faster_whisper.vad",
        "faster_whisper.feature_extractor",
        "faster_whisper.tokenizer",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "tkinter", "PyQt5", "PyQt6", "wx"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="voice-macro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX quebra alguns DLLs CUDA — manter False
    console=False,      # sem janela de console
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icons/voice-macro.ico",   # gerado pelo app na primeira execução
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="voice-macro",
)
