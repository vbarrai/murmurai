import logging
import multiprocessing
import queue
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

# Hotkey options: each entry maps a display name to (keycode, flag_mask)
_HOTKEY_OPTIONS = [
    ("Right Option",  0x3D, 0x00080000),
    ("Left Option",   0x3A, 0x00080000),
    ("Right Control", 0x3E, 0x00040000),
    ("Left Control",  0x3B, 0x00040000),
    ("Right Command", 0x36, 0x00100000),
    ("Left Command",  0x37, 0x00100000),
    ("Right Shift",   0x3C, 0x00020000),
    ("Left Shift",    0x38, 0x00020000),
    ("Fn",            0x3F, 0x00800000),
    ("Caps Lock",     0x39, 0x00010000),
]
_DEFAULT_HOTKEY = "Right Option"



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


def _check_microphone() -> bool:
    """Check if the app has microphone permission by trying a short recording."""
    import AVFoundation
    status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
        AVFoundation.AVMediaTypeAudio
    )
    if status == AVFoundation.AVAuthorizationStatusAuthorized:
        return True
    if status == AVFoundation.AVAuthorizationStatusNotDetermined:
        # Request permission — this triggers the macOS prompt
        granted = [False]
        event = threading.Event()

        def handler(granted_val):
            granted[0] = granted_val
            event.set()

        AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            AVFoundation.AVMediaTypeAudio, handler
        )
        event.wait(timeout=30)
        return granted[0]
    return False


_MODEL_SIZES = ["tiny", "base", "small", "medium", "large-v3"]
_DEFAULT_MODEL = "small"


class MurmurAIApp(rumps.App):
    def __init__(self):
        super().__init__("murmurai", icon=None, title="🎤")
        self._current_model = _DEFAULT_MODEL
        self._current_hotkey = _DEFAULT_HOTKEY
        self._hotkey_keycode, self._hotkey_flag_mask = self._get_hotkey_params(
            self._current_hotkey
        )
        self._bilingual = True

        log.info("Loading Whisper model (%s)...", self._current_model)
        self.recorder = AudioRecorder()
        self.transcriber = LocalTranscriber(
            model_size=self._current_model, bilingual=self._bilingual,
        )
        log.info("Model loaded, ready.")
        self._is_recording = False
        self._pending_quit = False

        # Model selection submenu
        self._model_menu = rumps.MenuItem("Model")
        for size in _MODEL_SIZES:
            item = rumps.MenuItem(size, callback=self._on_model_selected)
            if size == self._current_model:
                item.state = True
            self._model_menu.add(item)

        # Hotkey selection submenu
        self._hotkey_menu = rumps.MenuItem("Hotkey")
        for name, _, _ in _HOTKEY_OPTIONS:
            item = rumps.MenuItem(name, callback=self._on_hotkey_selected)
            if name == self._current_hotkey:
                item.state = True
            self._hotkey_menu.add(item)

        # Bilingual toggle
        self._bilingual_item = rumps.MenuItem(
            "Bilingual FR/EN", callback=self._on_bilingual_toggled,
        )
        self._bilingual_item.state = self._bilingual

        # Menu items
        self.menu = [
            rumps.MenuItem("murmurai — Push-to-Talk", callback=None),
            None,  # separator
            self._hotkey_menu,
            self._model_menu,
            self._bilingual_item,
            None,
            rumps.MenuItem("Open Logs…", callback=self._open_logs),
            None,
        ]

    def _on_bilingual_toggled(self, sender):
        if self._is_recording:
            return
        self._bilingual = not self._bilingual
        sender.state = self._bilingual
        self.transcriber.bilingual = self._bilingual
        log.info("Bilingual mode: %s", "ON" if self._bilingual else "OFF")

    def _on_model_selected(self, sender):
        if sender.title == self._current_model:
            return
        if self._is_recording:
            return
        previous = self._current_model
        self._current_model = sender.title
        # Update checkmarks
        for size in _MODEL_SIZES:
            self._model_menu[size].state = size == self._current_model
        # Reload model in background
        self.title = "⏳"
        log.info("Switching model from %s to %s...", previous, self._current_model)

        def reload():
            try:
                self.transcriber = LocalTranscriber(
                    model_size=self._current_model, bilingual=self._bilingual,
                )
                log.info("Model %s loaded.", self._current_model)
            except Exception as e:
                log.error("Failed to load model %s: %s", self._current_model, e)
                self._current_model = previous
                for size in _MODEL_SIZES:
                    self._model_menu[size].state = size == self._current_model
            finally:
                self.title = "🎤"

        threading.Thread(target=reload, daemon=True).start()

    @staticmethod
    def _get_hotkey_params(name: str) -> tuple[int, int]:
        for hk_name, keycode, flag_mask in _HOTKEY_OPTIONS:
            if hk_name == name:
                return keycode, flag_mask
        return _HOTKEY_OPTIONS[0][1], _HOTKEY_OPTIONS[0][2]

    def _on_hotkey_selected(self, sender):
        if sender.title == self._current_hotkey:
            return
        if self._is_recording:
            return
        self._current_hotkey = sender.title
        self._hotkey_keycode, self._hotkey_flag_mask = self._get_hotkey_params(
            self._current_hotkey
        )
        for name, _, _ in _HOTKEY_OPTIONS:
            self._hotkey_menu[name].state = name == self._current_hotkey
        log.info("Hotkey changed to %s", self._current_hotkey)

    def _open_logs(self, _):
        log_file = Path.home() / "Library" / "Logs" / "murmurai" / "murmurai.log"
        subprocess.Popen(["open", str(log_file)])

    @rumps.timer(1)
    def _check_pending_quit(self, _):
        """Check if we need to show the quit dialog (must run on main thread)."""
        if self._pending_quit:
            self._pending_quit = False
            rumps.alert(
                title="murmurai",
                message="All permissions granted. Please reopen murmurai for changes to take effect.",
                ok="Quit",
            )
            rumps.quit_application()

    def _check_permissions_at_startup(self):
        """Check all permissions at startup. Let macOS prompt the user."""
        # Step 1: Check accessibility — triggers macOS prompt if not granted
        if not _check_accessibility():
            log.info("Accessibility permission not granted, macOS will prompt")
            def wait_for_accessibility():
                while not _check_accessibility():
                    time.sleep(2)
                log.info("Accessibility permission granted")
                self._check_microphone()
            threading.Thread(target=wait_for_accessibility, daemon=True).start()
            return

        log.info("Accessibility permission OK")
        self._check_microphone()

    def _check_microphone(self):
        """Check microphone permission, then proceed to System Events check."""
        if not _check_microphone():
            log.info("Microphone permission not granted, polling...")
            def wait_for_microphone():
                while not _check_microphone():
                    time.sleep(2)
                log.info("Microphone permission granted")
                self._check_and_setup_paste()
            threading.Thread(target=wait_for_microphone, daemon=True).start()
            return

        log.info("Microphone permission OK")
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
                self._pending_quit = True
            threading.Thread(target=wait_for_system_events, daemon=True).start()
            return

        log.info("System Events permission OK")
        self._setup_event_tap()

    def _setup_event_tap(self):
        """Create the CGEventTap for the selected hotkey."""
        log.info("Listening for %s key (hold to record)", self._current_hotkey)

        def callback(proxy, event_type, event, refcon):
            keycode = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeycode
            )
            flags = Quartz.CGEventGetFlags(event)

            if keycode == self._hotkey_keycode:
                key_down = bool(flags & self._hotkey_flag_mask)
                if key_down and not self._is_recording:
                    self._start_recording()
                elif not key_down and self._is_recording:
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

        # Create streaming pipeline
        self._chunk_queue = queue.Queue()
        self._transcript_result = ""

        # Start transcription consumer thread (processes chunks as they arrive)
        def consume():
            try:
                self._transcript_result = self.transcriber.transcribe_stream(
                    self._chunk_queue
                )
            except Exception as e:
                log.error("Streaming transcription failed: %s", e)
                self._transcript_result = ""

        self._transcribe_thread = threading.Thread(target=consume, daemon=True)
        self._transcribe_thread.start()

        # Start recording with chunk streaming
        self.recorder.start(chunk_queue=self._chunk_queue)
        self._start_stuck_guard()

    def _start_stuck_guard(self):
        """Safety net: if key release event is lost (e.g. macOS dialog steals focus),
        stop recording after detecting the key is no longer held."""
        def guard():
            while self._is_recording:
                time.sleep(0.5)
                flags = Quartz.CGEventSourceFlagsState(
                    Quartz.kCGEventSourceStateHIDSystemState
                )
                key_held = bool(flags & self._hotkey_flag_mask)
                if not key_held and self._is_recording:
                    log.info("Stuck recording detected, stopping")
                    self._stop_recording_and_transcribe()
                    break
        threading.Thread(target=guard, daemon=True).start()

    def _stop_recording_and_transcribe(self):
        self._is_recording = False
        self.title = "⏳"
        log.info("Recording stopped, finalizing transcription...")

        # Stop recording — flushes remaining audio + sentinel to queue
        self.recorder.stop()

        def finalize():
            try:
                # Wait for transcription thread to finish processing all chunks
                self._transcribe_thread.join(timeout=15)
                text = self._transcript_result.strip()
                if text:
                    log.info("Final transcription: %s", text)
                    paste_text(text)
                    log.info("Text pasted to cursor")
                else:
                    log.info("No transcription result")
            except Exception as e:
                log.error("Finalization failed: %s", e)
                rumps.notification("murmurai", "Error", str(e))
            finally:
                self.title = "🎤"

        threading.Thread(target=finalize, daemon=True).start()


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
