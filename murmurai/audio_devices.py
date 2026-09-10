"""Microphone selection.

murmurai records through whichever input device the user picked in the menu
bar; ``None`` means "follow the macOS system default". Devices are addressed by
name rather than by index because indices are reassigned whenever a device is
plugged or unplugged, whereas the name survives a reconnect.
"""

from __future__ import annotations

import logging
from typing import Optional

import sounddevice as sd

log = logging.getLogger("murmurai")


def list_input_devices() -> list[dict]:
    """Return the available input devices as ``[{"name": ..., "index": ...}]``.

    Output-only devices are filtered out. Duplicate names are de-duplicated
    (the first index wins) so the menu stays unambiguous.
    """
    try:
        devices = sd.query_devices()
    except Exception as exc:  # sounddevice raises bare Exceptions on HAL errors
        log.warning("Could not query audio devices: %s", exc)
        return []

    seen: set[str] = set()
    inputs = []
    for index, device in enumerate(devices):
        if device.get("max_input_channels", 0) <= 0:
            continue
        name = device.get("name", "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        inputs.append({"name": name, "index": index})
    return inputs


def default_input_name() -> Optional[str]:
    """Return the name of the current system default input device."""
    try:
        index = sd.default.device[0]
        if index is None or index < 0:
            return None
        return sd.query_devices(index)["name"]
    except Exception:
        return None


def resolve_device(name: Optional[str]) -> Optional[int]:
    """Resolve a device name to a sounddevice index.

    Returns ``None`` for an empty name (use the system default) and also when
    the named device is not currently connected — recording then falls back to
    the system default instead of failing outright.
    """
    if not name:
        return None
    for device in list_input_devices():
        if device["name"] == name:
            return device["index"]
    log.warning("Microphone %r not connected, falling back to system default", name)
    return None
