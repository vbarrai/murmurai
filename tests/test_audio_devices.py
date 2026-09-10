"""Tests for microphone enumeration and name→index resolution."""

import murmurai.audio_devices as devices


class _FakeSD:
    def __init__(self, table, default_index=None):
        self._table = table
        self.default = type("D", (), {"device": (default_index, None)})()

    def query_devices(self, index=None):
        if index is None:
            return self._table
        return self._table[index]


def _patch(monkeypatch, table, default_index=None):
    monkeypatch.setattr(devices, "sd", _FakeSD(table, default_index))


def test_list_skips_output_only_devices(monkeypatch):
    _patch(monkeypatch, [
        {"name": "MacBook Pro Microphone", "max_input_channels": 1},
        {"name": "MacBook Pro Speakers", "max_input_channels": 0},
    ])

    assert devices.list_input_devices() == [
        {"name": "MacBook Pro Microphone", "index": 0},
    ]


def test_list_keeps_original_indices(monkeypatch):
    _patch(monkeypatch, [
        {"name": "Speakers", "max_input_channels": 0},
        {"name": "Headset", "max_input_channels": 1},
    ])

    # The index must be the position in the full sounddevice table, not the
    # position among inputs — it is passed straight to sd.InputStream.
    assert devices.list_input_devices() == [{"name": "Headset", "index": 1}]


def test_list_deduplicates_names(monkeypatch):
    _patch(monkeypatch, [
        {"name": "Headset", "max_input_channels": 1},
        {"name": "Headset", "max_input_channels": 2},
    ])

    assert devices.list_input_devices() == [{"name": "Headset", "index": 0}]


def test_list_returns_empty_when_query_fails(monkeypatch):
    class _Broken:
        def query_devices(self, index=None):
            raise RuntimeError("HAL error")

    monkeypatch.setattr(devices, "sd", _Broken())

    assert devices.list_input_devices() == []


def test_resolve_empty_name_uses_system_default(monkeypatch):
    _patch(monkeypatch, [{"name": "Headset", "max_input_channels": 1}])

    assert devices.resolve_device("") is None
    assert devices.resolve_device(None) is None


def test_resolve_known_device(monkeypatch):
    _patch(monkeypatch, [
        {"name": "Speakers", "max_input_channels": 0},
        {"name": "Headset", "max_input_channels": 1},
    ])

    assert devices.resolve_device("Headset") == 1


def test_resolve_disconnected_device_falls_back_to_default(monkeypatch):
    _patch(monkeypatch, [{"name": "Headset", "max_input_channels": 1}])

    # The device is remembered in config but not plugged in right now:
    # recording must fall back to the system default rather than fail.
    assert devices.resolve_device("USB Mic") is None


def test_default_input_name(monkeypatch):
    _patch(monkeypatch, [
        {"name": "Headset", "max_input_channels": 1},
    ], default_index=0)

    assert devices.default_input_name() == "Headset"


def test_default_input_name_without_default(monkeypatch):
    _patch(monkeypatch, [], default_index=None)

    assert devices.default_input_name() is None
