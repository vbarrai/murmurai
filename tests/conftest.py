"""Shared test fixtures and platform stubs.

murmurai targets macOS and pulls in mac-only frameworks (rumps, Quartz,
AppKit, …) plus heavy native deps (faster-whisper, sounddevice). None of
those can be imported on a Linux CI runner, so this module installs light
stand-ins into ``sys.modules`` *only when the real module is unavailable*.
On macOS the real modules import normally and the stubs are never used.
"""

from __future__ import annotations

import sys
import types

import pytest


def _stub_if_missing(name: str, factory):
    """Install ``factory()`` as ``sys.modules[name]`` if the real import fails."""
    if name in sys.modules:
        return
    try:
        __import__(name)
    except Exception:  # ImportError on Linux, plus any framework load error
        sys.modules[name] = factory()


def _fake_rumps() -> types.ModuleType:
    mod = types.ModuleType("rumps")

    class App:
        def __init__(self, *args, **kwargs):
            pass

    class MenuItem:
        def __init__(self, title=None, callback=None, *args, **kwargs):
            self.title = title
            self.callback = callback
            self.state = False
            self._children = {}

        def add(self, item):
            self._children[item.title] = item

        def clear(self):
            self._children.clear()

        def keys(self):
            return list(self._children.keys())

        def __getitem__(self, key):
            return self._children[key]

        def __setitem__(self, key, value):
            self._children[key] = value

    def timer(*_args, **_kwargs):
        # Decorator factory: leave the wrapped method untouched so tests can
        # call it directly.
        def decorator(func):
            return func

        return decorator

    def _noop(*_args, **_kwargs):
        return None

    mod.App = App
    mod.MenuItem = MenuItem
    mod.timer = timer
    mod.alert = _noop
    mod.quit_application = _noop
    mod.notification = _noop
    return mod


def _fake_quartz() -> types.ModuleType:
    from unittest.mock import MagicMock

    return MagicMock(name="Quartz")


def _fake_hud() -> types.ModuleType:
    mod = types.ModuleType("murmurai.hud")

    class HUDOverlay:
        def __init__(self, *args, **kwargs):
            self.on_cancel = None

        def update(self, *args, **kwargs):
            pass

        def show(self, *args, **kwargs):
            pass

        def hide(self, *args, **kwargs):
            pass

    mod.HUDOverlay = HUDOverlay
    return mod


def _fake_paster() -> types.ModuleType:
    mod = types.ModuleType("murmurai.paster")
    mod.grab_selection = lambda *a, **k: ""
    mod.paste_text = lambda *a, **k: None
    mod.replace_text = lambda *a, **k: None
    return mod


def _fake_recorder() -> types.ModuleType:
    mod = types.ModuleType("murmurai.recorder")

    class AudioRecorder:
        def __init__(self, *args, **kwargs):
            pass

        def start(self, *args, **kwargs):
            pass

        def stop(self, *args, **kwargs):
            return None

    mod.AudioRecorder = AudioRecorder
    return mod


def _fake_transcriber() -> types.ModuleType:
    mod = types.ModuleType("murmurai.transcriber")

    class LocalTranscriber:
        def __init__(self, model_size=None, *args, **kwargs):
            self.model_size = model_size
            self.on_status = None
            self.on_text = None

        def transcribe(self, *args, **kwargs):
            return ""

    mod.LocalTranscriber = LocalTranscriber
    return mod


# Install stubs at import time so they are in place before any test module
# imports murmurai.app.
_stub_if_missing("rumps", _fake_rumps)
_stub_if_missing("Quartz", _fake_quartz)
_stub_if_missing("murmurai.hud", _fake_hud)
_stub_if_missing("murmurai.paster", _fake_paster)
_stub_if_missing("murmurai.recorder", _fake_recorder)
_stub_if_missing("murmurai.transcriber", _fake_transcriber)


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """Point murmurai.config at a throwaway config file under tmp_path."""
    import murmurai.config as cfg

    path = tmp_path / "config.json"
    monkeypatch.setattr(cfg, "CONFIG_FILE", path)
    monkeypatch.setattr(cfg, "_CONFIG_FILE", path)
    return path


def _base_config(**overrides) -> dict:
    config = {
        "whisper_model": "small",
        "transcript_key": "Right Option",
        "agent_key": "Right Command",
        "agent_model": "gemma3:latest",
        "jargon": {},
    }
    config.update(overrides)
    return config


@pytest.fixture
def base_config():
    return _base_config


@pytest.fixture
def app(tmp_config):
    """A MurmurAIApp instance with the heavy __init__ skipped.

    Only the attributes touched by the settings-reload code path are
    populated, with stubbed menu items so checkmark updates can be asserted.
    Depends on tmp_config so config-validity checks read a throwaway path
    (absent → valid) rather than the developer's real config file.
    """
    import murmurai.app as appmod

    instance = appmod.MurmurAIApp.__new__(appmod.MurmurAIApp)
    rumps = appmod.rumps

    def menu_with(names):
        parent = rumps.MenuItem("parent")
        for name in names:
            parent.add(rumps.MenuItem(name))
        return parent

    instance._is_recording = False
    instance._config = _base_config()
    instance._config_mtime = 0.0
    instance._current_model = "small"
    instance._transcript_key = "Right Option"
    instance._agent_key = "Right Command"
    instance._agent_model = "gemma3:latest"
    instance.title = "🎤"

    instance._transcript_key_menu = menu_with(appmod._HOTKEY_OPTIONS)
    instance._agent_key_menu = menu_with(appmod._HOTKEY_OPTIONS)
    instance._model_menu = menu_with(appmod._MODEL_SIZES)
    instance._agent_model_menu = menu_with([])
    instance._agent_model_titles = {}

    instance._edit_settings_item = rumps.MenuItem("Edit Settings…")
    instance._config_status_item = rumps.MenuItem(
        "⚠️ Invalid config — using defaults")

    # Reflect the initial selections in the menu checkmarks.
    instance._transcript_key_menu[instance._transcript_key].state = True
    instance._agent_key_menu[instance._agent_key].state = True
    instance._model_menu[instance._current_model].state = True

    instance.transcriber = appmod.LocalTranscriber(model_size="small")
    instance._hud = appmod.HUDOverlay()
    instance.recorder = appmod.AudioRecorder()
    return instance
