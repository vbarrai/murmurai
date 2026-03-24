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
    "fusion_model": "qwen2.5-coder:0.5b",
    "agent_model": "gpt-oss:20b",
    "jargon": [
        # Git / version control
        "commit", "push", "pull", "merge", "rebase", "cherry-pick", "stash",
        "branch", "checkout", "clone", "fetch", "fork", "tag", "diff", "blame",
        "squash", "reset", "revert",
        # Development workflow
        "deploy", "release", "build", "debug", "refactor", "review",
        "sprint", "standup", "backlog", "ticket", "issue", "feature",
        "hotfix", "bugfix", "rollback", "staging", "production",
        # Code concepts
        "API", "endpoint", "frontend", "backend", "fullstack",
        "framework", "library", "package", "module", "plugin",
        "import", "export", "async", "await", "callback", "promise",
        "middleware", "proxy", "cache", "router", "handler",
        "payload", "token", "webhook", "socket", "stream",
        "runtime", "compiler", "linter", "formatter",
        # Infrastructure / DevOps
        "cloud", "server", "cluster", "container", "pod", "namespace",
        "pipeline", "workflow", "CI/CD", "DevOps",
        "docker", "Kubernetes", "load balancer",
        # Data
        "database", "query", "schema", "migration", "seed",
        "index", "join", "insert", "update", "delete",
        # Testing
        "test", "mock", "stub", "fixture", "coverage",
        "unit test", "integration test", "end-to-end",
        # Tools / technologies
        "TypeScript", "JavaScript", "Python", "React", "Node.js",
        "Git", "GitHub", "GitLab", "VS Code", "Slack",
        "Jira", "Confluence", "Notion", "Figma",
        # Agile / project
        "scrum", "kanban", "roadmap", "milestone", "deadline",
        "pull request", "code review", "pair programming",
        "onboarding", "offboarding",
    ],
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
