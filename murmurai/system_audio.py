"""Mute the system output while recording.

Optional (off by default): when enabled, whatever is playing through the
speakers is muted for the duration of the recording so it is not picked up by
the microphone, then restored. Uses AppleScript's built-in ``set volume``,
which lives in osascript itself and — unlike ``System Events`` — needs no
Automation permission.
"""

from __future__ import annotations

import logging
import subprocess

log = logging.getLogger("murmurai")


def _osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=5,
    )
    if result.returncode != 0:
        raise OSError(result.stderr.strip())
    return result.stdout.strip()


class OutputMuter:
    """Mutes the default output device and restores its previous state.

    ``restore()`` is a no-op when ``mute()`` never ran or already failed, so it
    is safe to call unconditionally from a ``finally`` block.
    """

    def __init__(self):
        self._was_muted: bool | None = None

    def mute(self):
        if self._was_muted is not None:
            return  # already muted by us
        try:
            self._was_muted = _osascript(
                "output muted of (get volume settings)") == "true"
            if not self._was_muted:
                _osascript("set volume output muted true")
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("Could not mute output: %s", exc)
            self._was_muted = None

    def restore(self):
        if self._was_muted is None:
            return
        was_muted, self._was_muted = self._was_muted, None
        if was_muted:
            return  # it was already muted before us — leave it alone
        try:
            _osascript("set volume output muted false")
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("Could not restore output volume: %s", exc)
