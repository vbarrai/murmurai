#!/usr/bin/env sh
# maconfai-update hook
#
# Triggered at the start of an agent session (Claude Code: SessionStart,
# Cursor: sessionStart). When an `ai-lock.json` is present at the
# project root, run `npx maconfai update` so maconfai-managed skills,
# MCP servers, and hooks stay in sync with their upstream sources.
#
# The hook is intentionally non-blocking: any failure is swallowed so an
# offline machine or transient npm error never breaks the agent session.

set -u

# Resolve project root. Claude Code and Cursor both invoke hooks from the
# project root, but fall back to the script's grandparent dir
# (.agents/hooks/maconfai-update/ -> project root) if CWD is unexpected.
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
if [ ! -f "$PROJECT_ROOT/ai-lock.json" ]; then
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
fi

# No lockfile -> nothing maconfai-managed here, exit silently.
if [ ! -f "$PROJECT_ROOT/ai-lock.json" ]; then
  exit 0
fi

# npx is required. If unavailable, surface a hint on stderr but don't block.
if ! command -v npx >/dev/null 2>&1; then
  echo "[maconfai-update] npx not found in PATH; skipping update check." >&2
  exit 0
fi

cd "$PROJECT_ROOT" || exit 0

# `maconfai update` is non-interactive and applies available updates.
# Run with a short timeout-ish behavior via background + wait isn't portable;
# rely on the agent's own hook timeout. stderr/stdout go to the agent so the
# user sees what changed.
npx --yes maconfai update 2>&1 || true

exit 0
