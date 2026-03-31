# murmurai

Push-to-talk voice transcription and AI assistant for macOS. Hold a key, speak, release — your speech is transcribed locally and pasted at the cursor. With a second key, the transcript is sent to a local AI agent that can answer questions or act on selected text.

Uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper) for offline transcription and [Ollama](https://ollama.com) for AI agent features. No cloud API needed.

## Features

- **Push-to-talk transcription** — hold a key, speak, release to paste
- **Bilingual FR/EN** — transcribes in both French and English in parallel, then fuses the results locally to keep French sentence structure with English technical jargon intact
- **Technical jargon** — built-in dictionary of ~100 technical terms with their French variants, extensible via config; fusion is instant (no LLM needed)
- **AI agent mode** — hold a second key to send your voice instruction (+ any selected text) to Ollama; the AI response replaces the selected text
- **HUD overlay** — real-time status display showing current step, transcription text, and agent context
- **Fully local** — no cloud, no API key; transcription and fusion run entirely on your machine (Ollama only needed for agent mode)
- **Configurable** — hotkeys, Whisper model, agent model, and jargon list all editable from the menu bar or config file

## Installation

### Homebrew (recommended)

```bash
brew install --cask vbarrai/tap/murmurai
```

### DMG

Download the latest `.dmg` from [Releases](https://github.com/vbarrai/murmurai/releases), open it, and drag **murmurai** into your Applications folder.

The Whisper model (~500 Mo for `small`) is downloaded automatically at first launch.

### From source

```bash
git clone https://github.com/vbarrai/murmurai.git
cd murmurai
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Ollama (optional, for agent mode only)

Ollama is only needed if you want to use agent mode. Bilingual transcription works without it.

Install [Ollama](https://ollama.com), then pull a model:

```bash
ollama pull gpt-oss:20b   # or any model you prefer
```

Make sure Ollama is running (`ollama serve`) before using agent mode.

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
| **Transcript** | Right Option (hold) | Records → transcription → pasted at cursor |
| **Agent** | Right Command (hold) | Records → transcription + selected text → AI agent → response pasted |

### Transcript mode

Hold the transcript key, speak, release. Your speech is transcribed locally by Whisper and pasted at the cursor position.

**Pipeline:**

```
Audio → Whisper (FR) → Text pasted
```

With **bilingual mode** enabled, the pipeline becomes:

```
Audio → Whisper (FR) + Whisper (EN) in parallel → Local fusion → Text pasted
```

The two Whisper passes run in parallel on separate model instances. The local fusion then replaces frenchified technical terms using the jargon dictionary — this step is instant (no network call).

A HUD overlay shows the current step and the text being transcribed in real-time.

### Fusion

The fusion step combines the French and English transcripts into a single result:

1. **Start from the French transcript** — it has the correct sentence structure
2. **Cross-reference with the English transcript** — identify which words were actually spoken in English
3. **Replace frenchified terms** — using the jargon dictionary (built-in + user entries)

Example:

| | Transcript |
|---|---|
| Whisper FR | "Est-ce que tu peux **commettre** et **pousser** les modifications ?" |
| Whisper EN | "Can you **commit** and **push** the modifications?" |
| After fusion | "Est-ce que tu peux **commit** et **push** les modifications ?" |

The fusion is purely local (regex-based dictionary lookup). It does not require Ollama or any network access. When bilingual mode is off, Whisper runs a single French pass and no fusion occurs.

### Agent mode

Hold the agent key, speak, release. Your voice instruction is transcribed and sent to a local Ollama model along with any text you had selected on screen.

**Pipeline (with bilingual):**

```
Audio → Whisper (FR) + Whisper (EN) in parallel → Both transcripts + selected text → Ollama → Response pasted
```

In agent mode, the fusion step is **skipped entirely**. Both raw transcripts (FR and EN) are sent directly to the Ollama model in a single call. The model is smart enough to understand the user's intent from both versions.

**Pipeline (without bilingual):**

```
Audio → Whisper (FR) → Transcript + selected text → Ollama → Response pasted
```

**With selected text:** the agent applies your voice instruction to the selected text. The response **replaces** the selection.

**Without selected text:** the agent responds freely to your voice message and pastes the response at the cursor.

#### Examples

Select some text, then hold Right Command and speak:

- "Simplifie cette phrase"
- "Traduis en anglais"
- "Corrige les erreurs"
- "Résume en 3 bullet points"
- "Explain this code"
- "Réécris de manière plus concise"

Without selection:

- "Écris-moi un email de relance"
- "Donne-moi la commande git pour..."

## Menu bar options

Click the menu bar icon to access:

- **Transcript key** — choose which key triggers transcription
- **Agent key** — choose which key triggers agent mode
- **Model** — select the Whisper model size
- **Bilingual FR/EN** — toggle bilingual transcription on/off
- **Ollama status** — shows connection status (click to refresh)
- **Agent model** — select the Ollama model for agent responses
- **↻ Refresh Ollama** — re-check connection and refresh model list
- **Edit Settings…** — open `config.json` in your default editor
- **Open Logs…** — open the log file

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

#### The problem

When you speak French with English technical terms, Whisper tends to "frenchify" them:

| You say | Whisper transcribes (FR) |
|---|---|
| "commit" | "commettre" |
| "push" | "pousser" |
| "merge" | "fusionner" |
| "debug" | "déboguer" |
| "deploy" | "déployer" |

#### How it works

With bilingual mode on, murmurai transcribes the same audio in both French and English in parallel. It then **fuses** the two transcripts locally:

1. Start from the French transcript (correct sentence structure)
2. Look at the English transcript to identify which technical terms were spoken
3. Replace the frenchified words with their English originals

This fusion is **instant** — it's a simple dictionary lookup, no LLM call.

#### Built-in vs user jargon

murmurai uses two layers of jargon:

- **Built-in** (`murmurai/jargon.py`) — ~100 terms covering Git, DevOps, code, testing, tools, etc. Updated with the app on each new version.
- **User** (`~/.config/murmurai/config.json`) — your custom additions, merged on top of the built-in dictionary.

The merge works as follows:
- New terms in user jargon are added to the dictionary
- If a term already exists in built-in, user variants are appended (no duplicates)
- Built-in terms are never removed by user config

This means app updates can add new terms without overwriting your custom entries.

#### Adding custom jargon

Edit the `"jargon"` dict in `~/.config/murmurai/config.json` (accessible from the menu: **Edit Settings…**):

```json
{
  "jargon": {
    "kubectl": ["kubecétéèle", "kubeucétéèle"],
    "terraform": ["terraformer"],
    "Datadog": ["datadogue"]
  }
}
```

Each entry maps an **English term** (the correct form to keep) to a list of **French variants** that Whisper might produce. The matching is case-insensitive.

#### Legacy format

If your config still has the old list format (`"jargon": ["commit", "push", ...]`), it will still work — each term is added with an empty variant list. But the new dict format is recommended for better fusion accuracy.
