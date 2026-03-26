from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel

from murmurai.jargon import fix_jargon

log = logging.getLogger("murmurai")


class LocalTranscriber:
    """Transcribes audio locally using faster-whisper."""

    def __init__(
        self,
        model_size: str = "small",
        language: Optional[str] = None,
        device: str = "auto",
    ):
        self.language = language
        self.on_status: Optional[callable] = None
        self.on_text: Optional[callable] = None  # called with partial text during transcription
        self._model_size = model_size
        self._device = device
        self._model = WhisperModel(model_size, device=device, compute_type="int8")

    def transcribe(self, audio_path: Path, cancel_event: Optional[threading.Event] = None) -> str:
        segments, _ = self._model.transcribe(
            str(audio_path),
            language=self.language or "fr",
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        parts = []
        for segment in segments:
            if cancel_event and cancel_event.is_set():
                log.info("Transcription cancelled")
                return ""
            parts.append(segment.text.strip())
            if self.on_text:
                self.on_text(" ".join(parts))
        text = " ".join(parts)
        return fix_jargon(text)
