# murmurai

Push-to-talk voice transcription for macOS. Hold a key, speak, release — your speech is transcribed locally and pasted at the cursor.

Uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper) for offline transcription (no API key needed).

## Installation

```bash
# Clone the repo
git clone https://github.com/vbarrai/murmurai.git
cd murmurai

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install
pip install -e .
```

The Whisper model (~1.5 Go for `medium`) is downloaded automatically at first launch.

## macOS permissions

murmurai needs two permissions in **System Settings > Privacy & Security**:

- **Accessibility** — to simulate Cmd+V for pasting
- **Microphone** — to record audio

Add your terminal app (Terminal.app, iTerm, etc.) to both lists.

You may also need to create the Info.plist for notifications:

```bash
/usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string "rumps"' .venv/bin/Info.plist
```

## Usage

```bash
source .venv/bin/activate
murmurai
```

Hold **Right Option** to record, release to transcribe and paste.

## Configuration

You can change the Whisper model size in `murmurai/transcriber.py`:

| Model | Size | Speed | Quality |
|---|---|---|---|
| `tiny` | ~75 Mo | Fastest | Basic |
| `base` | ~150 Mo | Fast | Decent |
| `small` | ~500 Mo | Moderate | Good |
| `medium` | ~1.5 Go | Slower | Very good |
| `large-v3` | ~3 Go | Slowest | Best |
