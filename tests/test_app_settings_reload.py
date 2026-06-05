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


# --- _apply_external_config: invalid file flagging --------------------------

def _patch_load(monkeypatch, config):
    monkeypatch.setattr(appmod.cfg, "load", lambda: config)


def test_apply_flags_warning_and_keeps_settings_on_invalid_config(app, monkeypatch):
    monkeypatch.setattr(appmod.cfg, "is_file_valid", lambda: False)

    def _no_load():
        raise AssertionError("load() must not run on an invalid file")

    monkeypatch.setattr(appmod.cfg, "load", _no_load)

    app._apply_external_config()

    # Edit Settings… is flagged and the running settings are left untouched.
    assert app._edit_settings_item.title == "⚠️ Edit Settings…"
    assert app._transcript_key == "Right Option"
    assert app._agent_key == "Right Command"
    assert app._current_model == "small"


def test_apply_clears_warning_on_valid_config(app, monkeypatch, base_config):
    app._edit_settings_item.title = "⚠️ Edit Settings…"
    monkeypatch.setattr(appmod.cfg, "is_file_valid", lambda: True)
    _patch_load(monkeypatch, base_config())

    app._apply_external_config()

    assert app._edit_settings_item.title == "Edit Settings…"


# --- _apply_external_config: hotkeys ----------------------------------------


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


# --- _apply_external_config: transcript icon --------------------------------

def test_apply_updates_transcript_icon_and_checkmarks(app, monkeypatch, base_config):
    _patch_load(monkeypatch, base_config(transcript_icon="📼"))

    app._apply_external_config()

    assert app._transcript_icon == "📼"
    assert app._transcript_icon_menu["📼 Magnétophone"].state is True
    assert app._transcript_icon_menu["🎙️ Micro studio"].state is False


def test_apply_disables_transcript_icon_with_none(app, monkeypatch, base_config):
    _patch_load(monkeypatch, base_config(transcript_icon=""))

    app._apply_external_config()

    assert app._transcript_icon == ""
    assert app._transcript_icon_menu["Aucun"].state is True
    assert app._transcript_icon_menu["🎙️ Micro studio"].state is False


# --- _on_transcript_icon_selected -------------------------------------------

def test_select_transcript_icon_updates_state_and_persists(app, monkeypatch, tmp_config):
    import json

    sender = appmod.rumps.MenuItem("📼 Magnétophone")

    app._on_transcript_icon_selected(sender)

    assert app._transcript_icon == "📼"
    assert app._transcript_icon_menu["📼 Magnétophone"].state is True
    assert app._transcript_icon_menu["🎙️ Micro studio"].state is False
    saved = json.loads(tmp_config.read_text(encoding="utf-8"))
    assert saved["transcript_icon"] == "📼"


def test_select_transcript_icon_none_clears_prefix(app, tmp_config):
    import json

    app._on_transcript_icon_selected(appmod.rumps.MenuItem("Aucun"))

    assert app._transcript_icon == ""
    assert app._transcript_icon_menu["Aucun"].state is True
    saved = json.loads(tmp_config.read_text(encoding="utf-8"))
    assert saved["transcript_icon"] == ""


def test_select_transcript_icon_blocked_while_recording(app):
    app._is_recording = True
    app._on_transcript_icon_selected(appmod.rumps.MenuItem("📼 Magnétophone"))
    assert app._transcript_icon == "🎙️"


# --- _format_transcript: icon prefix ----------------------------------------

def test_format_transcript_prepends_icon_and_colon(app):
    app._transcript_icon = "🎙️"
    assert app._format_transcript("Hello how are you?") == "🎙️: Hello how are you?"


def test_format_transcript_without_icon_returns_text_unchanged(app):
    app._transcript_icon = ""
    assert app._format_transcript("Hello how are you?") == "Hello how are you?"


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


# --- _on_edit_settings: never clobber an invalid file -----------------------

def test_edit_settings_does_not_overwrite_invalid_file(app, monkeypatch):
    opened = []
    monkeypatch.setattr(appmod.subprocess, "Popen", lambda args: opened.append(args))
    monkeypatch.setattr(appmod.cfg, "is_file_valid", lambda: False)
    monkeypatch.setattr(app, "_save_config", lambda: (_ for _ in ()).throw(
        AssertionError("must not rewrite an invalid file")))

    app._on_edit_settings(None)

    # File is opened for repair but never rewritten.
    assert opened and opened[0][0] == "open"


def test_edit_settings_materialises_file_when_valid(app, monkeypatch):
    opened = []
    saved = []
    monkeypatch.setattr(appmod.subprocess, "Popen", lambda args: opened.append(args))
    monkeypatch.setattr(appmod.cfg, "is_file_valid", lambda: True)
    monkeypatch.setattr(app, "_save_config", lambda: saved.append(True))

    app._on_edit_settings(None)

    assert saved == [True]
    assert opened and opened[0][0] == "open"


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
    app._transcript_icon = "📼"

    app._save_config()

    saved = json.loads(tmp_config.read_text(encoding="utf-8"))
    assert saved["whisper_model"] == "base"
    assert saved["transcript_key"] == "Left Option"
    assert saved["agent_key"] == "Right Shift"
    assert saved["agent_model"] == "llama3:8b"
    assert saved["transcript_icon"] == "📼"
