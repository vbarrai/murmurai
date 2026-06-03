"""Tests for the live settings-reload path in murmurai.app.

These cover the bug where editing config.json via "Edit Settings…" had no
effect: the app now watches the file's mtime and re-applies external edits.
"""

import murmurai.app as appmod


# --- _watch_config: mtime-driven trigger -----------------------------------

def test_watch_config_applies_when_mtime_changes(app, monkeypatch):
    calls = []
    app._config_mtime = 100.0
    monkeypatch.setattr(app, "_config_file_mtime", lambda: 200.0)
    monkeypatch.setattr(app, "_apply_external_config", lambda: calls.append(True))

    app._watch_config(None)

    assert calls == [True]
    assert app._config_mtime == 200.0  # tracked mtime advances


def test_watch_config_noop_when_mtime_unchanged(app, monkeypatch):
    calls = []
    app._config_mtime = 100.0
    monkeypatch.setattr(app, "_config_file_mtime", lambda: 100.0)
    monkeypatch.setattr(app, "_apply_external_config", lambda: calls.append(True))

    app._watch_config(None)

    assert calls == []


def test_watch_config_skips_while_recording(app, monkeypatch):
    calls = []
    app._is_recording = True
    app._config_mtime = 100.0
    monkeypatch.setattr(app, "_config_file_mtime", lambda: 200.0)
    monkeypatch.setattr(app, "_apply_external_config", lambda: calls.append(True))

    app._watch_config(None)

    # No reload mid-recording, and mtime is left so the next tick retries.
    assert calls == []
    assert app._config_mtime == 100.0


# --- _apply_external_config: hotkeys ----------------------------------------

def _patch_load(monkeypatch, config):
    monkeypatch.setattr(appmod.cfg, "load", lambda: config)


def test_apply_updates_hotkeys_and_checkmarks(app, monkeypatch, base_config):
    _patch_load(monkeypatch, base_config(
        transcript_key="Left Command", agent_key="Right Control",
    ))

    app._apply_external_config()

    assert app._transcript_key == "Left Command"
    assert app._agent_key == "Right Control"
    assert app._transcript_key_menu["Left Command"].state is True
    assert app._transcript_key_menu["Right Option"].state is False
    assert app._agent_key_menu["Right Control"].state is True
    assert app._agent_key_menu["Right Command"].state is False


def test_apply_rejects_duplicate_hotkeys(app, monkeypatch, base_config):
    _patch_load(monkeypatch, base_config(transcript_key="Fn", agent_key="Fn"))

    app._apply_external_config()

    # Same key for both → invalid, current keys preserved.
    assert app._transcript_key == "Right Option"
    assert app._agent_key == "Right Command"


def test_apply_rejects_unknown_hotkey(app, monkeypatch, base_config):
    _patch_load(monkeypatch, base_config(transcript_key="Banana"))

    app._apply_external_config()

    assert app._transcript_key == "Right Option"


# --- _apply_external_config: agent model ------------------------------------

def test_apply_updates_agent_model_and_checkmarks(app, monkeypatch, base_config):
    rumps = appmod.rumps
    menu = rumps.MenuItem("Agent model")
    menu.add(rumps.MenuItem("gemma3:latest  (5.0 GB)"))
    menu.add(rumps.MenuItem("llama3:8b  (4.0 GB)"))
    app._agent_model_menu = menu
    app._agent_model_titles = {
        "gemma3:latest  (5.0 GB)": "gemma3:latest",
        "llama3:8b  (4.0 GB)": "llama3:8b",
    }

    _patch_load(monkeypatch, base_config(agent_model="llama3:8b"))

    app._apply_external_config()

    assert app._agent_model == "llama3:8b"
    assert app._agent_model_menu["llama3:8b  (4.0 GB)"].state is True
    assert app._agent_model_menu["gemma3:latest  (5.0 GB)"].state is False


# --- _apply_external_config: whisper model (background reload) ---------------

class _SyncThread:
    """Drop-in for threading.Thread that runs the target synchronously."""

    def __init__(self, target=None, daemon=None, **kwargs):
        self._target = target

    def start(self):
        if self._target:
            self._target()


def test_apply_switches_whisper_model(app, monkeypatch, base_config, tmp_config):
    monkeypatch.setattr(appmod.threading, "Thread", _SyncThread)
    _patch_load(monkeypatch, base_config(whisper_model="medium"))

    app._apply_external_config()

    assert app._current_model == "medium"
    assert app._model_menu["medium"].state is True
    assert app._model_menu["small"].state is False
    # New transcriber instance loaded with the new size.
    assert app.transcriber.model_size == "medium"
    # Switch persists the config (written to the tmp path).
    assert tmp_config.exists()


def test_apply_ignores_unknown_whisper_model(app, monkeypatch, base_config):
    monkeypatch.setattr(appmod.threading, "Thread", _SyncThread)
    _patch_load(monkeypatch, base_config(whisper_model="ginormous"))

    app._apply_external_config()

    assert app._current_model == "small"
    assert app.transcriber.model_size == "small"


# --- _switch_model guards ---------------------------------------------------

def test_switch_model_noop_for_same_model(app, monkeypatch):
    monkeypatch.setattr(appmod.threading, "Thread", _SyncThread)
    before = app.transcriber
    app._switch_model("small")
    assert app.transcriber is before  # no reload


def test_switch_model_blocked_while_recording(app, monkeypatch):
    monkeypatch.setattr(appmod.threading, "Thread", _SyncThread)
    app._is_recording = True
    app._switch_model("medium")
    assert app._current_model == "small"


def test_switch_model_reverts_on_load_failure(app, monkeypatch, tmp_config):
    monkeypatch.setattr(appmod.threading, "Thread", _SyncThread)

    def boom(*args, **kwargs):
        raise RuntimeError("model download failed")

    monkeypatch.setattr(appmod, "LocalTranscriber", boom)

    app._switch_model("large-v3")

    # Failure rolls back to the previous model and restores the checkmark.
    assert app._current_model == "small"
    assert app._model_menu["small"].state is True
    assert app._model_menu["large-v3"].state is False


# --- _save_config: mtime tracking -------------------------------------------

def test_save_config_updates_tracked_mtime(app, tmp_config):
    app._config_mtime = 0.0

    app._save_config()

    assert tmp_config.exists()
    # Tracked mtime now matches the file, so the watcher won't treat our own
    # write as an external edit.
    assert app._config_mtime == tmp_config.stat().st_mtime
    assert app._config_mtime != 0.0


def test_save_config_persists_current_settings(app, tmp_config):
    import json

    app._current_model = "base"
    app._transcript_key = "Left Option"
    app._agent_key = "Right Shift"
    app._agent_model = "llama3:8b"

    app._save_config()

    saved = json.loads(tmp_config.read_text(encoding="utf-8"))
    assert saved["whisper_model"] == "base"
    assert saved["transcript_key"] == "Left Option"
    assert saved["agent_key"] == "Right Shift"
    assert saved["agent_model"] == "llama3:8b"
