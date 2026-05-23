import time
import queue
import threading
import logging
from PIL import Image, ImageDraw
import pystray

logger = logging.getLogger(__name__)

# ── State palette ────────────────────────────────────────────────────────────
_STATE_COLORS = {
    "disabled":   "#4A5568",
    "loading":    "#2196F3",
    "idle":       "#00C8DC",   # Haku teal at rest
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

MODES = ["DICTATE", "CLEAN", "SUMMARY", "INSTRUCT", "REFINE", "ACTION", "PLAN"]

# ── Dragon icon (Haku-inspired) ──────────────────────────────────────────────
#
# 64×64 RGBA.  Eastern dragon head in profile, facing right.
# Palette: near-black bg, cool-white scales, teal mane, golden antlers.
# State colour drives the eye glow; recording frame 1 pulses the glow.

_BG       = "#0D1117"
_HEAD     = "#D8E4EF"   # cool white scales
_TEAL     = "#00C8DC"   # mane / whiskers
_TEAL_HI  = "#40E8FF"   # brighter teal for animated frame
_ANTLER   = "#B8956A"   # golden-tan antlers


def _draw_mane(d: ImageDraw.ImageDraw, teal: str) -> None:
    """Three flowing arcs behind the head — Haku's characteristic mane."""
    d.arc((1, 12, 20, 42),  start=195, end=320, fill=teal, width=2)
    d.arc((3,  5, 19, 28),  start=205, end=335, fill=teal, width=2)
    d.arc((0, 22, 12, 46),  start=180, end=278, fill=teal, width=2)


def _draw_head(d: ImageDraw.ImageDraw) -> None:
    """Dragon head: forehead dome + main cranium + elongated snout."""
    d.ellipse(( 9, 10, 40, 34), fill=_HEAD)   # forehead dome
    d.ellipse(( 8, 16, 48, 52), fill=_HEAD)   # main cranium
    d.ellipse((35, 26, 60, 44), fill=_HEAD)   # snout


def _draw_antlers(d: ImageDraw.ImageDraw) -> None:
    """Two forked antlers — Haku's most distinctive feature."""
    # Left antler
    d.line([(22, 16), (17,  8)], fill=_ANTLER, width=2)
    d.line([(17,  8), (13,  3)], fill=_ANTLER, width=2)
    d.line([(17,  8), (20,  3)], fill=_ANTLER, width=2)
    # Right antler
    d.line([(30, 13), (28,  5)], fill=_ANTLER, width=2)
    d.line([(28,  5), (24,  1)], fill=_ANTLER, width=2)
    d.line([(28,  5), (31,  1)], fill=_ANTLER, width=2)


def _draw_eye(d: ImageDraw.ImageDraw, state_color: str, frame: int) -> None:
    """Glowing slit eye — glow radius pulses on recording frame 1."""
    ex, ey = 43, 33
    # Outer glow (larger on animated frame)
    gr = 8 if frame == 1 else 6
    d.ellipse((ex - gr, ey - gr, ex + gr, ey + gr), fill=state_color)
    # Eye white
    d.ellipse((ex - 5, ey - 5, ex + 5, ey + 5), fill="#FFFEF0")
    # Vertical slit pupil
    d.rectangle((ex - 1, ey - 4, ex + 1, ey + 4), fill="#0A0B16")


def _draw_whiskers(d: ImageDraw.ImageDraw, teal: str) -> None:
    """Three barbels trailing from snout — characteristic of eastern dragons."""
    d.line([(54, 32), (61, 28)], fill=teal, width=1)
    d.line([(55, 35), (62, 35)], fill=teal, width=1)
    d.line([(54, 39), (61, 43)], fill=teal, width=1)


def _make_dragon_icon(state: str, frame: int = 0) -> Image.Image:
    """Render one 64×64 RGBA frame of the Haku dragon icon."""
    color = _STATE_COLORS[state]
    teal  = _TEAL_HI if frame == 1 else _TEAL

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    # Background
    d.rounded_rectangle((0, 0, 63, 63), radius=12, fill=_BG)

    # Draw in painter's order: mane → head → antlers → eye → whiskers
    _draw_mane(d, teal)
    _draw_head(d)
    _draw_antlers(d)
    _draw_eye(d, color, frame)
    _draw_whiskers(d, teal)

    return img


# ── TrayIcon ─────────────────────────────────────────────────────────────────

class TrayIcon:
    def __init__(self, transcriber, event_queue: queue.Queue,
                 config: dict | None = None) -> None:
        self._transcriber = transcriber
        self._event_queue = event_queue
        self._current_mode = "DICTATE"

        # Pre-render all state icons + 2 recording animation frames
        self._icons: dict[str, Image.Image] = {}
        for state in _STATE_COLORS:
            self._icons[state] = _make_dragon_icon(state)
        self._icons["recording_1"] = _make_dragon_icon("recording", frame=1)

        self._icon: pystray.Icon | None = None
        self._animating = False
        self._animation_thread: threading.Thread | None = None

        # Optional HUD overlay
        cfg = config or {}
        hud_enabled = cfg.get("app", {}).get("hud_enabled", True)
        self._hud = None
        if hud_enabled:
            try:
                from app.ui.hud import RecordingHUD
                self._hud = RecordingHUD(enabled=True)
            except Exception as e:
                logger.warning(f"HUD unavailable: {e}")

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

    # ── State management ─────────────────────────────────────────────────────

    def set_state(self, state: str, info: str = "") -> None:
        if self._icon is None:
            return

        # Stop ongoing animation
        self._animating = False

        if state == "recording":
            self._icon.icon = self._icons["recording"]
            self._icon.title = _STATE_TOOLTIPS["recording"]
            self._animating = True
            self._animation_thread = threading.Thread(
                target=self._animate_recording, daemon=True
            )
            self._animation_thread.start()
        else:
            self._icon.icon = self._icons.get(state, self._icons["idle"])
            tooltip = _STATE_TOOLTIPS.get(state, f"voice-macro — {state}")
            if state == "idle":
                tooltip = f"voice-macro — Pronto · {self._current_mode}"
            elif state == "done" and info:
                tooltip = f"voice-macro — Concluído · {info}"
                threading.Thread(
                    target=self._show_toast, args=(info,), daemon=True
                ).start()
            self._icon.title = tooltip

        # Update HUD overlay
        if self._hud is not None:
            self._hud.update(state, self._current_mode)

    def _animate_recording(self) -> None:
        frame = 0
        while self._animating:
            key = "recording" if frame == 0 else "recording_1"
            if self._icon:
                self._icon.icon = self._icons[key]
            frame = 1 - frame
            time.sleep(0.44)

    def set_recording_duration(self, seconds: float) -> None:
        if self._icon:
            self._icon.title = f"voice-macro — Gravando... {seconds:.0f}s"

    def _show_toast(self, info: str) -> None:
        try:
            from winotify import Notification
            # Include mode and a brief description in the toast
            toast = Notification(
                app_id="voice-macro",
                title=f"Texto injetado · {self._current_mode}",
                msg=info,
                duration="short",
            )
            toast.show()
        except Exception:
            pass

    def get_current_mode(self) -> str:
        return self._current_mode

    def start(self) -> None:
        t = threading.Thread(target=self._icon.run, daemon=True)
        t.start()
        logger.info("Tray icon started")

    def stop(self) -> None:
        self._animating = False
        if self._hud is not None:
            self._hud.destroy()
        if self._icon:
            self._icon.stop()
