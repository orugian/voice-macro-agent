import queue
import threading
import logging
from PIL import Image, ImageDraw
import pystray

logger = logging.getLogger(__name__)

_STATE_COLORS = {
    "disabled":   "#666666",
    "loading":    "#2196F3",
    "idle":       "#4CAF50",
    "recording":  "#F44336",
    "processing": "#FF9800",
    "done":       "#00E676",
    "error":      "#C62828",
}

_STATE_TOOLTIPS = {
    "disabled":   "voice-macro — Desativado · clique para ativar",
    "loading":    "voice-macro — Carregando modelo...",
    "idle":       "voice-macro — Pronto",
    "recording":  "voice-macro — Gravando...",
    "processing": "voice-macro — Processando...",
    "done":       "voice-macro — Concluído",
    "error":      "voice-macro — Erro · ver voice-macro.log",
}

MODES = ["DICTATE", "CLEAN", "SUMMARY", "INSTRUCT", "REFINE", "ACTION"]


def _make_icon(color: str) -> Image.Image:
    """Ícone 64×64: quadrado arredondado colorido com silhueta de microfone branca."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Fundo: rounded square (squircle)
    d.rounded_rectangle((2, 2, 62, 62), radius=16, fill=color)
    # Corpo do microfone
    white = "#FFFFFF"
    d.rounded_rectangle((24, 8, 40, 34), radius=8, fill=white)
    # Arco do suporte
    d.arc((16, 26, 48, 48), start=0, end=180, fill=white, width=3)
    # Haste
    d.line([(32, 48), (32, 56)], fill=white, width=3)
    # Base
    d.line([(23, 56), (41, 56)], fill=white, width=3)
    return img


class TrayIcon:
    def __init__(self, transcriber, event_queue: queue.Queue):
        self._transcriber = transcriber
        self._event_queue = event_queue
        self._current_mode = "DICTATE"
        self._icons = {state: _make_icon(color) for state, color in _STATE_COLORS.items()}
        self._icon: pystray.Icon | None = None
        self._build_tray()

    def _build_tray(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem(
                lambda item: "Desativar" if self._transcriber.is_enabled else "Ativar",
                self._on_toggle_enable,
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Modo", pystray.Menu(*self._make_mode_items())),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", self._on_quit),
        )
        self._icon = pystray.Icon(
            "voice-macro",
            self._icons["disabled"],
            _STATE_TOOLTIPS["disabled"],
            menu,
        )

    def _make_mode_items(self) -> list:
        items = []
        for mode in MODES:
            items.append(pystray.MenuItem(
                mode,
                self._make_mode_selector(mode),
                checked=lambda item, m=mode: self._current_mode == m,
                radio=True,
            ))
        return items

    def _make_mode_selector(self, mode: str):
        def on_select(icon, item):
            self._current_mode = mode
            logger.info(f"Mode changed to {mode}")
            icon.update_menu()
        return on_select

    def _on_toggle_enable(self, icon, item) -> None:
        if self._transcriber.is_enabled:
            self._transcriber.disable()
            self.set_state("disabled")
            icon.update_menu()
        else:
            self.set_state("loading")
            threading.Thread(target=self._do_enable, args=(icon,), daemon=True).start()

    def _do_enable(self, icon) -> None:
        try:
            self._transcriber.enable()
            self.set_state("idle")
        except Exception as e:
            logger.error(f"Failed to load STT model: {e}")
            self.set_state("error")
        icon.update_menu()

    def _on_quit(self, icon, item) -> None:
        self._event_queue.put("QUIT")
        icon.stop()

    def set_state(self, state: str, info: str = "") -> None:
        if self._icon is None:
            return
        tooltip = _STATE_TOOLTIPS.get(state, f"voice-macro — {state}")
        if state == "idle":
            tooltip = f"voice-macro — Pronto · {self._current_mode}"
        elif state == "done" and info:
            tooltip = f"voice-macro — Concluído · {info}"
            threading.Thread(target=self._show_toast, args=(info,), daemon=True).start()
        self._icon.icon = self._icons[state]
        self._icon.title = tooltip

    def set_recording_duration(self, seconds: float) -> None:
        if self._icon:
            self._icon.title = f"voice-macro — Gravando... {seconds:.0f}s"

    def _show_toast(self, info: str) -> None:
        try:
            from winotify import Notification
            toast = Notification(
                app_id="voice-macro",
                title="Texto injetado",
                msg=info,
                duration="short",
            )
            toast.show()
        except Exception:
            pass  # winotify não instalado ou falha silenciosa

    def get_current_mode(self) -> str:
        return self._current_mode

    def start(self) -> None:
        t = threading.Thread(target=self._icon.run, daemon=True)
        t.start()
        logger.info("Tray icon started")

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()
