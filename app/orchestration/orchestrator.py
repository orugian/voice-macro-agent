import time
import queue
import logging
import threading
import numpy as np
from pynput import keyboard as pynput_keyboard
from app.modes import processors
from app.audio import sounds

logger = logging.getLogger(__name__)

_MIN_DURATION_S = 0.5   # gravações menores que isso são ignoradas (tecla acidental)
_SILENCE_THRESHOLD = 0.01  # pico de amplitude máximo para considerar áudio vazio


class Orchestrator:
    def __init__(self, config: dict, tray, audio, stt, inject_fn, event_queue: queue.Queue,
                 llm_client=None):
        self._config = config
        self.tray = tray
        self.audio = audio
        self.stt = stt
        self._inject = inject_fn
        self._event_queue = event_queue
        self._llm_client = llm_client
        self._recording = False
        self._recording_event = threading.Event()  # set=gravando, clear=parado
        self._recording_start: float = 0.0
        self._samplerate: int = config["audio"]["samplerate"]
        self._current_keys: set = set()
        self._hotkey_parts: list[set] = []
        self._listener: pynput_keyboard.Listener | None = None
        self._sounds_enabled: bool = config["app"].get("sounds_enabled", True)
        self._setup_listener()

    def _parse_combo(self, combo: str) -> list[set]:
        # Inclui variantes genéricas (Key.shift) além de left/right — VNC e
        # alguns teclados reportam o genérico em vez do direcional.
        MOD = {
            "ctrl":  {pynput_keyboard.Key.ctrl,
                      pynput_keyboard.Key.ctrl_l,  pynput_keyboard.Key.ctrl_r},
            "alt":   {pynput_keyboard.Key.alt,
                      pynput_keyboard.Key.alt_l,   pynput_keyboard.Key.alt_r,
                      pynput_keyboard.Key.alt_gr},
            "shift": {pynput_keyboard.Key.shift,
                      pynput_keyboard.Key.shift_l, pynput_keyboard.Key.shift_r},
        }
        parts = []
        for p in combo.lower().split("+"):
            p = p.strip()
            if p in MOD:
                parts.append(MOD[p])
            elif len(p) == 1:
                parts.append({pynput_keyboard.KeyCode.from_char(p)})
        return parts

    def _normalize_key(self, key):
        """Normaliza a tecla para forma base ignorando efeito dos modificadores.

        Com Ctrl pressionado: 'r' chega como '\\x12' (ctrl-char ASCII 18).
        Com Alt pressionado:  'r' chega como KeyCode(vk=82) sem .char.
        Ambos precisam ser normalizados para KeyCode.from_char('r') para
        bater com o que _parse_combo() gerou.
        """
        if isinstance(key, pynput_keyboard.KeyCode):
            char = key.char
            if char is not None and len(char) == 1:
                code = ord(char)
                if 1 <= code <= 26:
                    # Ctrl+letra → caractere de controle; recupera a letra base
                    return pynput_keyboard.KeyCode.from_char(chr(code + 96))
                return pynput_keyboard.KeyCode.from_char(char.lower())
            elif key.vk is not None and 65 <= key.vk <= 90:
                # VK A-Z (65-90); converte para minúscula
                return pynput_keyboard.KeyCode.from_char(chr(key.vk + 32))
        return key

    def _is_hotkey_complete(self) -> bool:
        return all(
            any(k in self._current_keys for k in alternatives)
            for alternatives in self._hotkey_parts
        )

    def _is_hotkey_key(self, key) -> bool:
        return any(key in alternatives for alternatives in self._hotkey_parts)

    def _setup_listener(self) -> None:
        combo = self._config["hotkey"]["combination"]
        self._hotkey_parts = self._parse_combo(combo)
        logger.info(f"Hotkey configured: {combo}")

        def on_press(key):
            normalized = self._normalize_key(key)
            self._current_keys.add(normalized)
            if not self._recording and self._is_hotkey_complete():
                self._event_queue.put("PTT_START")

        def on_release(key):
            normalized = self._normalize_key(key)
            if self._is_hotkey_key(normalized):
                self._event_queue.put("PTT_STOP")
            self._current_keys.discard(normalized)

        self._listener = pynput_keyboard.Listener(
            on_press=on_press,
            on_release=on_release,
        )
        self._listener.start()

    def run(self) -> None:
        logger.info("Orchestrator running — waiting for events")
        while True:
            event = self._event_queue.get()
            if event == "PTT_START" and not self._recording:
                self._on_ptt_start()
            elif event == "PTT_STOP" and self._recording:
                self._on_ptt_stop()
            elif event == "QUIT":
                break
        self._cleanup()

    def _on_ptt_start(self) -> None:
        if not self.stt.is_enabled:
            return
        self._recording = True
        self._recording_start = time.monotonic()
        self._recording_event.set()
        self.tray.set_state("recording")
        self.audio.start_recording()
        if self._sounds_enabled:
            sounds.start_recording()
        threading.Thread(target=self._update_recording_duration, daemon=True).start()
        logger.debug("PTT start — recording")

    def _update_recording_duration(self) -> None:
        """Atualiza tooltip a cada 0.5 s enquanto grava. Sai imediatamente ao Event.clear()."""
        while self._recording_event.wait(timeout=0.5):
            elapsed = time.monotonic() - self._recording_start
            self.tray.set_recording_duration(elapsed)

    def _on_ptt_stop(self) -> None:
        self._recording = False
        self._recording_event.clear()
        if self._sounds_enabled:
            sounds.stop_recording()
        self.tray.set_state("processing")
        audio = self.audio.stop_recording()

        duration = len(audio) / self._samplerate if len(audio) > 0 else 0.0
        if duration < _MIN_DURATION_S:
            logger.debug(f"Recording too short ({duration:.2f}s) — ignored")
            self.tray.set_state("idle")
            return

        if np.max(np.abs(audio)) < _SILENCE_THRESHOLD:
            logger.warning("Audio silent — skipping pipeline")
            self.tray.set_state("idle")
            return

        logger.debug(f"PTT stop — {len(audio)} samples, {duration:.2f}s")

        t0 = time.monotonic()
        elapsed_llm: float | None = None
        try:
            text, lang = self.stt.transcribe(audio)
            elapsed_stt = time.monotonic() - t0
            logger.info(f"STT [{lang}] {len(text)} chars in {elapsed_stt:.2f}s")

            if text.strip():
                mode = self.tray.get_current_mode()
                if mode != "DICTATE" and self._llm_client is not None:
                    t1 = time.monotonic()
                    text = processors.process(mode, text, self._llm_client)
                    elapsed_llm = time.monotonic() - t1
                    logger.info(f"LLM [{mode}] {len(text)} chars in {elapsed_llm:.2f}s")
                if text.strip():
                    self._inject(text)
                    if self._sounds_enabled:
                        sounds.success()

            latency_info = f"STT {elapsed_stt:.1f}s"
            if elapsed_llm is not None:
                latency_info += f" · LLM {elapsed_llm:.1f}s"
            self.tray.set_state("done", latency_info)
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            if self._sounds_enabled:
                sounds.error()
            self.tray.set_state("error")
        finally:
            time.sleep(0.5)
            self.tray.set_state("idle")
            self._drain_ptt_events()

    def _drain_ptt_events(self) -> None:
        """Descarta PTT events enfileirados durante processamento. Preserva QUIT."""
        saved = []
        try:
            while True:
                ev = self._event_queue.get_nowait()
                if ev == "QUIT":
                    saved.append(ev)
        except queue.Empty:
            pass
        for ev in saved:
            self._event_queue.put(ev)

    def _cleanup(self) -> None:
        if self._listener:
            self._listener.stop()
        self.stt.disable()
        logger.info("Orchestrator stopped")
