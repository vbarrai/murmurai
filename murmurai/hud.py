"""Floating HUD overlay for showing processing status."""

from __future__ import annotations

import threading
from typing import Callable, Optional

import AppKit
import objc
from PyObjCTools import AppHelper


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


class HUDOverlay:
    """A centered, semi-transparent HUD window with title and optional detail lines."""

    def __init__(self):
        self._window: AppKit.NSWindow | None = None
        self._title_label: AppKit.NSTextField | None = None
        self._detail_label: AppKit.NSTextField | None = None
        self._spinner: AppKit.NSProgressIndicator | None = None
        self._content: AppKit.NSVisualEffectView | None = None
        self._close_window: AppKit.NSWindow | None = None
        self._btn_target = None
        self.on_cancel: Optional[Callable] = None

    def show(self, message: str = "Processing…", detail: str = ""):
        """Show the HUD."""
        _on_main(self._show_on_main, message, detail)

    def update(self, message: str, detail: str = ""):
        """Update the HUD message and detail."""
        _on_main(self._update_on_main, message, detail)

    def hide(self):
        """Hide and destroy the HUD."""
        _on_main(self._hide_on_main)

    def _show_on_main(self, message: str, detail: str):
        # Hide existing window if any
        self._hide_on_main()

        width = 500
        has_detail = bool(detail.strip())
        # Count lines to size the window dynamically
        detail_lines = _estimate_lines(detail) if has_detail else 0
        height = 60 + max(0, detail_lines) * 16 + (20 if has_detail else 0)

        # Get screen center
        screen = AppKit.NSScreen.mainScreen()
        sf = screen.frame()
        x = (sf.size.width - width) / 2
        y = (sf.size.height - height) / 2

        # Create borderless window
        self._window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(x, y, width, height),
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
            AppKit.NSMakeRect(0, 0, width, height)
        )
        self._content.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow)
        self._content.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
        self._content.setState_(AppKit.NSVisualEffectStateActive)
        self._content.setWantsLayer_(True)
        self._content.layer().setCornerRadius_(16)
        self._content.layer().setMasksToBounds_(True)
        self._window.setContentView_(self._content)

        # Spinner
        spinner_y = height - 38 if has_detail else (height - 24) / 2
        self._spinner = AppKit.NSProgressIndicator.alloc().initWithFrame_(
            AppKit.NSMakeRect(20, spinner_y, 24, 24)
        )
        self._spinner.setStyle_(AppKit.NSProgressIndicatorStyleSpinning)
        self._spinner.setControlSize_(AppKit.NSControlSizeSmall)
        self._spinner.startAnimation_(None)
        self._content.addSubview_(self._spinner)

        # Title label
        title_y = height - 38 if has_detail else (height - 20) / 2
        self._title_label = AppKit.NSTextField.labelWithString_(message)
        self._title_label.setFrame_(AppKit.NSMakeRect(52, title_y, width - 68, 20))
        self._title_label.setTextColor_(AppKit.NSColor.whiteColor())
        self._title_label.setFont_(
            AppKit.NSFont.systemFontOfSize_weight_(14, AppKit.NSFontWeightMedium)
        )
        self._content.addSubview_(self._title_label)

        # Detail label
        detail_height = max(36, detail_lines * 16)
        self._detail_label = AppKit.NSTextField.labelWithString_(
            _truncate(detail) if detail else ""
        )
        self._detail_label.setFrame_(AppKit.NSMakeRect(20, 12, width - 40, detail_height))
        self._detail_label.setTextColor_(
            AppKit.NSColor.secondaryLabelColor()
        )
        self._detail_label.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        self._detail_label.setMaximumNumberOfLines_(0)  # unlimited lines
        self._detail_label.setLineBreakMode_(AppKit.NSLineBreakByWordWrapping)
        self._detail_label.setHidden_(not has_detail)
        self._content.addSubview_(self._detail_label)

        # Close button in a separate clickable child window
        btn_size = 24
        btn_x = x + width - btn_size - 8
        btn_y = y + height - btn_size - 8
        self._close_window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(btn_x, btn_y, btn_size, btn_size),
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
            self._show_on_main(message, detail)
            return

        if self._title_label:
            self._title_label.setStringValue_(message)

        has_detail = bool(detail.strip())
        if self._detail_label:
            self._detail_label.setStringValue_(_truncate(detail) if detail else "")
            self._detail_label.setHidden_(not has_detail)

        # Resize window dynamically based on content
        detail_lines = _estimate_lines(detail) if has_detail else 0
        new_height = 60 + max(0, detail_lines) * 16 + (20 if has_detail else 0)
        width = 500
        frame = self._window.frame()
        if abs(frame.size.height - new_height) > 1:
            screen = AppKit.NSScreen.mainScreen()
            sf = screen.frame()
            frame.origin.y = (sf.size.height - new_height) / 2
            frame.size.height = new_height
            self._window.setFrame_display_animate_(frame, True, False)

            # Resize content view
            if self._content:
                self._content.setFrame_(AppKit.NSMakeRect(0, 0, width, new_height))

            # Reposition spinner and title
            spinner_y = new_height - 38 if has_detail else (new_height - 24) / 2
            title_y = new_height - 38 if has_detail else (new_height - 20) / 2
            if self._spinner:
                sf2 = self._spinner.frame()
                sf2.origin.y = spinner_y
                self._spinner.setFrame_(sf2)
            if self._title_label:
                tf = self._title_label.frame()
                tf.origin.y = title_y
                self._title_label.setFrame_(tf)

            # Resize detail label
            if self._detail_label:
                detail_height = max(36, detail_lines * 16)
                self._detail_label.setFrame_(
                    AppKit.NSMakeRect(20, 12, width - 40, detail_height)
                )

            # Reposition close button
            if self._close_window:
                btn_size = 24
                self._close_window.setFrame_display_(
                    AppKit.NSMakeRect(
                        frame.origin.x + width - btn_size - 8,
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
            self._content = None
