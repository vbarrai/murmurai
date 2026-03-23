import subprocess
import time

import AppKit


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


def paste_text(text: str):
    """Paste text at the current cursor position, preserving the clipboard."""
    # Save current clipboard
    saved_data, saved_types = _get_clipboard()

    # Copy transcribed text to clipboard via pbcopy
    env = {**subprocess.os.environ, "LANG": "en_US.UTF-8"}
    process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, env=env)
    process.communicate(text.encode("utf-8"))

    # Small delay to ensure clipboard is ready
    time.sleep(0.05)

    # Simulate Cmd+V via osascript
    subprocess.run(
        [
            "osascript",
            "-e",
            'tell application "System Events" to keystroke "v" using command down',
        ],
        check=True,
    )

    # Wait for the paste to complete, then restore clipboard
    time.sleep(0.1)
    if saved_data is not None:
        _set_clipboard(saved_data, saved_types)
    else:
        AppKit.NSPasteboard.generalPasteboard().clearContents()
