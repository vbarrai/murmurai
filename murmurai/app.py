import logging
import multiprocessing
import threading
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

    def start_hotkey_listener(self):
        """Start listening for the Right Option key using Quartz CGEventTap."""
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
            log.error(
                "Failed to create event tap — accessibility permission not granted"
            )
            rumps.notification(
                "murmurai",
                "Permission required",
                "Grant Accessibility access in System Settings > Privacy & Security",
            )
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
    app.start_hotkey_listener()
    app.run()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
