from __future__ import annotations

import logging
import queue
from pathlib import Path
from typing import Optional

import numpy as np
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
        self._model = WhisperModel(model_size, device=device, compute_type="int8")

    def transcribe(self, audio_path: Path) -> str:
        segments, _ = self._model.transcribe(
            str(audio_path),
            language=self.language,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        return " ".join(segment.text.strip() for segment in segments)

    def transcribe_stream(self, chunk_queue: queue.Queue) -> str:
        """Consume audio chunks from a queue and transcribe incrementally.

        Each chunk is an int16 numpy array. A None sentinel signals end of stream.
        In bilingual mode, streams with the primary language during recording,
        then does a final dual-language pass + Ollama fusion at the end.
        """
        all_chunks: list[np.ndarray] = []
        text = ""
        new_audio = False

        while True:
            chunk = chunk_queue.get()
            if chunk is None:
                break
            all_chunks.append(chunk)
            new_audio = True

            # Drain any additional queued chunks
            while not chunk_queue.empty():
                chunk = chunk_queue.get()
                if chunk is None:
                    if new_audio and all_chunks:
                        text = self._finalize(all_chunks)
                        log.info("Final transcript: %s", text)
                    return text
                all_chunks.append(chunk)

            # Streaming preview (single language for speed)
            text = self._transcribe_buffer(all_chunks)
            new_audio = False
            log.info("Streaming transcript: %s", text)

        if new_audio and all_chunks:
            text = self._finalize(all_chunks)
            log.info("Final transcript: %s", text)

        return text

    def _finalize(self, chunks: list[np.ndarray]) -> str:
        """Final transcription — bilingual fusion if enabled."""
        if not self.bilingual:
            return self._transcribe_buffer(chunks)
        return self._transcribe_bilingual(chunks)

    def _transcribe_bilingual(self, chunks: list[np.ndarray]) -> str:
        """Transcribe in both FR and EN, then fuse via Ollama."""
        audio = self._prepare_audio(chunks)
        if audio is None:
            return ""

        log.info("Bilingual transcription: running FR + EN passes...")

        # Run both transcriptions sequentially (model is not thread-safe)
        text_fr = self._run_transcription(audio, language="fr")
        text_en = self._run_transcription(audio, language="en")

        log.info("Transcript FR: %s", text_fr)
        log.info("Transcript EN: %s", text_en)

        # Fuse via Ollama
        log.info("Fusing transcripts via Ollama...")
        return fuse_transcripts(text_fr, text_en)

    def _run_transcription(self, audio: np.ndarray, language: str) -> str:
        segments, _ = self._model.transcribe(
            audio,
            language=language,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        return " ".join(segment.text.strip() for segment in segments)

    def _prepare_audio(self, chunks: list[np.ndarray]) -> Optional[np.ndarray]:
        audio = np.concatenate(chunks).flatten().astype(np.float32) / 32768.0
        if len(audio) < 16000 * 0.3:
            return None
        return audio

    def _transcribe_buffer(self, chunks: list[np.ndarray]) -> str:
        audio = self._prepare_audio(chunks)
        if audio is None:
            return ""
        return self._run_transcription(
            audio, language=self.language or "fr",
        )
