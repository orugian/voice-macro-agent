"""Minimal always-on-top overlay showing voice-macro state during active PTT.

Runs tkinter mainloop in a dedicated daemon thread. Updates from other threads
are posted safely via root.after(0, callback).
"""
import threading
import logging

logger = logging.getLogger(__name__)

_VISIBLE_STATES = {"recording", "processing", "done"}

_STATE_STYLES = {
    "recording":  ("● GRAVANDO",    "#F44336"),
    "processing": ("⟳ PROCESSANDO", "#FF9800"),
    "done":       ("✓ CONCLUÍDO",   "#00E676"),
}

_AUTO_HIDE_MS = 1400  # ms to keep "done" visible before hiding


class RecordingHUD:
    """Non-blocking overlay window — visible only during recording/processing."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._root = None
        self._status_var = None
        self._mode_var = None
        self._dot_label = None
        self._hide_job = None  # pending after() job id for auto-hide

        if enabled:
            threading.Thread(target=self._run_mainloop, daemon=True).start()

    def _run_mainloop(self) -> None:
        try:
            import tkinter as tk
        except ImportError:
            logger.warning("tkinter not available — HUD disabled")
            return

        self._root = tk.Tk()
        self._root.withdraw()
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        try:
            self._root.attributes("-alpha", 0.88)
        except Exception:
            pass

        # Dimensions & position (bottom-center, above taskbar)
        w, h = 268, 46
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x = (sw - w) // 2
        y = sh - h - 76
        self._root.geometry(f"{w}x{h}+{x}+{y}")
        self._root.configure(bg="#0D1117")

        frame = tk.Frame(self._root, bg="#0D1117", padx=14, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        self._dot_label = tk.Label(
            frame, text="●", fg="#4CAF50", bg="#0D1117",
            font=("Segoe UI", 10),
        )
        self._dot_label.pack(side=tk.LEFT, padx=(0, 8))

        self._status_var = tk.StringVar(value="")
        tk.Label(
            frame, textvariable=self._status_var,
            fg="#DDE6F0", bg="#0D1117",
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT)

        self._mode_var = tk.StringVar(value="")
        tk.Label(
            frame, textvariable=self._mode_var,
            fg="#4A5568", bg="#0D1117",
            font=("Segoe UI", 9),
        ).pack(side=tk.RIGHT)

        self._root.mainloop()

    # ── Thread-safe public API ───────────────────────────────────────────────

    def update(self, state: str, mode: str = "") -> None:
        if not self._enabled or self._root is None:
            return
        self._root.after(0, lambda: self._apply(state, mode))

    def destroy(self) -> None:
        if self._root:
            self._root.after(0, self._root.destroy)

    # ── Internal (runs on tkinter thread) ───────────────────────────────────

    def _apply(self, state: str, mode: str) -> None:
        if self._root is None:
            return

        # Cancel any pending auto-hide
        if self._hide_job is not None:
            self._root.after_cancel(self._hide_job)
            self._hide_job = None

        if state not in _VISIBLE_STATES:
            self._root.withdraw()
            return

        text, dot_color = _STATE_STYLES[state]
        self._status_var.set(text)
        self._mode_var.set(f"[{mode}]" if mode and state != "done" else "")
        self._dot_label.configure(fg=dot_color)
        self._root.deiconify()

        if state == "done":
            self._hide_job = self._root.after(_AUTO_HIDE_MS, self._root.withdraw)
