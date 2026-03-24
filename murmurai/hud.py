"""Floating HUD overlay for showing processing status."""

from __future__ import annotations

import threading

import AppKit
from PyObjCTools import AppHelper


def _on_main(fn, *args):
    """Run fn(*args) on the main thread."""
    if threading.current_thread() is threading.main_thread():
        fn(*args)
    else:
        AppHelper.callAfter(fn, *args)


def _truncate(text: str, max_len: int = 80) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


class HUDOverlay:
    """A centered, semi-transparent HUD window with title and optional detail lines."""

    def __init__(self):
        self._window: AppKit.NSWindow | None = None
        self._title_label: AppKit.NSTextField | None = None
        self._detail_label: AppKit.NSTextField | None = None
        self._spinner: AppKit.NSProgressIndicator | None = None
        self._content: AppKit.NSVisualEffectView | None = None

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

        width = 400
        has_detail = bool(detail.strip())
        height = 100 if has_detail else 60

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
        self._detail_label = AppKit.NSTextField.labelWithString_(
            _truncate(detail) if detail else ""
        )
        self._detail_label.setFrame_(AppKit.NSMakeRect(20, 12, width - 40, 36))
        self._detail_label.setTextColor_(
            AppKit.NSColor.secondaryLabelColor()
        )
        self._detail_label.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        self._detail_label.setMaximumNumberOfLines_(2)
        self._detail_label.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
        self._detail_label.setHidden_(not has_detail)
        self._content.addSubview_(self._detail_label)

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

        # Resize window if detail toggled
        new_height = 100 if has_detail else 60
        frame = self._window.frame()
        if abs(frame.size.height - new_height) > 1:
            screen = AppKit.NSScreen.mainScreen()
            sf = screen.frame()
            frame.origin.y = (sf.size.height - new_height) / 2
            frame.size.height = new_height
            self._window.setFrame_display_animate_(frame, True, False)

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

    def _hide_on_main(self):
        if self._window:
            self._window.orderOut_(None)
            self._window = None
            self._title_label = None
            self._detail_label = None
            self._spinner = None
            self._content = None
