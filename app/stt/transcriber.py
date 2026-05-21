import gc
import logging
import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, config: dict):
        self._config = config
        self._model: WhisperModel | None = None

    def enable(self) -> None:
        if self._model is None:
            logger.info("Loading STT model into VRAM...")
            self._model = WhisperModel(
                self._config["stt"]["model"],
                device=self._config["stt"]["device"],
                compute_type=self._config["stt"]["compute_type"],
                num_workers=1,
            )
            logger.info("STT model loaded successfully")

    def disable(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            gc.collect()
            logger.info("STT model unloaded, VRAM freed")

    @property
    def is_enabled(self) -> bool:
        return self._model is not None

    def transcribe(self, audio_1d: np.ndarray) -> tuple[str, str]:
        if self._model is None:
            raise RuntimeError("Transcriber not enabled. Activate via tray first.")
        language = self._config["stt"].get("language") or None
        segments, info = self._model.transcribe(
            audio_1d,
            language=language,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        segment_list = list(segments)
        full_text = " ".join(s.text for s in segment_list).strip()
        return full_text, info.language
