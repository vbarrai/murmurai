from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel

from murmurai.jargon import fuse_local

log = logging.getLogger("murmurai")


class LocalTranscriber:
    """Transcribes audio locally using faster-whisper."""

    def __init__(
        self,
        model_size: str = "small",
        language: Optional[str] = None,
        device: str = "auto",
        bilingual: bool = False,
    ):
        self.language = language
        self.bilingual = bilingual
        self.on_status: Optional[callable] = None
        self.on_text: Optional[callable] = None  # called with partial text during transcription
        self._model_size = model_size
        self._device = device
        self._model = WhisperModel(model_size, device=device, compute_type="int8")
        # Second model instance for parallel bilingual transcription
        self._model2: Optional[WhisperModel] = None

    def transcribe(self, audio_path: Path) -> str:
        if self.bilingual:
            return self._transcribe_bilingual_from_file(audio_path)
        return self._transcribe_single(audio_path)

    def transcribe_bilingual_raw(self, audio_path: Path) -> tuple[str, str]:
        """Return (text_fr, text_en) without fusion. For agent mode."""
        if self._model2 is None:
            log.info("Loading second Whisper model for parallel bilingual...")
            self._model2 = WhisperModel(
                self._model_size, device=self._device, compute_type="int8",
            )

        if self.on_status:
            self.on_status("Transcription FR + EN…")
        log.info("Bilingual transcription (raw): running FR + EN passes in parallel...")
        path_str = str(audio_path)

        def run_fr(model):
            segments, _ = model.transcribe(
                path_str, language="fr", beam_size=1,
                vad_filter=True, condition_on_previous_text=False,
            )
            parts = []
            for s in segments:
                parts.append(s.text.strip())
                if self.on_text:
                    self.on_text(" ".join(parts))
            return " ".join(parts)

        def run_en(model):
            segments, _ = model.transcribe(
                path_str, language="en", beam_size=1,
                vad_filter=True, condition_on_previous_text=False,
            )
            return " ".join(s.text.strip() for s in segments)

        with ThreadPoolExecutor(max_workers=2) as pool:
            future_fr = pool.submit(run_fr, self._model)
            future_en = pool.submit(run_en, self._model2)
            text_fr = future_fr.result()
            text_en = future_en.result()

        log.info("Transcript FR: %s", text_fr)
        log.info("Transcript EN: %s", text_en)
        return text_fr, text_en

    def _transcribe_single(self, audio_path: Path) -> str:
        segments, _ = self._model.transcribe(
            str(audio_path),
            language=self.language or "fr",
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        parts = []
        for segment in segments:
            parts.append(segment.text.strip())
            if self.on_text:
                self.on_text(" ".join(parts))
        return " ".join(parts)

    def _transcribe_bilingual_from_file(self, audio_path: Path) -> str:
        """Transcribe file in both FR and EN in parallel, then fuse locally."""
        text_fr, text_en = self.transcribe_bilingual_raw(audio_path)

        if self.on_status:
            self.on_status("Fusion FR/EN…")
        log.info("Fusing transcripts locally...")
        result = fuse_local(text_fr, text_en)
        log.info("Fusion result: %s", result)
        return result

