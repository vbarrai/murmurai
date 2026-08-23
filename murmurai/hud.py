"""Floating HUD overlay for showing processing status."""

from __future__ import annotations

import threading
from typing import Callable, List, Optional

import AppKit
import objc
from PyObjCTools import AppHelper

_WIDTH = 500
_PADDING = 12
_TITLE_HEIGHT = 20
_WAVE_HEIGHT = 28
_GAP = 8

# Number of bars kept in the scrolling waveform.
_WAVE_BARS = 60


class _CloseButtonTarget(AppKit.NSObject):
    """ObjC target for the HUD close button."""

    callback = None

    @objc.python_method
    def initWithCallback_(self, cb):
        self = objc.super(_CloseButtonTarget, self).init()
        self.callback = cb
        return self

    @objc.IBAction
    def closeClicked_(self, sender):
        if self.callback:
            self.callback()


class _WaveformView(AppKit.NSView):
    """A scrolling bar waveform fed with 0..1 levels from the recorder."""

    levels = None

    @objc.python_method
    def initWithFrame_(self, frame):
        self = objc.super(_WaveformView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.levels = [0.0] * _WAVE_BARS
        return self

    @objc.python_method
    def pushLevel(self, level: float):
        if self.levels is None:
            self.levels = [0.0] * _WAVE_BARS
        self.levels.append(max(0.0, min(1.0, float(level))))
        del self.levels[:-_WAVE_BARS]
        self.setNeedsDisplay_(True)

    def drawRect_(self, rect):
        levels: List[float] = self.levels or []
        if not levels:
            return
        bounds = self.bounds()
        count = len(levels)
        slot = bounds.size.width / count
        bar_width = max(2.0, slot - 2.0)
        mid = bounds.size.height / 2

        AppKit.NSColor.whiteColor().colorWithAlphaComponent_(0.85).setFill()
        for index, level in enumerate(levels):
            height = max(2.0, level * bounds.size.height)
            bar = AppKit.NSMakeRect(
                index * slot + (slot - bar_width) / 2,
                mid - height / 2,
                bar_width,
                height,
            )
            path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                bar, bar_width / 2, bar_width / 2,
            )
            path.fill()


def _on_main(fn, *args):
    """Run fn(*args) on the main thread."""
    if threading.current_thread() is threading.main_thread():
        fn(*args)
    else:
        AppHelper.callAfter(fn, *args)


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


class HUDOverlay:
    """A centered, semi-transparent HUD window with title and optional detail lines."""

    def __init__(self):
        self._window: AppKit.NSWindow | None = None
        self._title_label: AppKit.NSTextField | None = None
        self._detail_label: AppKit.NSTextField | None = None
        self._spinner: AppKit.NSProgressIndicator | None = None
        self._waveform: _WaveformView | None = None
        self._content: AppKit.NSVisualEffectView | None = None
        self._close_window: AppKit.NSWindow | None = None
        self._btn_target = None
        self._detail = ""
        self._waveform_enabled = False
        self.on_cancel: Optional[Callable] = None

    def show(self, message: str = "Processing…", detail: str = "", waveform: bool = False):
        """Show the HUD, optionally with a live waveform strip."""
        _on_main(self._show_on_main, message, detail, waveform)

    def update(self, message: str, detail: str = ""):
        """Update the HUD message and detail."""
        _on_main(self._update_on_main, message, detail)

    def set_level(self, level: float):
        """Feed one audio level into the waveform. No-op when it is hidden."""
        if not self._waveform_enabled:
            return
        _on_main(self._set_level_on_main, level)

    def hide(self):
        """Hide and destroy the HUD."""
        _on_main(self._hide_on_main)

    def _set_level_on_main(self, level: float):
        if self._waveform is not None:
            self._waveform.pushLevel(level)

    def _show_on_main(self, message: str, detail: str, waveform: bool = False):
        # Hide existing window if any
        self._hide_on_main()

        self._detail = detail
        self._waveform_enabled = waveform
        layout = _layout(detail, waveform)
        height = layout["height"]
        has_detail = bool(detail.strip())

        # Get screen center
        screen = AppKit.NSScreen.mainScreen()
        sf = screen.frame()
        x = (sf.size.width - _WIDTH) / 2
        y = (sf.size.height - height) / 2

        # Create borderless window
        self._window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(x, y, _WIDTH, height),
            AppKit.NSWindowStyleMaskBorderless,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        self._window.setLevel_(AppKit.NSStatusWindowLevel + 1)
        self._window.setOpaque_(False)
        self._window.setBackgroundColor_(AppKit.NSColor.clearColor())
        self._window.setIgnoresMouseEvents_(True)
        self._window.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorStationary
        )

        # Content view with rounded dark background
        self._content = AppKit.NSVisualEffectView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, _WIDTH, height)
        )
        self._content.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow)
        self._content.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
        self._content.setState_(AppKit.NSVisualEffectStateActive)
        self._content.setWantsLayer_(True)
        self._content.layer().setCornerRadius_(16)
        self._content.layer().setMasksToBounds_(True)
        self._window.setContentView_(self._content)

        # Spinner, vertically centered on the title line
        self._spinner = AppKit.NSProgressIndicator.alloc().initWithFrame_(
            AppKit.NSMakeRect(20, layout["title_y"] - 2, 24, 24)
        )
        self._spinner.setStyle_(AppKit.NSProgressIndicatorStyleSpinning)
        self._spinner.setControlSize_(AppKit.NSControlSizeSmall)
        self._spinner.startAnimation_(None)
        self._content.addSubview_(self._spinner)

        # Title label
        self._title_label = AppKit.NSTextField.labelWithString_(message)
        self._title_label.setFrame_(
            AppKit.NSMakeRect(52, layout["title_y"], _WIDTH - 68, _TITLE_HEIGHT)
        )
        self._title_label.setTextColor_(AppKit.NSColor.whiteColor())
        self._title_label.setFont_(
            AppKit.NSFont.systemFontOfSize_weight_(14, AppKit.NSFontWeightMedium)
        )
        self._content.addSubview_(self._title_label)

        # Waveform strip
        if waveform:
            self._waveform = _WaveformView.alloc().initWithFrame_(
                AppKit.NSMakeRect(20, layout["wave_y"], _WIDTH - 40, _WAVE_HEIGHT)
            )
            self._content.addSubview_(self._waveform)

        # Detail label
        self._detail_label = AppKit.NSTextField.labelWithString_(
            _truncate(detail) if detail else ""
        )
        self._detail_label.setFrame_(
            AppKit.NSMakeRect(
                20, layout.get("detail_y", _PADDING),
                _WIDTH - 40, max(36, layout["detail_height"]),
            )
        )
        self._detail_label.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        self._detail_label.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        self._detail_label.setMaximumNumberOfLines_(0)  # unlimited lines
        self._detail_label.setLineBreakMode_(AppKit.NSLineBreakByWordWrapping)
        self._detail_label.setHidden_(not has_detail)
        self._content.addSubview_(self._detail_label)

        # Close button in a separate clickable child window
        btn_size = 24
        self._close_window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(
                x + _WIDTH - btn_size - 8, y + height - btn_size - 8, btn_size, btn_size,
            ),
            AppKit.NSWindowStyleMaskBorderless,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        self._close_window.setLevel_(AppKit.NSStatusWindowLevel + 2)
        self._close_window.setOpaque_(False)
        self._close_window.setBackgroundColor_(AppKit.NSColor.clearColor())
        self._close_window.setIgnoresMouseEvents_(False)

        self._btn_target = _CloseButtonTarget.alloc().initWithCallback_(
            self._on_cancel_clicked,
        )
        btn = AppKit.NSButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, btn_size, btn_size),
        )
        btn.setBezelStyle_(AppKit.NSBezelStyleInline)
        btn.setTitle_("✕")
        btn.setTarget_(self._btn_target)
        btn.setAction_(b"closeClicked:")
        btn.setBordered_(False)
        btn.setFont_(AppKit.NSFont.systemFontOfSize_(12))
        btn.setContentTintColor_(AppKit.NSColor.secondaryLabelColor())
        self._close_window.contentView().addSubview_(btn)

        self._window.addChildWindow_ordered_(self._close_window, AppKit.NSWindowAbove)
        self._window.orderFrontRegardless()

    def _update_on_main(self, message: str, detail: str):
        if not self._window:
            self._show_on_main(message, detail, self._waveform_enabled)
            return

        self._detail = detail
        if self._title_label:
            self._title_label.setStringValue_(message)

        has_detail = bool(detail.strip())
        if self._detail_label:
            self._detail_label.setStringValue_(_truncate(detail) if detail else "")
            self._detail_label.setHidden_(not has_detail)

        # Resize window dynamically based on content
        layout = _layout(detail, self._waveform_enabled)
        new_height = layout["height"]
        frame = self._window.frame()
        if abs(frame.size.height - new_height) <= 1:
            return

        screen = AppKit.NSScreen.mainScreen()
        sf = screen.frame()
        frame.origin.y = (sf.size.height - new_height) / 2
        frame.size.height = new_height
        self._window.setFrame_display_animate_(frame, True, False)

        if self._content:
            self._content.setFrame_(AppKit.NSMakeRect(0, 0, _WIDTH, new_height))
        if self._spinner:
            sp = self._spinner.frame()
            sp.origin.y = layout["title_y"] - 2
            self._spinner.setFrame_(sp)
        if self._title_label:
            tf = self._title_label.frame()
            tf.origin.y = layout["title_y"]
            self._title_label.setFrame_(tf)
        if self._waveform is not None and "wave_y" in layout:
            wf = self._waveform.frame()
            wf.origin.y = layout["wave_y"]
            self._waveform.setFrame_(wf)
        if self._detail_label:
            self._detail_label.setFrame_(
                AppKit.NSMakeRect(
                    20, layout.get("detail_y", _PADDING),
                    _WIDTH - 40, max(36, layout["detail_height"]),
                )
            )
        if self._close_window:
            btn_size = 24
            self._close_window.setFrame_display_(
                AppKit.NSMakeRect(
                    frame.origin.x + _WIDTH - btn_size - 8,
                    frame.origin.y + new_height - btn_size - 8,
                    btn_size, btn_size,
                ),
                True,
            )

    def _on_cancel_clicked(self):
        if self.on_cancel:
            self.on_cancel()

    def _hide_on_main(self):
        if self._close_window:
            self._close_window.orderOut_(None)
            self._close_window = None
            self._btn_target = None
        if self._window:
            self._window.orderOut_(None)
            self._window = None
            self._title_label = None
            self._detail_label = None
            self._spinner = None
            self._waveform = None
            self._content = None
        self._waveform_enabled = False
