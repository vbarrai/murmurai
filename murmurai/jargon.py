"""Technical jargon: English terms with their French-ified variants.

The built-in jargon ships with the app and is updated on upgrades.
User jargon from config.json is merged on top (additions/overrides).
"""

from __future__ import annotations

import re
import logging

from murmurai.config import load

log = logging.getLogger("murmurai")

# Built-in jargon: English term → list of French-ified variants Whisper may produce.
# Lowercase variants are matched case-insensitively.
# Only franglais variants — words Whisper may write when English terms are
# pronounced with a French accent.  Real French words (pousser, fusion, …)
# are NOT listed here because Whisper already transcribes the actual English
# word correctly when it is spoken in English.
BUILTIN_JARGON: dict[str, list[str]] = {
    # Git / version control
    "commit": ["commiter", "comité", "comite", "commette"],
    "push": ["poucher", "pouche"],
    "pull": ["puller"],
    "merge": ["merger"],
    "rebase": ["rebaser"],
    "cherry-pick": ["cherry-picker"],
    "stash": ["stasher"],
    "checkout": ["checker"],
    "fetch": ["fetcher"],
    "fork": ["forker"],
    "tag": ["taguer", "tagger"],
    "diff": ["differ"],
    "squash": ["squasher"],
    "reset": ["reseter"],
    "revert": ["reverter", "riverte"],
    "empty": ["empti", "emti", "emptie"],
    # Development workflow
    "deploy": ["deployer"],
    "release": ["releaser"],
    "build": ["builder"],
    "debug": ["débugger", "debugger", "débugguer"],
    "refactor": ["refactorer", "refactoriser"],
    "review": ["reviewer"],
    "sprint": ["sprinter"],
    "backlog": ["backloguer"],
    "ticket": ["ticketer"],
    "feature": ["featurer"],
    "hotfix": ["hotfixer"],
    "bugfix": ["bugfixer"],
    "rollback": ["rollbacker"],
    "staging": ["stager"],
    # Code concepts
    "frontend": ["front-end"],
    "backend": ["back-end"],
    "fullstack": ["full-stack"],
    "stream": ["streamer"],
    # Data
    "seed": ["seeder"],
    "delete": ["déleter"],
    # Testing
    "mock": ["mocker"],
    "stub": ["stuber"],
    # Misc
    "fix": ["fixe"],
    "true": ["trou"],
    "README": ["rythmi", "rythme y", "read me"],
}


def load_jargon() -> dict[str, list[str]]:
    """Return merged jargon: built-in + user additions from config."""
    merged = dict(BUILTIN_JARGON)
    user_jargon = load().get("jargon", {})

    if isinstance(user_jargon, dict):
        for term, variants in user_jargon.items():
            if term in merged:
                # Merge variants, avoid duplicates
                existing = set(merged[term])
                for v in variants:
                    if v not in existing:
                        merged[term].append(v)
            else:
                merged[term] = list(variants)
    elif isinstance(user_jargon, list):
        # Legacy format (plain list) — add as terms with no variants
        for term in user_jargon:
            if term not in merged:
                merged[term] = []

    return merged


def fix_jargon(text: str) -> str:
    """Replace franglais variants with their English originals.

    Instant — no LLM call needed.
    """
    if not text:
        return ""

    jargon = load_jargon()
    result = text

    for english_term, variants in jargon.items():
        for variant in variants:
            if not variant:
                continue
            pattern = re.compile(re.escape(variant), re.IGNORECASE)
            if pattern.search(result):
                result = pattern.sub(english_term, result)
                log.debug("Jargon: '%s' → '%s'", variant, english_term)

    return result
