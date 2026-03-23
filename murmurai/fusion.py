"""Bilingual transcript fusion via a local Ollama model."""

from __future__ import annotations

import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

log = logging.getLogger("murmurai")

_DEFAULT_OLLAMA_URL = "http://localhost:11434"
_DEFAULT_MODEL = "gpt-oss:20b"

_SYSTEM_PROMPT = (
    "You are a bilingual transcript merger. "
    "The user spoke in a mix of French and English. "
    "You receive two transcriptions of the SAME audio: one forced in French, one forced in English. "
    "Your job is to produce the single best transcript that keeps each segment in its original language. "
    "Rules:\n"
    "- Keep French parts in French and English parts in English.\n"
    "- Fix obvious transcription errors by cross-referencing both versions.\n"
    "- Do NOT translate anything. Preserve the speaker's language choices.\n"
    "- Technical terms commonly used in English even by French speakers must stay in English. "
    "Use the English transcript to detect them. "
    "Examples: commit, push, pull, merge, deploy, debug, refactor, build, release, sprint, "
    "feature, bug, issue, branch, tag, review, test, API, endpoint, frontend, backend, database, "
    "cloud, server, docker, container, pipeline, etc.\n"
    "- Output ONLY the merged transcript, nothing else.\n"
)


def fuse_transcripts(
    transcript_fr: str,
    transcript_en: str,
    *,
    ollama_url: str = _DEFAULT_OLLAMA_URL,
    model: str = _DEFAULT_MODEL,
    timeout: float = 30,
) -> str:
    """Merge a French and English transcript using Ollama.

    Falls back to the French transcript if Ollama is unreachable.
    """
    if not transcript_fr and not transcript_en:
        return ""
    if not transcript_fr:
        return transcript_en
    if not transcript_en:
        return transcript_fr

    user_msg = (
        f"=== French transcription ===\n{transcript_fr}\n\n"
        f"=== English transcription ===\n{transcript_en}"
    )

    payload = json.dumps({
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
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
            log.info("Ollama fusion result: %s", result)
            return result
        log.warning("Ollama returned empty content, falling back to FR transcript")
        return transcript_fr
    except (URLError, OSError, json.JSONDecodeError, KeyError) as exc:
        log.warning("Ollama fusion failed (%s), falling back to FR transcript", exc)
        return transcript_fr


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
