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

import murmurai.config as cfg
from murmurai.fusion import ask_agent, ask_agent_bilingual, _DEFAULT_OLLAMA_URL
from murmurai.hud import HUDOverlay
from murmurai.paster import grab_selection, paste_text, replace_text
from murmurai.recorder import AudioRecorder
from murmurai.transcriber import LocalTranscriber

log = logging.getLogger("murmurai")

# Key codes and their corresponding modifier flags
_HOTKEY_OPTIONS = {
    "Right Option":  (0x3D, 0x00080000),  # kVK_RightOption, kCGEventFlagMaskAlternate
    "Right Command": (0x36, 0x00100000),  # kVK_RightCommand, kCGEventFlagMaskCommand
    "Right Control": (0x3E, 0x00040000),  # kVK_RightControl, kCGEventFlagMaskControl
    "Left Option":   (0x3A, 0x00080000),  # kVK_LeftOption, kCGEventFlagMaskAlternate
    "Left Command":  (0x37, 0x00100000),  # kVK_LeftCommand, kCGEventFlagMaskCommand
    "Left Control":  (0x3B, 0x00040000),  # kVK_LeftControl, kCGEventFlagMaskControl
    "Right Shift":   (0x3C, 0x00020000),  # kVK_RightShift, kCGEventFlagMaskShift
    "Left Shift":    (0x38, 0x00020000),  # kVK_LeftShift, kCGEventFlagMaskShift
    "Fn":            (0x3F, 0x00800000),  # kVK_Function, kCGEventFlagMaskSecondaryFn
    "Caps Lock":     (0x39, 0x00010000),  # kVK_CapsLock, kCGEventFlagMaskAlphaShift
}

_DEFAULT_TRANSCRIPT_KEY = "Right Option"
_DEFAULT_AGENT_KEY = "Right Command"


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


def _list_ollama_models(ollama_url: str = _DEFAULT_OLLAMA_URL) -> list[str]:
    """Fetch available model names from Ollama."""
    import json
    from urllib.request import Request, urlopen
    from urllib.error import URLError

    try:
        req = Request(f"{ollama_url}/api/tags")
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return sorted(m["name"] for m in data.get("models", []))
    except (URLError, OSError, json.JSONDecodeError):
        log.warning("Could not fetch Ollama models")
        return []


class MurmurAIApp(rumps.App):
    def __init__(self):
        super().__init__("murmurai", icon=None, title="🎤")
        self._config = cfg.load()
        self._current_model = self._config["whisper_model"]
        self._bilingual = self._config["bilingual"]
        self._transcript_key = self._config["transcript_key"]
        self._agent_key = self._config["agent_key"]
        self._fusion_model = self._config["fusion_model"]
        self._agent_model = self._config["agent_model"]

        log.info("Loading Whisper model (%s)...", self._current_model)
        self.recorder = AudioRecorder()
        self.transcriber = LocalTranscriber(
            model_size=self._current_model, bilingual=self._bilingual,
        )
        self.transcriber.fusion_model = self._fusion_model
        self.transcriber.on_status = lambda msg: self._hud.update(msg)
        self.transcriber.on_text = lambda text: self._hud.update("Transcription…", text)
        log.info("Model loaded, ready.")
        self._is_recording = False
        self._agent_mode = False
        self._ollama_connected = False
        self._hud = HUDOverlay()
        self._pending_quit = False

        # Model selection submenu
        self._model_menu = rumps.MenuItem("Model")
        for size in _MODEL_SIZES:
            item = rumps.MenuItem(size, callback=self._on_model_selected)
            if size == self._current_model:
                item.state = True
            self._model_menu.add(item)

        # Hotkey submenus
        self._transcript_key_menu = rumps.MenuItem("Transcript key")
        for key_name in _HOTKEY_OPTIONS:
            item = rumps.MenuItem(key_name, callback=self._on_transcript_key_selected)
            item.state = key_name == self._transcript_key
            self._transcript_key_menu.add(item)

        self._agent_key_menu = rumps.MenuItem("Agent key")
        for key_name in _HOTKEY_OPTIONS:
            item = rumps.MenuItem(key_name, callback=self._on_agent_key_selected)
            item.state = key_name == self._agent_key
            self._agent_key_menu.add(item)

        # Bilingual toggle
        self._bilingual_item = rumps.MenuItem(
            "Bilingual FR/EN", callback=self._on_bilingual_toggled,
        )
        self._bilingual_item.state = self._bilingual

        # Ollama status + model submenus
        self._ollama_status_item = rumps.MenuItem(
            "Ollama: checking…", callback=lambda _: self._check_ollama_status(),
        )
        self._fusion_model_menu = rumps.MenuItem("Fusion model")
        self._agent_model_menu = rumps.MenuItem("Agent model")
        self._populate_ollama_menus()
        self._check_ollama_status()

        # Menu items
        self.menu = [
            rumps.MenuItem("murmurai — Push-to-Talk", callback=None),
            None,  # separator
            self._transcript_key_menu,
            self._agent_key_menu,
            self._model_menu,
            self._bilingual_item,
            None,
            self._ollama_status_item,
            self._fusion_model_menu,
            self._agent_model_menu,
            rumps.MenuItem("↻ Refresh Ollama", callback=lambda _: self._check_ollama_status()),
            None,
            rumps.MenuItem("Edit Settings…", callback=self._on_edit_settings),
            rumps.MenuItem("Open Logs…", callback=self._open_logs),
            None,
        ]

    def _check_ollama_status(self):
        """Check if Ollama server is reachable and update UI accordingly."""
        from urllib.request import Request, urlopen
        from urllib.error import URLError

        connected = False
        try:
            req = Request(f"{_DEFAULT_OLLAMA_URL}/api/tags")
            with urlopen(req, timeout=3) as resp:
                connected = resp.status == 200
        except (URLError, OSError):
            pass

        was_connected = self._ollama_connected
        self._ollama_connected = connected
        self._ollama_status_item.title = (
            "Ollama: ✓ connected" if connected else "Ollama: ✗ disconnected"
        )

        # Enable/disable bilingual toggle
        self._bilingual_item.set_callback(
            self._on_bilingual_toggled if connected else None
        )

        # Disable bilingual if disconnected
        if not connected and self._bilingual:
            self._bilingual = False
            self._bilingual_item.state = False
            self.transcriber.bilingual = False
            log.info("Bilingual mode disabled (Ollama disconnected)")

        # Always refresh model menus (status change or manual refresh)
        self._populate_ollama_menus()
        if connected != was_connected:
            log.info("Ollama %s", "connected" if connected else "disconnected")

    @rumps.timer(30)
    def _ollama_health_check(self, _):
        """Periodically check Ollama server status."""
        self._check_ollama_status()

    def _populate_ollama_menus(self):
        """Populate fusion and agent model submenus with available Ollama models."""
        models = _list_ollama_models()
        if not models:
            models = [self._fusion_model, self._agent_model]
            # deduplicate while preserving order
            seen = set()
            models = [m for m in models if not (m in seen or seen.add(m))]

        # Clear existing items (only if menu is already attached)
        try:
            self._fusion_model_menu.clear()
            self._agent_model_menu.clear()
        except AttributeError:
            pass

        # Use None callback to grey out items when Ollama is disconnected
        fusion_cb = self._on_fusion_model_selected if self._ollama_connected else None
        agent_cb = self._on_agent_model_selected if self._ollama_connected else None

        for name in models:
            item = rumps.MenuItem(name, callback=fusion_cb)
            item.state = name == self._fusion_model
            self._fusion_model_menu.add(item)

            item = rumps.MenuItem(name, callback=agent_cb)
            item.state = name == self._agent_model
            self._agent_model_menu.add(item)


    def _save_config(self):
        """Persist all current settings to config.json."""
        self._config.update({
            "whisper_model": self._current_model,
            "bilingual": self._bilingual,
            "transcript_key": self._transcript_key,
            "agent_key": self._agent_key,
            "fusion_model": self._fusion_model,
            "agent_model": self._agent_model,
        })
        cfg.save(self._config)

    def _on_fusion_model_selected(self, sender):
        if self._is_recording or sender.title == self._fusion_model:
            return
        previous = self._fusion_model
        self._fusion_model = sender.title
        self.transcriber.fusion_model = self._fusion_model
        for key in list(self._fusion_model_menu.keys()):
            item = self._fusion_model_menu[key]
            if hasattr(item, 'state'):
                item.state = key == self._fusion_model
        log.info("Fusion model changed: %s → %s", previous, self._fusion_model)
        self._save_config()

    def _on_agent_model_selected(self, sender):
        if self._is_recording or sender.title == self._agent_model:
            return
        previous = self._agent_model
        self._agent_model = sender.title
        for key in list(self._agent_model_menu.keys()):
            item = self._agent_model_menu[key]
            if hasattr(item, 'state'):
                item.state = key == self._agent_model
        log.info("Agent model changed: %s → %s", previous, self._agent_model)
        self._save_config()

    def _on_bilingual_toggled(self, sender):
        if self._is_recording:
            return
        self._bilingual = not self._bilingual
        sender.state = self._bilingual
        self.transcriber.bilingual = self._bilingual
        log.info("Bilingual mode: %s", "ON" if self._bilingual else "OFF")
        self._save_config()

    def _on_transcript_key_selected(self, sender):
        if self._is_recording or sender.title == self._transcript_key:
            return
        if sender.title == self._agent_key:
            log.warning("Key already used for agent")
            return
        previous = self._transcript_key
        self._transcript_key = sender.title
        for key_name in _HOTKEY_OPTIONS:
            self._transcript_key_menu[key_name].state = key_name == self._transcript_key
        log.info("Transcript key changed: %s → %s", previous, self._transcript_key)
        self._save_config()

    def _on_agent_key_selected(self, sender):
        if self._is_recording or sender.title == self._agent_key:
            return
        if sender.title == self._transcript_key:
            log.warning("Key already used for transcript")
            return
        previous = self._agent_key
        self._agent_key = sender.title
        for key_name in _HOTKEY_OPTIONS:
            self._agent_key_menu[key_name].state = key_name == self._agent_key
        log.info("Agent key changed: %s → %s", previous, self._agent_key)
        self._save_config()

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
                self.transcriber.fusion_model = self._fusion_model
                self.transcriber.on_status = lambda msg: self._hud.update(msg)
                self.transcriber.on_text = lambda text: self._hud.update("Transcription…", text)
                log.info("Model %s loaded.", self._current_model)
                self._save_config()
            except Exception as e:
                log.error("Failed to load model %s: %s", self._current_model, e)
                self._current_model = previous
                for size in _MODEL_SIZES:
                    self._model_menu[size].state = size == self._current_model
            finally:
                self.title = "🎤"

        threading.Thread(target=reload, daemon=True).start()

    def _on_edit_settings(self, _):
        """Open the config.json file in the default editor."""
        # Ensure config file exists
        self._save_config()
        config_file = Path.home() / ".config" / "murmurai" / "config.json"
        subprocess.Popen(["open", str(config_file)])

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
        """Create the CGEventTap for configurable transcript and agent keys."""
        log.info(
            "Listening for %s (transcript) and %s (agent)",
            self._transcript_key, self._agent_key,
        )

        def callback(proxy, event_type, event, refcon):
            keycode = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeycode
            )
            flags = Quartz.CGEventGetFlags(event)

            tk, tf = _HOTKEY_OPTIONS[self._transcript_key]
            ak, af = _HOTKEY_OPTIONS[self._agent_key]

            if keycode == tk:
                key_down = bool(flags & tf)
                if key_down and not self._is_recording:
                    self._agent_mode = False
                    self._start_recording()
                elif not key_down and self._is_recording and not self._agent_mode:
                    self._stop_recording_and_transcribe()

            elif keycode == ak:
                key_down = bool(flags & af)
                if key_down and not self._is_recording:
                    if not self._ollama_connected:
                        log.warning("Agent mode unavailable (Ollama disconnected)")
                        return event
                    self._agent_mode = True
                    self._start_recording()
                elif not key_down and self._is_recording and self._agent_mode:
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
        self._hud.show("🎙 Recording…" if not self._agent_mode else "🎙 Recording (agent)…")

        # In agent mode, grab the currently selected text via Accessibility API
        self._agent_selection = ""
        if self._agent_mode:
            try:
                self._agent_selection = grab_selection()
                if self._agent_selection:
                    log.info("Agent mode: captured selection (%d chars)", len(self._agent_selection))
                else:
                    log.info("Agent mode: no text selected")
            except Exception as e:
                log.warning("Failed to grab selection: %s", e)

        log.info("Recording started (%s)", "agent" if self._agent_mode else "transcript")

        # Record without streaming — transcribe once at the end
        self.recorder.start()
        self._start_stuck_guard()

    def _start_stuck_guard(self):
        """Safety net: if key release event is lost (e.g. macOS dialog steals focus),
        stop recording after detecting the key is no longer held."""
        key_name = self._agent_key if self._agent_mode else self._transcript_key
        _, expected_flag = _HOTKEY_OPTIONS[key_name]

        def guard():
            while self._is_recording:
                time.sleep(0.5)
                flags = Quartz.CGEventSourceFlagsState(
                    Quartz.kCGEventSourceStateHIDSystemState
                )
                key_held = bool(flags & expected_flag)
                if not key_held and self._is_recording:
                    log.info("Stuck recording detected, stopping")
                    self._stop_recording_and_transcribe()
                    break
        threading.Thread(target=guard, daemon=True).start()

    def _stop_recording_and_transcribe(self):
        self._is_recording = False
        agent_mode = self._agent_mode
        self.title = "🤖" if agent_mode else "⏳"
        log.info(
            "Recording stopped, %s...",
            "sending to agent" if agent_mode else "finalizing transcription",
        )

        # Stop recording — returns a WAV file path
        audio_path = self.recorder.stop()

        def finalize():
            try:
                if not audio_path:
                    log.info("No audio recorded")
                    return

                self._hud.update("Transcription…")

                if agent_mode and self._bilingual:
                    # Agent + bilingual: skip fusion, send both transcripts
                    # to agent in a single Ollama call
                    text_fr, text_en = self.transcriber.transcribe_bilingual_raw(
                        audio_path,
                    )
                    audio_path.unlink(missing_ok=True)

                    if not text_fr and not text_en:
                        log.info("No transcription result")
                        return

                    if self._agent_selection:
                        log.info("With selection: %s", self._agent_selection[:100])
                    detail = ""
                    if self._agent_selection:
                        detail += f"📄 {self._agent_selection[:60]}\n"
                    detail += f"🎙 {text_fr[:60]}"
                    self._hud.update("Agent…", detail)
                    self.title = "🤖"
                    response = ask_agent_bilingual(
                        text_fr, text_en,
                        selection=self._agent_selection,
                        model=self._agent_model,
                    )
                    log.info("Agent response: %s", response)

                    if self._agent_selection:
                        replace_text(self._agent_selection, response)
                    else:
                        paste_text(response)
                else:
                    # Transcript mode (with optional fusion) or agent without bilingual
                    text = self.transcriber.transcribe(audio_path).strip()
                    log.info("Transcript: %s", text)
                    audio_path.unlink(missing_ok=True)

                    if not text:
                        log.info("No transcription result")
                        return

                    if agent_mode:
                        if self._agent_selection:
                            log.info("With selection: %s", self._agent_selection[:100])
                        detail = ""
                        if self._agent_selection:
                            detail += f"📄 {self._agent_selection[:60]}\n"
                        detail += f"🎙 {text[:60]}"
                        self._hud.update("Agent…", detail)
                        self.title = "🤖"
                        response = ask_agent(
                            text, selection=self._agent_selection,
                            model=self._agent_model,
                        )
                        log.info("Agent response: %s", response)

                        if self._agent_selection:
                            replace_text(self._agent_selection, response)
                        else:
                            paste_text(response)
                    else:
                        paste_text(text)

                log.info("Text pasted to cursor")
            except Exception as e:
                log.error("Finalization failed: %s", e)
                rumps.notification("murmurai", "Error", str(e))
            finally:
                self._hud.hide()
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
