# murmurai

Push-to-talk voice transcription and AI assistant for macOS. Hold a key, speak, release — your speech is transcribed locally and pasted at the cursor. With a second key, the transcript is sent to a local AI agent that can answer questions or act on selected text.

Uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper) for offline transcription and [Ollama](https://ollama.com) for AI agent features. No cloud API needed.

## Features

- **Push-to-talk transcription** — hold a key, speak, release to paste
- **Technical jargon** — the French transcript is post-processed against a built-in dictionary of ~100 technical terms and their frenchified variants, so "commiter" comes back as "commit"; instant, no LLM needed, extensible via config
- **AI agent mode** — hold a second key to send your voice instruction (+ any selected text) to Ollama; the AI response replaces the selected text
- **HUD overlay** — a live waveform while you speak, then the current step, transcription text, and agent context
- **Microphone selection** — pick an input device or follow the macOS default; hot-plugged devices appear automatically
- **Audio feedback** — short system sounds at the start and end of an operation, so push-to-talk works without looking at the screen
- **Mute while recording** — optionally silence the speakers while recording so playback is not picked up by the mic
- **Launch at login** — start murmurai with your session
- **Two permissions only** — Accessibility and Microphone; text is pasted with `CGEvent`, so there is no Automation prompt
- **Fully local** — no cloud, no API key; transcription runs entirely on your machine (Ollama only needed for agent mode)
- **Configurable** — hotkeys, Whisper model, agent model, microphone, and jargon list all editable from the menu bar or config file

## Installation

### Homebrew (recommended)

```bash
brew install --cask vbarrai/tap/murmurai
```

### DMG

Download the latest `.dmg` from [Releases](https://github.com/vbarrai/murmurai/releases), open it, and drag **murmurai** into your Applications folder.

The Whisper model (~500 Mo for `small`) is downloaded automatically at first launch.

### From source

Requires [uv](https://docs.astral.sh/uv/) (`brew install uv`).

```bash
git clone https://github.com/vbarrai/murmurai.git
cd murmurai
make dev
```

`make dev` creates `.venv` with the interpreter pinned in `.python-version`
(Python 3.12, the same version the release builds with) and installs murmurai in
editable mode along with the test and build extras. uv downloads the interpreter
itself if it is missing — no system Python setup required.

### Ollama (optional, for agent mode only)

Ollama is only needed if you want to use agent mode. Transcription works without it.

Install [Ollama](https://ollama.com), then pull a model:

```bash
ollama pull gpt-oss:20b   # or any model you prefer
```

Make sure Ollama is running (`ollama serve`) before using agent mode.

## macOS permissions

murmurai needs two permissions in **System Settings > Privacy & Security**:

- **Accessibility** — to listen for global hotkeys *and* to paste at the cursor
- **Microphone** — to record audio

On first launch, macOS will prompt you for each permission automatically. Grant access and the app will activate without needing a restart.

> Earlier versions also required **Automation (System Events)**, because pasting
> went through `osascript`. Pasting now posts a synthetic Cmd+V with `CGEvent`,
> which is already covered by the Accessibility grant murmurai needs for its
> hotkeys — so that third prompt is gone. If it is still listed in System
> Settings you can revoke it.

## Usage

Launch murmurai from Applications, or from source:

```bash
uv run --no-sync murmurai
```

### Two modes

| Mode | Default key | What it does |
|---|---|---|
| **Transcript** | Right Option (hold) | Records → transcription → pasted at cursor |
| **Agent** | Right Command (hold) | Records → transcription + selected text → AI agent → response pasted |

Press **Escape** at any point to cancel the current recording, transcription, or
agent request.

### Transcript mode

Hold the transcript key, speak, release. Your speech is transcribed locally by Whisper and pasted at the cursor position.

**Pipeline:**

```
Audio → Whisper (FR) → Jargon fix → Text pasted
```

A single French Whisper pass runs, then the transcript is post-processed against
the jargon dictionary. That step is instant — a regex dictionary lookup, no
network call and no LLM.

The HUD shows a live waveform while you speak, then the current step and the
text being transcribed in real time.

### Jargon fix

| | Transcript |
|---|---|
| Whisper FR | "Est-ce que tu peux **commiter** et **pousher** les modifications ?" |
| After jargon fix | "Est-ce que tu peux **commit** et **push** les modifications ?" |

### Agent mode

Hold the agent key, speak, release. Your voice instruction is transcribed and sent to a local Ollama model along with any text you had selected on screen.

**Pipeline:**

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
- **Transcript icon** — choose an icon prepended to pasted transcripts (so readers, e.g. on Slack, recognize them as voice transcriptions), or **Aucun** for no icon
- **Model** — select the Whisper model size
- **Microphone** — select the input device, or follow the system default
- **Sound effects** — toggle the start/stop/done feedback sounds
- **Mute while recording** — toggle muting the speakers during recording
- **Launch at login** — start murmurai with your session (installed `.app` only)
- **Ollama status** — shows connection status (click to refresh)
- **Agent model** — select the Ollama model for agent responses
- **↻ Refresh Ollama** — re-check connection and refresh model list
- **Edit Settings…** — open `config.json` in your default editor (changes are applied automatically when you save the file — no restart needed)
- **Open Logs…** — open the log file

## Development

During development, run directly from source to test your latest changes:

```bash
uv run --no-sync murmurai
```

This always runs the current code — no rebuild needed. `--no-sync` tells uv to
use the existing `.venv` as-is; the project is deliberately lock-free, so the
environment is managed by `make dev` rather than resolved on every run.

Launch at login is unavailable when running from source: there is no `.app`
bundle for launchd to relaunch, so the menu item is greyed out.

### Tests

The test suite lives in `tests/` and runs with `pytest`:

```bash
make test
```

The tests are platform-independent: the macOS-only frameworks (`rumps`,
`Quartz`, `AppKit`, …) and heavy native deps (`faster-whisper`, `sounddevice`)
are stubbed in `tests/conftest.py` when they aren't installed, so the suite runs
on Linux CI as well as on macOS. Coverage focuses on the pure logic:

- `test_config.py` — config load/save, defaults merging, corrupt-file fallback
- `test_jargon.py` — franglais variant replacement and built-in/user merging
- `test_app_settings_reload.py` — the live settings-reload path (mtime watch,
  hotkey/agent-model/Whisper-model/microphone/toggle updates, validation)
- `test_audio_devices.py` — input-device enumeration and name→index resolution
- `test_system_audio.py` — mute/restore, including "leave it muted if the user
  had muted it"
- `test_login_item.py` — LaunchAgent install/removal
- `test_hud_layout.py` — HUD layout arithmetic

## Build standalone .app

To package murmurai as a standalone macOS app (no Python required):

```bash
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

Edits to the file are picked up live: murmurai watches `config.json` and re-applies your changes within a couple of seconds of saving — there is no need to restart the app. Hotkeys, the transcript icon, the microphone, the agent model, and the toggles take effect immediately; changing `whisper_model` reloads the model in the background. Invalid values (an unknown hotkey, the same key bound to both actions, or an unknown Whisper model) are ignored and the previous setting is kept — check the logs if a change doesn't seem to apply.

```json
{
  "whisper_model": "small",
  "transcript_key": "Right Option",
  "agent_key": "Right Command",
  "agent_model": "gpt-oss:20b",
  "transcript_icon": "🎙️",
  "microphone": "",
  "sounds": true,
  "mute_while_recording": false,
  "launch_at_login": false,
  "jargon": {
    "kubectl": ["kubecétéèle"],
    "terraform": ["terraformer"]
  }
}
```

| Key | Default | Meaning |
|---|---|---|
| `microphone` | `""` | Input device name; `""` follows the macOS system default. A device that is configured but unplugged falls back to the default until it is reconnected. |
| `sounds` | `true` | Play short system sounds at start/stop/done/cancel. |
| `mute_while_recording` | `false` | Mute the speakers for the duration of the recording. Speakers the user had already muted are left muted. |
| `launch_at_login` | `false` | Install a per-user LaunchAgent. Ignored when running from source. |

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

Ollama is only needed for **agent mode**. The jargon fix is done locally without any LLM. The menu bar shows the Ollama connection status; when disconnected, agent features are disabled.

- **Agent model** — selectable from the menu bar (default: `gpt-oss:20b`)

### Technical jargon

#### The problem

When you speak French with English technical terms, Whisper tends to "frenchify" them:

| You say | Whisper transcribes (FR) |
|---|---|
| "commit" | "commiter" |
| "push" | "pousher" |
| "debug" | "débugger" |
| "deploy" | "deployer" |

#### How it works

After the French Whisper pass, murmurai walks the jargon dictionary and replaces
each frenchified variant with the English term it maps to. The matching is
case-insensitive and purely local — a regex lookup, no LLM call.

Only *franglais* variants are listed. Real French words (`pousser`, `fusionner`,
…) are deliberately absent: when the English term is actually spoken in English,
Whisper already transcribes it correctly, and rewriting genuine French words
would corrupt ordinary sentences.

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

If your config still has the old list format (`"jargon": ["commit", "push", ...]`), it will still work — each term is added with an empty variant list. But the new dict format is recommended: without variants, a term is never actually substituted.
