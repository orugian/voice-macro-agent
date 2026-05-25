import time
import queue
import threading
import logging
from pathlib import Path
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

# ── Icon rendering ────────────────────────────────────────────────────────────
_BG    = "#0D1117"    # near-black background
_HEAD  = "#D8E4EF"    # cool-white dragon silhouette
_EYE_W = "#FFFEF0"    # eye white
_PUPIL = "#0A0B16"    # slit pupil

_PROJECT_ROOT = Path(__file__).parent.parent.parent


def _make_dragon_icon(state: str, frame: int = 0) -> Image.Image:
    """Render one 64×64 RGBA dragon icon, optimised for legibility at tray scale.

    Design principles for 16×16 effective rendering:
    - Only bold solid shapes (no thin lines)
    - State expressed as a large coloured eye — dominant at small sizes
    - Dorsal horn provides silhouette recognition at a glance
    """
    color = _STATE_COLORS[state]

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Background
    d.rounded_rectangle((0, 0, 63, 63), radius=12, fill=_BG)

    # Dragon silhouette — three overlapping bold shapes
    d.ellipse(( 6,  8, 46, 52), fill=_HEAD)             # cranium
    d.ellipse((30, 18, 58, 44), fill=_HEAD)              # snout (extends right)
    d.polygon([(18, 8), (13, 0), (27, 4)], fill=_HEAD)   # dorsal horn

    # Eye — large, state-coloured; primary state indicator at tray scale
    ex, ey = 42, 30
    glow_r = 11 + (3 if frame == 1 else 0)   # 11 px at rest → 14 px on recording pulse
    d.ellipse((ex - glow_r, ey - glow_r, ex + glow_r, ey + glow_r), fill=color)
    d.ellipse((ex - 6,      ey - 6,      ex + 6,      ey + 6),      fill=_EYE_W)
    d.rectangle((ex - 2,    ey - 5,      ex + 2,      ey + 5),      fill=_PUPIL)

    return img


def _build_icon_cache(project_root: Path) -> dict[str, Image.Image]:
    """Load icons from assets/icons/ if present, otherwise generate via PIL.

    Drop a file named icon_{state}.png in assets/icons/ to override any state.
    icon_recording_1.png overrides the pulsed recording animation frame.
    """
    assets = project_root / "assets" / "icons"
    icons: dict[str, Image.Image] = {}

    keys = list(_STATE_COLORS.keys()) + ["recording_1"]
    for key in keys:
        state = "recording" if key == "recording_1" else key
        frame = 1          if key == "recording_1" else 0
        path  = assets / f"icon_{key}.png"
        if path.exists():
            try:
                icons[key] = Image.open(path).convert("RGBA").resize((64, 64), Image.LANCZOS)
                logger.debug(f"Loaded icon from file: {path.name}")
                continue
            except Exception as e:
                logger.warning(f"Failed to load {path.name}: {e} — using generated icon")
        icons[key] = _make_dragon_icon(state, frame=frame)

    return icons


def _save_icon_cache(icons: dict[str, Image.Image], project_root: Path) -> None:
    """Write generated icons to assets/icons/ for inspection and custom replacement.

    Existing files are never overwritten — delete a file to regenerate it.
    Also creates voice-macro.ico (multi-size) used by scripts/create_shortcut.py.
    """
    assets = project_root / "assets" / "icons"
    try:
        assets.mkdir(parents=True, exist_ok=True)
        for name, img in icons.items():
            path = assets / f"icon_{name}.png"
            if not path.exists():
                img.save(path)
        ico_path = assets / "voice-macro.ico"
        if not ico_path.exists():
            base = icons.get("idle", _make_dragon_icon("idle"))
            base.save(ico_path, format="ICO",
                      sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    except Exception as e:
        logger.warning(f"Could not save icon cache to assets/: {e}")


# ── TrayIcon ─────────────────────────────────────────────────────────────────

class TrayIcon:
    def __init__(self, transcriber, event_queue: queue.Queue,
                 config: dict | None = None) -> None:
        self._transcriber = transcriber
        self._event_queue = event_queue
        self._current_mode = "DICTATE"
        self._current_state = "disabled"
        self._config = config or {}

        # Build icon cache (loads from assets/ or generates + saves to disk)
        self._icons = _build_icon_cache(_PROJECT_ROOT)
        _save_icon_cache(self._icons, _PROJECT_ROOT)

        self._icon: pystray.Icon | None = None
        # Event-based animation control: set = stopped, clear = running
        self._stop_anim = threading.Event()
        self._stop_anim.set()

        # Optional HUD overlay
        hud_enabled = self._config.get("app", {}).get("hud_enabled", True)
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
        elif self._current_state != "loading":   # guard: ignore double-click during load
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

        self._current_state = state
        self._stop_anim.set()   # halt any running animation

        if state == "recording":
            self._icon.icon  = self._icons["recording"]
            self._icon.title = _STATE_TOOLTIPS["recording"]
            self._stop_anim.clear()   # arm the animation loop
            threading.Thread(target=self._animate_recording, daemon=True).start()
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

        logger.debug(f"Tray state → {state}")

        if self._hud is not None:
            self._hud.update(state, self._current_mode)

    def _animate_recording(self) -> None:
        """Alternates recording frames until _stop_anim is set.

        Uses Event.wait(timeout) as both the sleep and the stop-check,
        eliminating the race condition of a separate bool + sleep pattern.
        """
        frame = 0
        while not self._stop_anim.wait(timeout=0.44):
            if self._icon:
                key = "recording" if frame == 0 else "recording_1"
                self._icon.icon = self._icons[key]
            frame = 1 - frame

    def set_recording_duration(self, seconds: float) -> None:
        if self._icon:
            self._icon.title = f"voice-macro — Gravando... {seconds:.0f}s"

    def _show_toast(self, info: str) -> None:
        try:
            from winotify import Notification
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

    def start_if_enabled(self) -> None:
        """Auto-enable STT at startup when start_enabled = true in config.toml.

        Must be called *after* start() so the pystray Win32 loop is running.
        """
        if self._config.get("app", {}).get("start_enabled", False):
            def _delayed() -> None:
                time.sleep(0.5)   # let pystray Win32 loop settle
                self.set_state("loading")
                self._do_enable(self._icon)
            threading.Thread(target=_delayed, daemon=True).start()
            logger.info("start_enabled=true — STT auto-enable scheduled")

    def stop(self) -> None:
        self._stop_anim.set()
        if self._hud is not None:
            self._hud.destroy()
        if self._icon:
            self._icon.stop()
