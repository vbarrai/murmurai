from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import httpx


class OpenAITranscriber:
    """Transcribes audio using the OpenAI Whisper API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "whisper-1",
        language: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.language = language

    def transcribe(self, audio_path: Path) -> str:
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable."
            )

        with open(audio_path, "rb") as f:
            files = {"file": ("audio.wav", f, "audio/wav")}
            data = {"model": self.model}
            if self.language:
                data["language"] = self.language

            response = httpx.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files=files,
                data=data,
                timeout=30.0,
            )

        response.raise_for_status()
        return response.json()["text"]
