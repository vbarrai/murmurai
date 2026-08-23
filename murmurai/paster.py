"""Clipboard-based text injection.

Pasting goes through ``NSPasteboard`` + a synthetic Cmd+V posted with
``CGEvent``. The older implementation shelled out to ``osascript`` /
``System Events``, which required a third macOS permission (Automation) on top
of Accessibility and spawned a process on every paste. ``CGEvent`` only needs
Accessibility — which murmurai already requires for its hotkey event tap.
"""

from __future__ import annotations

import logging
import time

import AppKit
import Quartz

log = logging.getLogger("murmurai")

_VK_V = 0x09

# The pasteboard write is asynchronous from the target app's point of view:
# posting Cmd+V immediately after clearContents()/setString() makes the target
# read the *previous* contents. 60 ms is enough for the write to propagate.
_PASTE_DELAY = 0.06

# How long to wait after Cmd+V before putting the user's clipboard back.
_RESTORE_DELAY = 0.15


def _get_clipboard():
    """Return (data_by_type, types) from the general pasteboard, or (None, None) if empty."""
    pb = AppKit.NSPasteboard.generalPasteboard()
    types = pb.types()
    if not types:
        return None, None
    data_by_type = {}
    for t in types:
        data = pb.dataForType_(t)
        if data:
            data_by_type[t] = data
    return data_by_type, types


def _set_clipboard(data_by_type, types):
    """Restore pasteboard contents from a previous _get_clipboard() snapshot."""
    pb = AppKit.NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.declareTypes_owner_(types, None)
    for t in types:
        data = data_by_type.get(t)
        if data:
            pb.setData_forType_(data, t)


def _get_focused_element():
    """Return the AXFocusedUIElement of the frontmost application."""
    import ApplicationServices as AS

    frontmost = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    if not frontmost:
        return None
    pid = frontmost.processIdentifier()
    app_ref = AS.AXUIElementCreateApplication(pid)

    err, focused = AS.AXUIElementCopyAttributeValue(
        app_ref, AS.kAXFocusedUIElementAttribute, None,
    )
    if err == 0 and focused:
        return focused
    return None


def grab_selection() -> str:
    """Read the selected text from the focused UI element via Accessibility API.

    Returns the selected text, or empty string if nothing was selected.
    Does not simulate any keystrokes — reads directly from the AX tree.
    """
    import ApplicationServices as AS

    focused = _get_focused_element()
    if not focused:
        return ""

    err, value = AS.AXUIElementCopyAttributeValue(
        focused, AS.kAXSelectedTextAttribute, None,
    )
    if err == 0 and value:
        return str(value).strip()
    return ""


def _post_cmd_v():
    """Post a synthetic Cmd+V to the frontmost application.

    A *private* event source is used on purpose: the HID source would inherit
    the modifiers physically held down at that instant, and murmurai's
    push-to-talk keys are themselves modifiers (Right Option / Right Command).
    With a private source the only flag on the event is the one set here.
    """
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStatePrivate)

    down = Quartz.CGEventCreateKeyboardEvent(source, _VK_V, True)
    up = Quartz.CGEventCreateKeyboardEvent(source, _VK_V, False)
    Quartz.CGEventSetFlags(down, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventSetFlags(up, Quartz.kCGEventFlagMaskCommand)

    Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)


def replace_text(original: str, replacement: str):
    """Replace the currently selected text with replacement by pasting over it."""
    paste_text(replacement)


def paste_text(text: str):
    """Paste text at the current cursor position, preserving the clipboard.

    The previous clipboard contents are put back only if nothing else wrote to
    the pasteboard in the meantime — otherwise restoring would clobber a copy
    the user made while the transcription was running.
    """
    if not text:
        return

    pb = AppKit.NSPasteboard.generalPasteboard()
    saved_data, saved_types = _get_clipboard()

    pb.clearContents()
    pb.setString_forType_(text, AppKit.NSPasteboardTypeString)
    change_count = pb.changeCount()

    time.sleep(_PASTE_DELAY)
    _post_cmd_v()
    time.sleep(_RESTORE_DELAY)

    if pb.changeCount() != change_count:
        log.info("Clipboard changed during paste, not restoring previous contents")
        return

    if saved_data is not None:
        _set_clipboard(saved_data, saved_types)
    else:
        pb.clearContents()
