from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from typing import List, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf


class AudioRecorder:
    """Records microphone audio to a temporary WAV file."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self._frames: List[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()

    def start(self):
        """Start recording from the microphone."""
        with self._lock:
            self._frames = []
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=self._audio_callback,
            )
            self._stream.start()

    def stop(self) -> Optional[Path]:
        """Stop recording and return the path to the WAV file."""
        with self._lock:
            if self._stream is None:
                return None
            self._stream.stop()
            self._stream.close()
            self._stream = None

            if not self._frames:
                return None

            audio_data = np.concatenate(self._frames, axis=0)
            self._frames = []

        # Skip very short recordings (< 0.3s)
        if len(audio_data) < self.sample_rate * 0.3:
            return None

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, audio_data, self.sample_rate)
        return Path(tmp.name)

    def _audio_callback(self, indata, frames, time, status):
        if status:
            print(f"Audio status: {status}")
        self._frames.append(indata.copy())

    @property
    def is_recording(self) -> bool:
        return self._stream is not None and self._stream.active
