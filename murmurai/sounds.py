"""Short system sounds marking the start/end of an operation.

Audio feedback lets you use push-to-talk without looking at the HUD. Enabled
by default; toggled from the menu bar or via ``"sounds"`` in config.json.
"""

from __future__ import annotations

import logging

import AppKit

log = logging.getLogger("murmurai")

# Event name → macOS system sound. These ship with every macOS install, so
# nothing needs to be bundled.
_SOUNDS = {
    "start": "Tink",
    "stop": "Pop",
    "done": "Glass",
    "cancel": "Funk",
}


def play(event: str):
    """Play the sound for ``event``; silently does nothing if unavailable."""
    name = _SOUNDS.get(event)
    if not name:
        return
    sound = AppKit.NSSound.soundNamed_(name)
    if sound is None:
        log.debug("System sound %r not available", name)
        return
    # Restart from the beginning if the previous one is still playing.
    if sound.isPlaying():
        sound.stop()
    sound.play()
