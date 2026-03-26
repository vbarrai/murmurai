"""Ollama agent functions for voice assistant."""

from __future__ import annotations

import json
import logging
from typing import Callable, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

log = logging.getLogger("murmurai")

_DEFAULT_OLLAMA_URL = "http://localhost:11434"
_DEFAULT_MODEL = "gemma3:latest"


_AGENT_SYSTEM_PROMPT = (
    "You are a text transformation assistant.\n"
    "The user selects text on screen, then dictates a voice instruction.\n"
    "The 'Selected text' is the SUBJECT — the text to transform.\n"
    "The 'Voice instruction' tells you WHAT to do with it "
    "(e.g. 'simplify this sentence', 'translate to English', 'make it shorter', "
    "'split into bullet points').\n"
    "Rules:\n"
    "- Apply the instruction to the selected text.\n"
    "- Output ONLY the resulting text. No preamble, no explanation.\n"
    "- Preserve formatting (newlines, lists, indentation) when appropriate.\n"
    "- Your output will directly replace the selected text, so it must be ready to use as-is.\n"
    "- Respond in the same language as the selected text, unless the instruction says otherwise."
)


def ask_agent(
    transcript: str,
    *,
    selection: str = "",
    ollama_url: str = _DEFAULT_OLLAMA_URL,
    model: str = _DEFAULT_MODEL,
    timeout: float = 120,
    on_token: Optional[Callable[[str], None]] = None,
    cancel_event=None,
) -> str:
    """Send the transcript (and optional selected text) to Ollama and return the response.

    If on_token is provided, streams the response and calls on_token with the
    accumulated text after each chunk.
    Falls back to the raw transcript if Ollama is unreachable.
    """
    if not transcript:
        return ""

    if selection:
        log.info("Agent context — selection: %s", selection[:200])
        log.info("Agent context — instruction: %s", transcript)
        user_content = (
            f"=== Selected text ===\n{selection}\n\n"
            f"=== Voice instruction ===\n{transcript}"
        )
    else:
        log.info("Agent context — instruction (no selection): %s", transcript)
        user_content = transcript

    payload = json.dumps({
        "model": model,
        "stream": True,
        "messages": [
            {"role": "system", "content": _AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    }).encode()

    req = Request(
        f"{ollama_url}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        result = ""
        with urlopen(req, timeout=timeout) as resp:
            for line in resp:
                if cancel_event and cancel_event.is_set():
                    log.info("Agent streaming cancelled")
                    return ""
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    result += token
                    if on_token:
                        on_token(result)
                if chunk.get("done"):
                    break

        result = result.strip()
        if result:
            log.info("Ollama agent (%s) response: %s", model, result)
            return result
        log.warning("Ollama agent returned empty content, falling back to transcript")
        return transcript
    except (URLError, OSError, json.JSONDecodeError, KeyError) as exc:
        log.warning("Ollama agent failed (%s), falling back to transcript", exc)
        return transcript
