import logging
import multiprocessing
import subprocess
import threading
import time
from pathlib import Path

import rumps
import Quartz
from Quartz import (
    CGEventMaskBit,
    CGEventTapCreate,
    CFMachPortCreateRunLoopSource,
    CFRunLoopGetCurrent,
    CFRunLoopAddSource,
    CFRunLoopRun,
    kCGEventFlagsChanged,
    kCGEventTapOptionDefault,
    kCGHeadInsertEventTap,
    kCGSessionEventTap,
    kCFRunLoopCommonModes,
)

from murmurai.paster import paste_text
from murmurai.recorder import AudioRecorder
from murmurai.transcriber import LocalTranscriber

log = logging.getLogger("murmurai")

# Right Option key code
_kVK_RightOption = 0x3D
# Alternate/Option flag
_kCGEventFlagMaskAlternate = 0x00080000


def _check_accessibility() -> bool:
    """Check if the app has accessibility permission."""
    tap = CGEventTapCreate(
        kCGSessionEventTap,
        kCGHeadInsertEventTap,
        kCGEventTapOptionDefault,
        CGEventMaskBit(kCGEventFlagsChanged),
        lambda *args: args[2],
        None,
    )
    if tap is None:
        return False
    del tap
    return True


def _check_system_events() -> bool:
    """Check if the app has System Events (Automation) permission by doing a test call."""
    result = subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to return ""'],
        capture_output=True,
    )
    return result.returncode == 0


class MurmurAIApp(rumps.App):
    def __init__(self):
        super().__init__("murmurai", icon=None, title="🎤")
        log.info("Loading Whisper model...")
        self.recorder = AudioRecorder()
        self.transcriber = LocalTranscriber()
        log.info("Model loaded, ready.")
        self._is_recording = False

        # Menu items
        self.menu = [
            rumps.MenuItem("murmurai — Push-to-Talk", callback=None),
            None,  # separator
            rumps.MenuItem("Hotkey: Right Option (hold)", callback=None),
            None,
        ]

    def _check_permissions_at_startup(self):
        """Check all permissions at startup. Let macOS prompt the user."""
        # Step 1: Check accessibility — triggers macOS prompt if not granted
        if not _check_accessibility():
            log.info("Accessibility permission not granted, macOS will prompt")
            # Poll until granted
            def wait_for_accessibility():
                while not _check_accessibility():
                    time.sleep(2)
                log.info("Accessibility permission granted")
                # Now check System Events
                self._check_and_setup_paste()
            threading.Thread(target=wait_for_accessibility, daemon=True).start()
            return

        log.info("Accessibility permission OK")
        self._check_and_setup_paste()

    def _check_and_setup_paste(self):
        """Check System Events permission, then setup event tap."""
        if not _check_system_events():
            log.info("System Events permission not granted, macOS will prompt")
            # Poll until granted
            def wait_for_system_events():
                while not _check_system_events():
                    time.sleep(2)
                log.info("System Events permission granted")
                self._setup_event_tap()
                rumps.notification("murmurai", "Ready", "Hold Right Option to record.")
            threading.Thread(target=wait_for_system_events, daemon=True).start()
            return

        log.info("System Events permission OK")
        self._setup_event_tap()

    def _setup_event_tap(self):
        """Create the CGEventTap for the Right Option key."""
        log.info("Listening for Right Option key (hold to record)")

        def callback(proxy, event_type, event, refcon):
            keycode = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeycode
            )
            flags = Quartz.CGEventGetFlags(event)

            if keycode == _kVK_RightOption:
                option_down = bool(flags & _kCGEventFlagMaskAlternate)
                if option_down and not self._is_recording:
                    self._start_recording()
                elif not option_down and self._is_recording:
                    self._stop_recording_and_transcribe()

            return event

        mask = CGEventMaskBit(kCGEventFlagsChanged)
        tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionDefault,
            mask,
            callback,
            None,
        )

        if tap is None:
            log.error("Failed to create event tap")
            return

        log.info("Event tap created successfully")
        source = CFMachPortCreateRunLoopSource(None, tap, 0)

        def run_tap():
            loop = CFRunLoopGetCurrent()
            CFRunLoopAddSource(loop, source, kCFRunLoopCommonModes)
            CFRunLoopRun()

        threading.Thread(target=run_tap, daemon=True).start()

    def _start_recording(self):
        self._is_recording = True
        self.title = "🔴"
        log.info("Recording started")
        self.recorder.start()
        self._start_stuck_guard()

    def _start_stuck_guard(self):
        """Safety net: if key release event is lost (e.g. macOS dialog steals focus),
        stop recording after detecting the key is no longer held."""
        def guard():
            while self._is_recording:
                time.sleep(0.5)
                # Check if Option key is currently held by reading modifier flags
                flags = Quartz.CGEventSourceFlagsState(
                    Quartz.kCGEventSourceStateHIDSystemState
                )
                option_held = bool(flags & _kCGEventFlagMaskAlternate)
                if not option_held and self._is_recording:
                    log.info("Stuck recording detected, stopping")
                    self._stop_recording_and_transcribe()
                    break
        threading.Thread(target=guard, daemon=True).start()

    def _stop_recording_and_transcribe(self):
        self._is_recording = False
        self.title = "⏳"

        audio_path = self.recorder.stop()
        if audio_path is None:
            log.info("Recording too short, skipped")
            self.title = "🎤"
            return

        log.info("Recording stopped, saved to %s", audio_path)

        # Transcribe in background thread
        def do_transcribe():
            try:
                log.info("Transcribing...")
                text = self.transcriber.transcribe(audio_path)
                log.info("Transcription: %s", text)
                paste_text(text)
                log.info("Text pasted to cursor")
            except Exception as e:
                log.error("Transcription failed: %s", e)
                rumps.notification("murmurai", "Error", str(e))
            finally:
                self.title = "🎤"
                # Clean up temp file
                try:
                    audio_path.unlink()
                except OSError:
                    pass

        threading.Thread(target=do_transcribe, daemon=True).start()


def main():
    multiprocessing.freeze_support()

    log_file = Path.home() / "Library" / "Logs" / "murmurai" / "murmurai.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file),
        ],
    )
    app = MurmurAIApp()
    app._check_permissions_at_startup()
    app.run()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
