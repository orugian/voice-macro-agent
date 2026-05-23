# ── Fix 1: CUDA DLLs ─────────────────────────────────────────────────────────
# Deve ser o primeiro bloco de código. ctranslate2 usa LoadLibrary dinâmico;
# os DLLs instalados via pip ficam em .venv/.../nvidia/*/bin/ e não são
# encontrados automaticamente pelo Windows sem este fix.
from pathlib import Path
import os

_nvidia = Path(__file__).parent / ".venv" / "Lib" / "site-packages" / "nvidia"
if _nvidia.exists():
    for _pkg in _nvidia.iterdir():
        _bin = _pkg / "bin"
        if _bin.exists():
            os.add_dll_directory(str(_bin))
            os.environ["PATH"] = str(_bin) + os.pathsep + os.environ.get("PATH", "")

# ── Fix 2: SSL no Windows ─────────────────────────────────────────────────────
# httpx não respeita REQUESTS_CA_BUNDLE; truststore injeta o cert store nativo
# do Windows, evitando CERTIFICATE_VERIFY_FAILED no huggingface_hub / OpenRouter.
import truststore
truststore.inject_into_ssl()

# ── Application imports ───────────────────────────────────────────────────────
import queue
import logging

from app.config.settings import CONFIG
from app.logging.logger import setup_logging
from app.audio.capture import AudioCapture
from app.stt.transcriber import Transcriber
from app.injection.injector import inject
from app.tray.tray_icon import TrayIcon
from app.orchestration.orchestrator import Orchestrator
from app.llm.client import LLMClient


def main() -> None:
    setup_logging(CONFIG["app"]["log_level"])
    log = logging.getLogger(__name__)
    log.info("voice-macro starting (disabled — activate via tray)")

    llm_client = None
    if CONFIG["llm"]["api_key"]:
        llm_client = LLMClient(CONFIG)
    else:
        log.warning("OPENROUTER_API_KEY not set — LLM modes (CLEAN/SUMMARY/INSTRUCT/REFINE/ACTION/PLAN) unavailable")

    event_queue = queue.Queue()

    audio = AudioCapture(CONFIG)
    transcriber = Transcriber(CONFIG)
    tray = TrayIcon(transcriber, event_queue, CONFIG)
    orchestrator = Orchestrator(CONFIG, tray, audio, transcriber, inject, event_queue, llm_client)

    tray.start()

    try:
        orchestrator.run()
    finally:
        tray.stop()
        log.info("voice-macro stopped")


if __name__ == "__main__":
    main()
