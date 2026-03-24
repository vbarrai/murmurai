# murmurai

Push-to-talk voice transcription and AI assistant for macOS. Hold a key, speak, release — your speech is transcribed locally and pasted at the cursor. With a second key, the transcript is sent to a local AI agent that can answer questions or act on selected text.

Uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper) for offline transcription and [Ollama](https://ollama.com) for bilingual fusion and AI agent features. No cloud API needed.

## Features

- **Push-to-talk transcription** — hold a key, speak, release to paste
- **Bilingual FR/EN** — transcribes in both French and English in parallel, then fuses the results via Ollama to keep French sentence structure with English technical jargon intact
- **Technical jargon detection** — a configurable list of technical terms (commit, push, deploy, API, etc.) ensures they stay in English instead of being "frenchified" by Whisper
- **AI agent mode** — hold a second key to send your voice instruction (+ any selected text) to Ollama; the AI response replaces the selected text
- **Fully local** — no cloud, no API key, everything runs on your machine
- **Configurable hotkeys** — choose your preferred keys from the menu bar

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

The Whisper model (~500 Mo for `small`) is downloaded automatically at first launch.

### Ollama (required for bilingual mode and agent)

Install [Ollama](https://ollama.com), then pull a model:

```bash
ollama pull gpt-oss:20b   # for agent mode (or any model you prefer)
```

Make sure Ollama is running (`ollama serve`) before using murmurai.

## macOS permissions

murmurai needs three permissions in **System Settings > Privacy & Security**:

- **Accessibility** — to listen for global hotkeys
- **Microphone** — to record audio
- **Automation (System Events)** — to simulate Cmd+C/Cmd+V

On first launch, macOS will prompt you for each permission automatically. Grant access and the app will activate without needing a restart.

## Usage

```bash
source .venv/bin/activate
murmurai
```

### Two modes

| Mode | Default key | What it does |
|---|---|---|
| **Transcript** | Right Option (hold) | Records → bilingual transcript → pasted at cursor |
| **Agent** | Right Command (hold) | Records → bilingual transcript + selected text → sent to Ollama → AI response pasted |

### Agent mode examples

Select some text, then hold Right Command and speak:

- "Améliore ce prompt"
- "Traduis cela en italien"
- "Corrige les erreurs"
- "Résume ce texte en 3 bullet points"
- "Explain this code"

The AI response replaces the pasted text. If no text is selected, the agent just responds to your voice message.

## Menu bar options

Click the menu bar icon to access:

- **Transcript key** — choose which key triggers transcription
- **Agent key** — choose which key triggers agent mode
- **Model** — select the Whisper model size
- **Bilingual FR/EN** — toggle bilingual transcription on/off
- **Ollama status** — shows connection status (click to refresh)
- **Agent model** — select the Ollama model for agent responses
- **↻ Refresh Ollama** — re-check Ollama connection and refresh model list

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

All settings are stored in `~/.config/murmurai/config.json` and persist across launches. Settings can be changed from the menu bar or by editing the JSON file directly.

```json
{
  "whisper_model": "small",
  "bilingual": true,
  "transcript_key": "Right Option",
  "agent_key": "Right Command",
  "agent_model": "gpt-oss:20b",
  "jargon": {
    "kubectl": ["kubecétéèle"],
    "terraform": ["terraformer"]
  }
}
```

### Whisper model

Selectable from the menu bar. Available sizes:

| Model | Size | Speed | Quality |
|---|---|---|---|
| `tiny` | ~75 Mo | Fastest | Basic |
| `base` | ~150 Mo | Fast | Decent |
| `small` | ~500 Mo | Moderate | Good |
| `medium` | ~1.5 Go | Slower | Very good |
| `large-v3` | ~3 Go | Slowest | Best |

### Ollama

Ollama is only needed for **agent mode**. Bilingual fusion is now done locally without any LLM. The menu bar shows the Ollama connection status; when disconnected, agent features are disabled.

- **Agent model** — selectable from the menu bar (default: `gpt-oss:20b`)

### Technical jargon

murmurai ships with a built-in dictionary of ~100 technical terms and their French-ified variants (e.g. "commit" → ["commettre", "commiter"]). When bilingual mode is on, the fusion replaces these French variants with the English original — instantly, no LLM needed.

To add your own terms, edit the `"jargon"` dict in `~/.config/murmurai/config.json`:

```json
{
  "jargon": {
    "kubectl": ["kubecétéèle"],
    "terraform": ["terraformer"]
  }
}
```

User jargon is **merged on top** of the built-in dictionary. App updates add new built-in terms without overwriting your custom entries.
