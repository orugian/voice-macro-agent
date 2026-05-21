import re
import time
import logging
import pyperclip
import keyboard

logger = logging.getLogger(__name__)

_MAX_INJECT_CHARS = 5000


def _sanitize(text: str) -> str:
    """Remove caracteres de controle (exceto \\t e \\n) e trunca a 5 000 chars.

    Caracteres ASCII 0–8 e 11–31 (ex: \\x01, \\x1b ESC, \\x7f DEL) são removidos
    antes da injeção para evitar sequências inesperadas no campo ativo.
    \\t (9) e \\n (10) são preservados — conteúdo legítimo em texto multilinha.
    """
    text = re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', '', text)
    if len(text) > _MAX_INJECT_CHARS:
        logger.warning(
            f"Injection output truncated from {len(text)} to {_MAX_INJECT_CHARS} chars"
        )
        text = text[:_MAX_INJECT_CHARS]
    return text


def inject(text: str) -> None:
    text = _sanitize(text)
    if not text:
        logger.debug("Nothing to inject after sanitization")
        return
    try:
        _inject_clipboard(text)
    except Exception as e:
        logger.warning(f"Clipboard injection failed ({e}), using typing fallback")
        _inject_typing(text)


def _inject_clipboard(text: str) -> None:
    pyperclip.copy(text)
    time.sleep(0.05)
    keyboard.send("ctrl+v")
    logger.debug("Text injected via clipboard")


def _inject_typing(text: str) -> None:
    from pynput.keyboard import Controller
    Controller().type(text)
    logger.debug("Text injected via typing fallback")
