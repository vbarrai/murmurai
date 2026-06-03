"""Centralized configuration — all settings in ~/.config/murmurai/config.json."""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("murmurai")

CONFIG_FILE = Path.home() / ".config" / "murmurai" / "config.json"
_CONFIG_FILE = CONFIG_FILE  # backward-compatible alias

_DEFAULTS = {
    "whisper_model": "small",
    "transcript_key": "Right Option",
    "agent_key": "Right Command",
    "agent_model": "gemma3:latest",
    # User jargon: additional terms merged on top of built-in jargon.
    # Format: {"english_term": ["french_variant1", "french_variant2"]}
    "jargon": {
        "kubectl": ["kubecétéèle", "kubeucétéèle"],
        "terraform": ["terraformer"],
    },
}


def load() -> dict:
    """Load config from disk, merging with defaults for any missing keys.

    The file is never created or rewritten here: a missing or invalid file
    simply yields the defaults. Persisting only happens on explicit user
    actions (a menu change, or opening "Edit Settings…").
    """
    config = dict(_DEFAULTS)
    if _CONFIG_FILE.exists():
        try:
            user = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            config.update(user)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Could not read config (%s), using defaults", exc)
    return config


def is_file_valid() -> bool:
    """Report whether the config file on disk is usable.

    A missing file is valid: load() recreates it from defaults. Only a file
    that exists but contains unparseable JSON — typically a botched hand edit
    via "Edit Settings…" — is reported as invalid so the UI can flag it.
    """
    if not _CONFIG_FILE.exists():
        return True
    try:
        json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        return True
    except (json.JSONDecodeError, OSError):
        return False


def save(config: dict):
    """Write config to disk."""
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
