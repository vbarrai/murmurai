"""Centralized configuration — all settings in ~/.config/murmurai/config.json."""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("murmurai")

_CONFIG_FILE = Path.home() / ".config" / "murmurai" / "config.json"

_DEFAULTS = {
    "whisper_model": "small",
    "bilingual": True,
    "transcript_key": "Right Option",
    "agent_key": "Right Command",
    "agent_model": "gpt-oss:20b",
    # User jargon: additional terms merged on top of built-in jargon.
    # Format: {"english_term": ["french_variant1", "french_variant2"]}
    "jargon": {
        "kubectl": ["kubecétéèle", "kubeucétéèle"],
        "terraform": ["terraformer"],
    },
}


def load() -> dict:
    """Load config from disk, merging with defaults for any missing keys."""
    config = dict(_DEFAULTS)
    if _CONFIG_FILE.exists():
        try:
            user = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            config.update(user)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Could not read config (%s), using defaults", exc)
    else:
        save(config)
    return config


def save(config: dict):
    """Write config to disk."""
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
