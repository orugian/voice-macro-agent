"""Synthesized audio cues for voice-macro pipeline events.

Uses sounddevice + numpy (already in requirements). Falls back silently
if audio playback is unavailable or the device is busy.
"""
import threading
import numpy as np

try:
    import sounddevice as _sd
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False

_RATE = 44100
_AMP = 0.22  # master volume (0.0–1.0)
_FADE_MS = 8.0  # fade-in/out to avoid clicks


def _tone(freq_start: float, freq_end: float, ms: float) -> np.ndarray:
    """Linear frequency sweep (or constant tone when freq_start == freq_end)."""
    n = max(1, int(ms * _RATE / 1000))
    t = np.linspace(0, ms / 1000, n, endpoint=False)
    phase = 2.0 * np.pi * (
        freq_start * t
        + 0.5 * (freq_end - freq_start) * t * t / max(ms / 1000, 1e-6)
    )
    wave = np.sin(phase) * _AMP
    fade = min(int(_FADE_MS * _RATE / 1000), n // 4)
    if fade > 0:
        wave[:fade] *= np.linspace(0.0, 1.0, fade)
        wave[-fade:] *= np.linspace(1.0, 0.0, fade)
    return wave.astype(np.float32)


def _silence(ms: float) -> np.ndarray:
    return np.zeros(int(ms * _RATE / 1000), dtype=np.float32)


def _play(*segments: np.ndarray) -> None:
    if not _AVAILABLE:
        return
    audio = np.concatenate(segments)

    def _run() -> None:
        try:
            _sd.play(audio, samplerate=_RATE, blocking=True)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


# ── Public sound events ──────────────────────────────────────────────────────

def start_recording() -> None:
    """Ascending sweep — PTT engaged, recording started."""
    _play(_tone(600, 1050, 115))


def stop_recording() -> None:
    """Short neutral tone — PTT released."""
    _play(_tone(820, 820, 70))


def success() -> None:
    """Two-tone sequence — text injected successfully."""
    _play(_tone(920, 920, 70), _silence(28), _tone(1240, 1240, 90))


def error() -> None:
    """Descending tone — pipeline failure."""
    _play(_tone(480, 280, 215))
