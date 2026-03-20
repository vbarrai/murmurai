from __future__ import annotations

import logging
import queue
from pathlib import Path
from typing import Optional

import numpy as np
from faster_whisper import WhisperModel

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
        Returns the final transcription text.
        """
        all_chunks: list[np.ndarray] = []
        text = ""
        new_audio = False

        while True:
            # Wait for next chunk
            chunk = chunk_queue.get()
            if chunk is None:
                break
            all_chunks.append(chunk)
            new_audio = True

            # Drain any additional queued chunks to avoid re-transcribing
            # multiple times when chunks pile up during a slow transcription
            while not chunk_queue.empty():
                chunk = chunk_queue.get()
                if chunk is None:
                    # Got sentinel while draining — finalize
                    if new_audio and all_chunks:
                        text = self._transcribe_buffer(all_chunks)
                        log.info("Final transcript: %s", text)
                    return text
                all_chunks.append(chunk)

            text = self._transcribe_buffer(all_chunks)
            new_audio = False
            log.info("Streaming transcript: %s", text)

        # Final transcription only if new audio since last transcription
        if new_audio and all_chunks:
            text = self._transcribe_buffer(all_chunks)
            log.info("Final transcript: %s", text)

        return text

    def _transcribe_buffer(self, chunks: list[np.ndarray]) -> str:
        audio = np.concatenate(chunks).flatten().astype(np.float32) / 32768.0

        # Skip if too short
        if len(audio) < 16000 * 0.3:
            return ""

        segments, _ = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        return " ".join(segment.text.strip() for segment in segments)
