"""Launch at login.

Implemented with a per-user LaunchAgent rather than ``SMAppService``: the
ServiceManagement bridge is not part of the PyObjC set murmurai depends on, and
a plist in ``~/Library/LaunchAgents`` needs no extra dependency and no
privileged access.

Only meaningful for an installed ``.app``. When murmurai runs from source there
is no bundle to relaunch, so the feature reports itself as unavailable and the
menu item is greyed out.
"""

from __future__ import annotations

import logging
import plistlib
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("murmurai")

LABEL = "com.vbarrai.murmurai"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def app_bundle_path() -> Path | None:
    """Return the enclosing ``.app`` bundle, or None when running from source."""
    executable = Path(sys.executable).resolve()
    for parent in executable.parents:
        if parent.suffix == ".app":
            return parent
    return None


def is_available() -> bool:
    """Whether launch-at-login can be configured in this install."""
    return app_bundle_path() is not None


def is_enabled() -> bool:
    """Whether the LaunchAgent is currently installed."""
    return PLIST_PATH.exists()


def _launchctl(*args) -> bool:
    try:
        subprocess.run(
            ["launchctl", *args], capture_output=True, check=False, timeout=10,
        )
        return True
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("launchctl %s failed: %s", " ".join(args), exc)
        return False


def set_enabled(enabled: bool) -> bool:
    """Install or remove the LaunchAgent. Returns the resulting state."""
    bundle = app_bundle_path()
    if bundle is None:
        log.info("Launch at login unavailable (not running from an .app bundle)")
        return False

    if not enabled:
        if PLIST_PATH.exists():
            _launchctl("bootout", f"gui/{_uid()}/{LABEL}")
            PLIST_PATH.unlink(missing_ok=True)
            log.info("Launch at login disabled")
        return False

    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    plist = {
        "Label": LABEL,
        # `open -a` rather than the inner executable: it goes through
        # LaunchServices, so macOS treats the process as the bundled app and
        # keeps the Accessibility / Microphone grants attached to it.
        "ProgramArguments": ["/usr/bin/open", "-a", str(bundle)],
        "RunAtLoad": True,
        "KeepAlive": False,
    }
    PLIST_PATH.write_bytes(plistlib.dumps(plist))
    _launchctl("bootstrap", f"gui/{_uid()}", str(PLIST_PATH))
    log.info("Launch at login enabled (%s)", bundle)
    return True


def _uid() -> int:
    import os

    return os.getuid()
