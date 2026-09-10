"""Tests for the HUD's bottom-up layout arithmetic.

The layout is pure geometry, so it is checked without ever creating a window.
It lives in ``murmurai.hud_layout`` rather than ``murmurai.hud`` precisely so
this module imports on the Linux CI runner: ``murmurai.hud`` needs pyobjc and
is replaced by a stub there (see ``tests/conftest.py``).
"""

from murmurai.hud_layout import (
    _GAP,
    _PADDING,
    _TITLE_HEIGHT,
    _WAVE_HEIGHT,
    _layout,
)


def test_title_only():
    layout = _layout("", waveform=False)

    assert layout["title_y"] == _PADDING
    assert layout["height"] == _PADDING * 2 + _TITLE_HEIGHT
    assert "wave_y" not in layout
    assert "detail_y" not in layout


def test_waveform_sits_below_the_title():
    layout = _layout("", waveform=True)

    assert layout["wave_y"] == _PADDING
    assert layout["title_y"] == _PADDING + _WAVE_HEIGHT + _GAP
    assert layout["height"] > _layout("", waveform=False)["height"]


def test_detail_sits_below_the_waveform():
    layout = _layout("hello", waveform=True)

    assert layout["detail_y"] < layout["wave_y"] < layout["title_y"]


def test_blank_detail_takes_no_space():
    assert _layout("   ", waveform=False) == _layout("", waveform=False)


def test_taller_detail_grows_the_window():
    short = _layout("one line", waveform=False)
    tall = _layout("\n".join(f"line {n}" for n in range(10)), waveform=False)

    assert tall["height"] > short["height"]
    assert tall["detail_height"] > short["detail_height"]
