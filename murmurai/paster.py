import subprocess
import time


def paste_text(text: str):
    """Paste text at the current cursor position using pbcopy + Cmd+V."""
    # Copy text to clipboard via pbcopy
    process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
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
