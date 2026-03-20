import logging
import threading

import rumps
from pynput import keyboard

from murmurai.paster import paste_text
from murmurai.recorder import AudioRecorder
from murmurai.transcriber import LocalTranscriber

log = logging.getLogger("murmurai")


class MurmurAIApp(rumps.App):
    def __init__(self):
        super().__init__("murmurai", icon=None, title="🎤")
        log.info("Loading Whisper model...")
        self.recorder = AudioRecorder()
        self.transcriber = LocalTranscriber()
        log.info("Model loaded, ready.")
        self._is_recording = False
        self._hotkey_listener = None

        # Menu items
        self.menu = [
            rumps.MenuItem("murmurai — Push-to-Talk", callback=None),
            None,  # separator
            rumps.MenuItem("Hotkey: Right Option (hold)", callback=None),
            None,
        ]

    def start_hotkey_listener(self):
        """Start listening for the Right Option key."""
        log.info("Listening for Right Option key (hold to record)")
        self._right_option_pressed = False

        def on_press(key):
            # Right Option key = Key.alt_r
            if key == keyboard.Key.alt_r and not self._is_recording:
                self._start_recording()

        def on_release(key):
            if key == keyboard.Key.alt_r and self._is_recording:
                self._stop_recording_and_transcribe()

        self._hotkey_listener = keyboard.Listener(
            on_press=on_press, on_release=on_release
        )
        self._hotkey_listener.start()

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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    app = MurmurAIApp()
    app.start_hotkey_listener()
    app.run()


if __name__ == "__main__":
    main()
