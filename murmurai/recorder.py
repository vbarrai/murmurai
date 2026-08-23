from __future__ import annotations

import queue
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf


class AudioRecorder:
    """Records microphone audio with optional chunk streaming."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_interval: float = 1.5,
        device: Optional[int] = None,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_interval = chunk_interval
        # sounddevice input index, or None to follow the system default.
        self.device = device
        # Called with a 0..1 RMS level on every audio callback, for the HUD
        # waveform. Set to None to skip the computation entirely.
        self.on_level: Optional[Callable[[float], None]] = None
        self._frames: List[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._chunk_queue: Optional[queue.Queue] = None
        self._lock = threading.Lock()

    def start(self, chunk_queue: Optional[queue.Queue] = None):
        """Start recording from the microphone.

        If chunk_queue is provided, audio chunks are emitted periodically.
        """
        with self._lock:
            self._frames = []
            self._chunk_queue = chunk_queue
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                device=self.device,
                callback=self._audio_callback,
            )
            self._stream.start()

        if chunk_queue is not None:
            threading.Thread(target=self._chunk_emitter, daemon=True).start()

    def stop(self) -> Optional[Path]:
        """Stop recording. Flushes remaining audio to the chunk queue if streaming."""
        with self._lock:
            if self._stream is None:
                return None
            self._stream.stop()
            self._stream.close()
            self._stream = None

            remaining = None
            if self._frames:
                remaining = np.concatenate(self._frames, axis=0)
            self._frames = []

        # Streaming mode: flush remaining + sentinel
        if self._chunk_queue is not None:
            if remaining is not None and len(remaining) > 0:
                self._chunk_queue.put(remaining)
            self._chunk_queue.put(None)  # sentinel
            self._chunk_queue = None
            return None

        # Non-streaming fallback
        if remaining is None:
            return None
        if len(remaining) < self.sample_rate * 0.3:
            return None
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, remaining, self.sample_rate)
        return Path(tmp.name)

    def _chunk_emitter(self):
        """Periodically emit accumulated audio frames to the chunk queue."""
        while True:
            time.sleep(self.chunk_interval)
            with self._lock:
                if self._stream is None or not self._stream.active:
                    break
                if not self._frames:
                    continue
                chunk = np.concatenate(self._frames, axis=0)
                self._frames = []
            if self._chunk_queue is not None:
                self._chunk_queue.put(chunk)

    def _audio_callback(self, indata, frames, time, status):
        if status:
            print(f"Audio status: {status}")
        self._frames.append(indata.copy())
        if self.on_level is not None:
            self.on_level(_rms_level(indata))

    @property
    def is_recording(self) -> bool:
        return self._stream is not None and self._stream.active


def _rms_level(block: np.ndarray) -> float:
    """Return the RMS of an int16 block as a 0..1 level.

    The raw RMS of speech sits very low on a linear scale, so it is mapped
    through a decibel curve (-50 dBFS → 0, 0 dBFS → 1) to give the waveform a
    usable dynamic range.
    """
    if block.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(block.astype(np.float32) / 32768.0))))
    if rms <= 0:
        return 0.0
    db = 20.0 * np.log10(rms)
    return float(min(1.0, max(0.0, (db + 50.0) / 50.0)))
