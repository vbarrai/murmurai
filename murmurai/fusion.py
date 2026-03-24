"""Ollama agent functions for voice assistant."""

from __future__ import annotations

import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

log = logging.getLogger("murmurai")

_DEFAULT_OLLAMA_URL = "http://localhost:11434"
_DEFAULT_MODEL = "gpt-oss:20b"


_AGENT_SYSTEM_PROMPT = (
    "You are a text transformation assistant.\n"
    "The user selects text on screen, then dictates a voice instruction.\n"
    "The 'Selected text' is the SUBJECT — the text to transform.\n"
    "The 'Voice instruction' tells you WHAT to do with it "
    "(e.g. 'simplify this sentence', 'translate to English', 'make it shorter').\n"
    "Rules:\n"
    "- Apply the instruction to the selected text.\n"
    "- Output ONLY the resulting text. Nothing else.\n"
    "- No preamble, no explanation, no quotes, no formatting around it.\n"
    "- Your output will directly replace the selected text, so it must be ready to use as-is.\n"
    "- Respond in the same language as the selected text, unless the instruction says otherwise."
)

_AGENT_BILINGUAL_SYSTEM_PROMPT = (
    "You are a voice assistant. The user spoke in a mix of French and English.\n"
    "You receive TWO transcriptions of the SAME audio: one forced in French, one in English.\n"
    "The French one has the correct sentence structure but may frenchify English technical terms.\n"
    "The English one helps you identify which words were actually said in English.\n\n"
    "If a 'Selected text' section is provided, it is the SUBJECT of the user's instruction.\n"
    "Apply the voice instruction to that text.\n\n"
    "Rules:\n"
    "- Understand the user's intent by cross-referencing both transcripts.\n"
    "- If there is selected text, apply the instruction to it.\n"
    "- Output ONLY the resulting text. Nothing else.\n"
    "- No preamble, no explanation, no quotes, no formatting around it.\n"
    "- Your output will directly replace the selected text, so it must be ready to use as-is.\n"
    "- Respond in the same language as the selected text, unless the instruction says otherwise."
)


def ask_agent(
    transcript: str,
    *,
    selection: str = "",
    ollama_url: str = _DEFAULT_OLLAMA_URL,
    model: str = _DEFAULT_MODEL,
    timeout: float = 60,
) -> str:
    """Send the transcript (and optional selected text) to Ollama and return the response.

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
        "stream": False,
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
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        result = data.get("message", {}).get("content", "").strip()
        if result:
            log.info("Ollama agent response: %s", result)
            return result
        log.warning("Ollama agent returned empty content, falling back to transcript")
        return transcript
    except (URLError, OSError, json.JSONDecodeError, KeyError) as exc:
        log.warning("Ollama agent failed (%s), falling back to transcript", exc)
        return transcript


def ask_agent_bilingual(
    transcript_fr: str,
    transcript_en: str,
    *,
    selection: str = "",
    ollama_url: str = _DEFAULT_OLLAMA_URL,
    model: str = _DEFAULT_MODEL,
    timeout: float = 60,
) -> str:
    """Send both FR/EN transcripts + selection to Ollama in a single call.

    Skips the fusion step — the agent interprets both transcripts directly.
    Falls back to the FR transcript if Ollama is unreachable.
    """
    if not transcript_fr and not transcript_en:
        return ""

    parts = []
    if selection:
        log.info("Agent bilingual — selection: %s", selection[:200])
        parts.append(f"=== Selected text ===\n{selection}")
    parts.append(f"=== Voice instruction (French) ===\n{transcript_fr}")
    parts.append(f"=== Voice instruction (English) ===\n{transcript_en}")
    user_content = "\n\n".join(parts)
    log.info("Agent bilingual — FR: %s | EN: %s", transcript_fr, transcript_en)

    payload = json.dumps({
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": _AGENT_BILINGUAL_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    }).encode()

    req = Request(
        f"{ollama_url}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    fallback = transcript_fr or transcript_en
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        result = data.get("message", {}).get("content", "").strip()
        if result:
            log.info("Ollama agent bilingual response: %s", result)
            return result
        log.warning("Ollama agent returned empty, falling back to FR transcript")
        return fallback
    except (URLError, OSError, json.JSONDecodeError, KeyError) as exc:
        log.warning("Ollama agent bilingual failed (%s), falling back", exc)
        return fallback
