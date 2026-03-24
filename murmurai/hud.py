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


class HUDOverlay:
    """A centered, semi-transparent HUD window that shows a status message."""

    def __init__(self):
        self._window: AppKit.NSWindow | None = None
        self._label: AppKit.NSTextField | None = None
        self._spinner: AppKit.NSProgressIndicator | None = None

    def show(self, message: str = "Processing…"):
        """Show the HUD."""
        _on_main(self._show_on_main, message)

    def update(self, message: str):
        """Update the HUD message."""
        _on_main(self._update_on_main, message)

    def hide(self):
        """Hide and destroy the HUD."""
        _on_main(self._hide_on_main)

    def _show_on_main(self, message: str):
        width, height = 280, 80

        # Get screen center
        screen = AppKit.NSScreen.mainScreen()
        screen_frame = screen.frame()
        x = (screen_frame.size.width - width) / 2
        y = (screen_frame.size.height - height) / 2

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
        content = AppKit.NSVisualEffectView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, width, height)
        )
        content.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow)
        content.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
        content.setState_(AppKit.NSVisualEffectStateActive)
        content.setWantsLayer_(True)
        content.layer().setCornerRadius_(16)
        content.layer().setMasksToBounds_(True)
        self._window.setContentView_(content)

        # Spinner
        self._spinner = AppKit.NSProgressIndicator.alloc().initWithFrame_(
            AppKit.NSMakeRect(20, (height - 24) / 2, 24, 24)
        )
        self._spinner.setStyle_(AppKit.NSProgressIndicatorStyleSpinning)
        self._spinner.setControlSize_(AppKit.NSControlSizeSmall)
        self._spinner.startAnimation_(None)
        content.addSubview_(self._spinner)

        # Label
        self._label = AppKit.NSTextField.labelWithString_(message)
        self._label.setFrame_(AppKit.NSMakeRect(52, (height - 20) / 2, width - 68, 20))
        self._label.setTextColor_(AppKit.NSColor.whiteColor())
        self._label.setFont_(AppKit.NSFont.systemFontOfSize_weight_(14, AppKit.NSFontWeightMedium))
        self._label.setAlignment_(AppKit.NSTextAlignmentLeft)
        content.addSubview_(self._label)

        self._window.orderFrontRegardless()

    def _update_on_main(self, message: str):
        if self._label:
            self._label.setStringValue_(message)

    def _hide_on_main(self):
        if self._window:
            self._window.orderOut_(None)
            self._window = None
            self._label = None
            self._spinner = None
