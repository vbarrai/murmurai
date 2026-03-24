from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel

from murmurai.fusion import fuse_transcripts

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
        self.fusion_model: Optional[str] = None
        self.on_status: Optional[callable] = None
        self._model_size = model_size
        self._device = device
        self._model = WhisperModel(model_size, device=device, compute_type="int8")
        # Second model instance for parallel bilingual transcription
        self._model2: Optional[WhisperModel] = None

    def transcribe(self, audio_path: Path) -> str:
        if self.bilingual:
            return self._transcribe_bilingual_from_file(audio_path)
        segments, _ = self._model.transcribe(
            str(audio_path),
            language=self.language or "fr",
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        return " ".join(segment.text.strip() for segment in segments)

    def _transcribe_bilingual_from_file(self, audio_path: Path) -> str:
        """Transcribe file in both FR and EN in parallel, then fuse."""
        if self._model2 is None:
            log.info("Loading second Whisper model for parallel bilingual...")
            self._model2 = WhisperModel(
                self._model_size, device=self._device, compute_type="int8",
            )

        if self.on_status:
            self.on_status("Transcription FR + EN…")
        log.info("Bilingual transcription: running FR + EN passes in parallel...")
        path_str = str(audio_path)

        def run(model, lang):
            segments, _ = model.transcribe(
                path_str, language=lang, beam_size=1,
                vad_filter=True, condition_on_previous_text=False,
            )
            return " ".join(s.text.strip() for s in segments)

        with ThreadPoolExecutor(max_workers=2) as pool:
            future_fr = pool.submit(run, self._model, "fr")
            future_en = pool.submit(run, self._model2, "en")
            text_fr = future_fr.result()
            text_en = future_en.result()

        log.info("Transcript FR: %s", text_fr)
        log.info("Transcript EN: %s", text_en)

        if self.on_status:
            self.on_status("Fusion FR/EN…")
        log.info("Fusing transcripts via Ollama...")
        kwargs = {}
        if self.fusion_model:
            kwargs["model"] = self.fusion_model
        return fuse_transcripts(text_fr, text_en, **kwargs)

