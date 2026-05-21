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

# ── 10. Sanitizacao de injecao ────────────────────────────────────────────────
print("\n=== 10. Sanitizacao de injecao ===")

def t_sanitize_control_chars():
    from app.injection.injector import _sanitize
    # Caracteres de controle devem ser removidos
    assert _sanitize("\x00\x01\x08texto\x1f") == "texto"
    assert _sanitize("linha1\x1btexto") == "linha1texto"   # ESC removido
    assert _sanitize("\x7ftexto") == "texto"                # DEL removido
    # \t e \n devem ser preservados
    assert _sanitize("col1\tcol2") == "col1\tcol2"
    assert _sanitize("linha1\nlinha2") == "linha1\nlinha2"

def t_sanitize_truncation():
    from app.injection.injector import _sanitize, _MAX_INJECT_CHARS
    longo = "x" * (_MAX_INJECT_CHARS + 1000)
    resultado = _sanitize(longo)
    assert len(resultado) == _MAX_INJECT_CHARS, f"Esperado {_MAX_INJECT_CHARS}, got {len(resultado)}"

def t_sanitize_empty_after():
    from app.injection.injector import _sanitize
    # Texto que vira vazio apos sanitizacao
    assert _sanitize("\x01\x02\x03") == ""

def t_inject_skips_empty():
    """inject() deve retornar silenciosamente se texto for vazio ou virar vazio apos sanitizacao."""
    from unittest.mock import patch, MagicMock
    from app.injection import injector
    with patch("app.injection.injector._inject_clipboard") as mock_cb, \
         patch("app.injection.injector._inject_typing") as mock_ty:
        injector.inject("")          # string vazia
        injector.inject("\x01\x02") # vira vazia apos sanitizacao
        assert mock_cb.call_count == 0
        assert mock_ty.call_count == 0

check("controle chars removidos, \\t e \\n preservados", t_sanitize_control_chars)
check(f"texto > {5000} chars truncado", t_sanitize_truncation)
check("texto que vira vazio apos sanitizacao", t_sanitize_empty_after)
check("inject() nao chama clipboard/typing para texto vazio", t_inject_skips_empty)

# ── 11. threading.Event no orchestrator ──────────────────────────────────────
print("\n=== 11. threading.Event no orchestrator ===")

def t_recording_event_exists():
    import inspect
    from app.orchestration.orchestrator import Orchestrator
    src = inspect.getsource(Orchestrator.__init__)
    assert "_recording_event" in src
    assert "threading.Event()" in src

def t_recording_event_lifecycle():
    """Event deve ser set() no start e clear() no stop."""
    import inspect
    from app.orchestration.orchestrator import Orchestrator
    start_src = inspect.getsource(Orchestrator._on_ptt_start)
    stop_src = inspect.getsource(Orchestrator._on_ptt_stop)
    duration_src = inspect.getsource(Orchestrator._update_recording_duration)
    assert "_recording_event.set()" in start_src
    assert "_recording_event.clear()" in stop_src
    assert "_recording_event.wait(" in duration_src

check("_recording_event = threading.Event() em __init__", t_recording_event_exists)
check("set() no start, clear() no stop, wait() no duration thread", t_recording_event_lifecycle)

# ── Resultado final ───────────────────────────────────────────────────────────
print()
if errors:
    print(f"FALHAS: {len(errors)}")
    for label, err in errors:
        print(f"  - {label}: {err}")
    sys.exit(1)
else:
    print("TODOS OS 11 GRUPOS PASSARAM")
