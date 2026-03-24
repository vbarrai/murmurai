"""Bilingual transcript fusion via a local Ollama model."""

from __future__ import annotations

import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

log = logging.getLogger("murmurai")

_DEFAULT_OLLAMA_URL = "http://localhost:11434"
_DEFAULT_MODEL = "gpt-oss:20b"
_DEFAULT_FUSION_MODEL = "qwen2.5-coder:7b"

_SYSTEM_PROMPT = (
    "You merge two transcriptions of the SAME audio into one.\n"
    "The speaker speaks FRENCH but uses ENGLISH technical terms.\n"
    "You receive: one transcript forced in French, one forced in English.\n\n"
    "Rules:\n"
    "- The output sentence structure MUST be in French.\n"
    "- Replace French-ified technical words with their English original from the EN transcript.\n"
    "- Examples: 'commettre' → 'commit', 'poucher/pousser' → 'push', 'tirer' → 'pull', "
    "'fusionner' → 'merge', 'déployer' → 'deploy', 'débugger' → 'debug', etc.\n"
    "- Do NOT translate the whole sentence to English. Keep French grammar and French words.\n"
    "- Output ONLY the merged sentence, nothing else.\n\n"
    "Example:\n"
    "FR: Est-ce que tu peux commettre et pousser les modifications ?\n"
    "EN: Can you commit and push the modifications?\n"
    "Output: Est-ce que tu peux commit et push les modifications ?\n"
)


def fuse_transcripts(
    transcript_fr: str,
    transcript_en: str,
    *,
    ollama_url: str = _DEFAULT_OLLAMA_URL,
    model: str = _DEFAULT_FUSION_MODEL,
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
