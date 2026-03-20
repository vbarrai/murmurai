from __future__ import annotations

from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel


class LocalTranscriber:
    """Transcribes audio locally using faster-whisper."""

    def __init__(
        self,
        model_size: str = "medium",
        language: Optional[str] = None,
        device: str = "auto",
    ):
        self.language = language
        self._model = WhisperModel(model_size, device=device, compute_type="int8")

    def transcribe(self, audio_path: Path) -> str:
        segments, _ = self._model.transcribe(
            str(audio_path),
            language=self.language,
            beam_size=5,
        )
        return " ".join(segment.text.strip() for segment in segments)
