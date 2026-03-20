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

- **Accessibility** — to listen for hotkeys and simulate Cmd+V for pasting
- **Microphone** — to record audio

When running from the terminal, add your terminal app (Terminal.app, iTerm, etc.) to both lists.
When running the standalone `.app`, add `murmurai.app` instead.

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

## Development

During development, run directly from source to test your latest changes:

```bash
source .venv/bin/activate
murmurai
```

This always runs the current code — no rebuild needed.

## Build standalone .app

To package murmurai as a standalone macOS app (no Python required):

```bash
pip install -e ".[build]"
make install
```

This builds the app and installs it to `/Applications/murmurai.app`.

To build without installing:

```bash
make build
```

### Logs

Logs are written to `~/Library/Logs/murmurai/murmurai.log`.

## Configuration

You can change the Whisper model size in `murmurai/transcriber.py`:

| Model | Size | Speed | Quality |
|---|---|---|---|
| `tiny` | ~75 Mo | Fastest | Basic |
| `base` | ~150 Mo | Fast | Decent |
| `small` | ~500 Mo | Moderate | Good |
| `medium` | ~1.5 Go | Slower | Very good |
| `large-v3` | ~3 Go | Slowest | Best |
