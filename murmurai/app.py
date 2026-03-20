import os
import threading

import rumps
from pynput import keyboard

from murmurai.paster import paste_text
from murmurai.recorder import AudioRecorder
from murmurai.transcriber import OpenAITranscriber


class MurmurAIApp(rumps.App):
    def __init__(self):
        super().__init__("murmurai", icon=None, title="🎤")
        self.recorder = AudioRecorder()
        self.transcriber = OpenAITranscriber()
        self._is_recording = False
        self._hotkey_listener = None

        # Menu items
        self.menu = [
            rumps.MenuItem("murmurai — Push-to-Talk", callback=None),
            None,  # separator
            rumps.MenuItem("Hotkey: Right Option (hold)", callback=None),
            None,
        ]

        # Check API key
        if not os.environ.get("OPENAI_API_KEY"):
            rumps.notification(
                "murmurai",
                "API Key Missing",
                "Set OPENAI_API_KEY environment variable",
            )

    def start_hotkey_listener(self):
        """Start listening for the Right Option key."""
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
        self.recorder.start()

    def _stop_recording_and_transcribe(self):
        self._is_recording = False
        self.title = "⏳"

        audio_path = self.recorder.stop()
        if audio_path is None:
            self.title = "🎤"
            return

        # Transcribe in background thread
        def do_transcribe():
            try:
                text = self.transcriber.transcribe(audio_path)
                paste_text(text)
            except Exception as e:
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
    app = MurmurAIApp()
    app.start_hotkey_listener()
    app.run()


if __name__ == "__main__":
    main()
