import queue
import logging
import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


class AudioCapture:
    def __init__(self, config: dict):
        self._cfg = config["audio"]
        self._queue: queue.Queue = queue.Queue()
        self._stream: sd.InputStream | None = None

    def start_recording(self) -> None:
        self._queue = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=self._cfg["samplerate"],
            channels=self._cfg["channels"],
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()
        logger.debug("Audio capture started")

    def _callback(self, indata, frames, time, status) -> None:
        if status:
            logger.warning(f"Audio capture status: {status}")
        self._queue.put(indata.copy())

    def stop_recording(self) -> np.ndarray:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        chunks = []
        while not self._queue.empty():
            chunks.append(self._queue.get_nowait())

        logger.debug(f"Audio capture stopped: {len(chunks)} chunks")

        if not chunks:
            return np.zeros(0, dtype="float32")
        return np.concatenate(chunks, axis=0).flatten()
