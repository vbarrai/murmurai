"""Pure geometry for the HUD overlay.

Kept free of any pyobjc import (``AppKit``, ``objc``, ``PyObjCTools``) so the
layout arithmetic can be imported — and tested — on a Linux CI runner, where
those frameworks are unavailable and ``murmurai.hud`` is replaced by a stub.
"""

from __future__ import annotations

_WIDTH = 500
_PADDING = 12
_TITLE_HEIGHT = 20
_WAVE_HEIGHT = 28
_GAP = 8

# Number of bars kept in the scrolling waveform.
_WAVE_BARS = 60


def _truncate(text: str, max_len: int = 500) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


def _estimate_lines(text: str, chars_per_line: int = 60) -> int:
    """Estimate visual line count accounting for wrapping."""
    if not text:
        return 0
    lines = 0
    for line in text.split("\n"):
        lines += max(1, -(-len(line) // chars_per_line))  # ceil division
    return lines


def _detail_height(detail: str) -> float:
    """Height of the detail label for ``detail`` (0 when there is none)."""
    if not detail.strip():
        return 0.0
    return max(36, _estimate_lines(detail) * 16)


def _layout(detail: str, waveform: bool) -> dict:
    """Compute the HUD frames bottom-up.

    Returns the total height plus the y origin of each element, so the same
    arithmetic is used when the HUD is first shown and when it is resized on
    update.
    """
    detail_h = _detail_height(detail)
    y = _PADDING
    layout: dict = {"detail_height": detail_h}

    if detail_h:
        layout["detail_y"] = y
        y += detail_h + _GAP
    if waveform:
        layout["wave_y"] = y
        y += _WAVE_HEIGHT + _GAP

    layout["title_y"] = y
    y += _TITLE_HEIGHT + _PADDING
    layout["height"] = y
    return layout
