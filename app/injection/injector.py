import time
import logging
import pyperclip
import keyboard

logger = logging.getLogger(__name__)


def inject(text: str) -> None:
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
