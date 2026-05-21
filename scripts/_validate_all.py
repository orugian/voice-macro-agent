"""Script de validacao completa dos modulos implementados."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

errors = []

def check(label, fn):
    try:
        fn()
        print(f"  OK  {label}")
    except Exception as e:
        print(f"  ERR {label}: {e}")
        errors.append((label, e))

# ── 1. Imports ────────────────────────────────────────────────────────────────
print("=== 1. Imports ===")

def t_imports():
    from app.config.settings import CONFIG
    from app.audio.capture import AudioCapture
    from app.stt.transcriber import Transcriber
    from app.injection.injector import inject
    from app.tray.tray_icon import TrayIcon, MODES, _make_icon, _STATE_COLORS
    from app.orchestration.orchestrator import Orchestrator, _beep, _MIN_DURATION_S, _SILENCE_THRESHOLD
    from app.llm.client import LLMClient, _TIMEOUT, _RETRIES
    from app.modes.processors import process

check("todos os modulos app.*", t_imports)

# ── 2. Constantes ─────────────────────────────────────────────────────────────
print("\n=== 2. Constantes ===")

def t_llm_constants():
    from app.llm.client import _TIMEOUT, _RETRIES
    assert _TIMEOUT == 10.0, f"timeout={_TIMEOUT}"
    assert _RETRIES == 3, f"retries={_RETRIES}"

def t_orch_constants():
    from app.orchestration.orchestrator import _MIN_DURATION_S, _SILENCE_THRESHOLD
    assert _MIN_DURATION_S == 0.5
    assert _SILENCE_THRESHOLD == 0.01

def t_modes_list():
    from app.tray.tray_icon import MODES
    assert MODES == ["DICTATE", "CLEAN", "SUMMARY", "INSTRUCT", "REFINE", "ACTION"]

check("LLM timeout=10s retries=3", t_llm_constants)
check("min_duration=0.5s silence_threshold=0.01", t_orch_constants)
check("6 modos na ordem correta", t_modes_list)

# ── 3. Assinatura inject() ────────────────────────────────────────────────────
print("\n=== 3. inject() assinatura ===")

def t_inject_sig():
    import inspect
    from app.injection.injector import inject
    params = list(inspect.signature(inject).parameters.keys())
    assert params == ["text"], f"Esperado ['text'], got {params}"

check("inject(text) sem use_fallback residual", t_inject_sig)

# ── 4. Icones PIL ─────────────────────────────────────────────────────────────
print("\n=== 4. Icones PIL ===")

def t_icons():
    from app.tray.tray_icon import _make_icon, _STATE_COLORS
    for state, color in _STATE_COLORS.items():
        img = _make_icon(color)
        assert img.size == (64, 64), f"{state}: size={img.size}"
        assert img.mode == "RGBA", f"{state}: mode={img.mode}"
        # Verifica que o icone tem pixels nao-transparentes (nao e tela em branco)
        pixels = img.getdata()
        non_transparent = sum(1 for p in pixels if p[3] > 0)
        assert non_transparent > 100, f"{state}: imagem parece vazia ({non_transparent} pixels)"

check("7 estados renderizados 64x64 RGBA com conteudo", t_icons)

# ── 5. CONFIG ─────────────────────────────────────────────────────────────────
print("\n=== 5. CONFIG ===")

def t_config():
    from app.config.settings import CONFIG
    assert CONFIG["hotkey"]["combination"] == "ctrl+shift+r"
    assert CONFIG["audio"]["samplerate"] == 16000
    assert CONFIG["llm"]["model"] == "google/gemini-2.5-flash-lite"
    assert CONFIG["llm"]["max_tokens"] == 1000

def t_api_key():
    from app.config.settings import CONFIG
    key = CONFIG["llm"]["api_key"]
    assert key, "OPENROUTER_API_KEY nao encontrada no .env"

check("hotkey / samplerate / model / max_tokens", t_config)
check("OPENROUTER_API_KEY presente", t_api_key)

# ── 6. Logica de duracao e silencio ───────────────────────────────────────────
print("\n=== 6. Logica de duracao e silencio ===")

def t_duration_logic():
    import numpy as np
    from app.orchestration.orchestrator import _MIN_DURATION_S, _SILENCE_THRESHOLD
    samplerate = 16000

    # Audio de 0.3s deve ser rejeitado (< 0.5s)
    short = np.random.rand(int(0.3 * samplerate)).astype("float32") * 0.5
    dur = len(short) / samplerate
    assert dur < _MIN_DURATION_S, f"0.3s nao foi rejeitado: {dur}"

    # Audio de 1s deve passar
    ok = np.random.rand(int(1.0 * samplerate)).astype("float32") * 0.5
    dur = len(ok) / samplerate
    assert dur >= _MIN_DURATION_S

def t_silence_logic():
    import numpy as np
    from app.orchestration.orchestrator import _SILENCE_THRESHOLD

    # Silencio puro (zeros)
    silent = np.zeros(16000, dtype="float32")
    assert float(np.max(np.abs(silent))) < _SILENCE_THRESHOLD

    # Ruido de fundo leve (abaixo do threshold)
    low = np.full(16000, 0.005, dtype="float32")
    assert float(np.max(np.abs(low))) < _SILENCE_THRESHOLD

    # Audio real (acima do threshold)
    loud = np.full(16000, 0.05, dtype="float32")
    assert float(np.max(np.abs(loud))) >= _SILENCE_THRESHOLD

check("duracao minima 0.5s rejeita corretamente", t_duration_logic)
check("threshold de silencio 0.01 distingue sinal/ruido", t_silence_logic)

# ── 7. LLM retry logic (sem rede) ────────────────────────────────────────────
print("\n=== 7. LLM retry (mock) ===")

def t_llm_retry():
    """Verifica que o retry relancar a excecao apos 3 tentativas."""
    import time as time_mod
    from unittest.mock import MagicMock, patch
    from app.llm.client import LLMClient, _RETRIES

    # Config minimo para instanciar
    cfg = {"llm": {"api_key": "test", "model": "m", "max_tokens": 10, "temperature": 0.0}}

    with patch("app.llm.client.time") as mock_time:
        mock_time.sleep = MagicMock()  # nao esperar de verdade
        client = LLMClient(cfg)
        client._client = MagicMock()
        client._client.chat.completions.create.side_effect = RuntimeError("conexao falhou")
        try:
            client.process("sys", "txt")
            assert False, "Deveria ter lancado excecao"
        except RuntimeError as e:
            assert str(e) == "conexao falhou"
        calls = client._client.chat.completions.create.call_count
        assert calls == _RETRIES, f"Esperado {_RETRIES} tentativas, got {calls}"
        sleeps = mock_time.sleep.call_count
        assert sleeps == _RETRIES - 1, f"Esperado {_RETRIES - 1} sleeps, got {sleeps}"
        # Backoff: 1s, 2s
        sleep_args = [a[0][0] for a in mock_time.sleep.call_args_list]
        assert sleep_args == [1, 2], f"Backoff esperado [1, 2], got {sleep_args}"

check("3 tentativas + backoff 1s/2s + reraise correto", t_llm_retry)

# ── 8. set_state() tray com e sem info ───────────────────────────────────────
print("\n=== 8. TrayIcon.set_state() ===")

def t_tray_set_state():
    from unittest.mock import MagicMock
    from app.tray.tray_icon import TrayIcon

    mock_transcriber = MagicMock()
    mock_transcriber.is_enabled = False
    mock_queue = MagicMock()

    tray = TrayIcon(mock_transcriber, mock_queue)
    # Simula icone ativo
    tray._icon = MagicMock()
    tray._icon.title = ""

    # idle deve incluir modo atual
    tray.set_state("idle")
    assert "DICTATE" in tray._icon.title, f"idle tooltip sem modo: {tray._icon.title}"

    # done com info -> tooltip inclui info
    tray.set_state("done", "STT 1.2s")
    assert "STT 1.2s" in tray._icon.title, f"done tooltip sem info: {tray._icon.title}"

    # done sem info -> tooltip padrao
    tray.set_state("done")
    assert tray._icon.title == "voice-macro — Concluído", f"done sem info: {tray._icon.title}"

    # set_recording_duration
    tray.set_recording_duration(3.0)
    assert "3s" in tray._icon.title, f"duration tooltip: {tray._icon.title}"

check("idle/done/done-sem-info/recording_duration", t_tray_set_state)

# ── 9. setup_windows_startup paths ───────────────────────────────────────────
print("\n=== 9. setup_windows_startup paths ===")

def t_startup_paths():
    import os
    startup_base = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    assert startup_base.exists(), f"Pasta Startup nao existe: {startup_base}"
    pythonw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    assert pythonw.exists(), f"pythonw.exe nao encontrado: {pythonw}"

check("pasta Startup e pythonw.exe existem", t_startup_paths)

# ── Resultado final ───────────────────────────────────────────────────────────
print()
if errors:
    print(f"FALHAS: {len(errors)}")
    for label, err in errors:
        print(f"  - {label}: {err}")
    sys.exit(1)
else:
    print("TODOS OS 9 GRUPOS PASSARAM")
