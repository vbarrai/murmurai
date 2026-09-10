"""Tests for the mute-while-recording helper."""

import subprocess

import murmurai.system_audio as system_audio


class _FakeOsascript:
    """Records the scripts run and answers the "is it muted" query."""

    def __init__(self, muted=False, fail=False):
        self.muted = muted
        self.fail = fail
        self.calls = []

    def __call__(self, script):
        self.calls.append(script)
        if self.fail:
            raise OSError("osascript failed")
        if script.startswith("output muted of"):
            return "true" if self.muted else "false"
        if "muted true" in script:
            self.muted = True
        elif "muted false" in script:
            self.muted = False
        return ""


def _patch(monkeypatch, fake):
    monkeypatch.setattr(system_audio, "_osascript", fake)
    return fake


def test_mute_then_restore_unmutes(monkeypatch):
    fake = _patch(monkeypatch, _FakeOsascript(muted=False))
    muter = system_audio.OutputMuter()

    muter.mute()
    assert fake.muted is True

    muter.restore()
    assert fake.muted is False


def test_restore_leaves_output_muted_if_user_had_muted_it(monkeypatch):
    fake = _patch(monkeypatch, _FakeOsascript(muted=True))
    muter = system_audio.OutputMuter()

    muter.mute()
    muter.restore()

    # murmurai never un-mutes speakers the user had muted themselves.
    assert fake.muted is True
    assert not any("muted false" in call for call in fake.calls)


def test_restore_without_mute_is_a_noop(monkeypatch):
    fake = _patch(monkeypatch, _FakeOsascript(muted=False))

    system_audio.OutputMuter().restore()

    assert fake.calls == []


def test_double_mute_only_mutes_once(monkeypatch):
    fake = _patch(monkeypatch, _FakeOsascript(muted=False))
    muter = system_audio.OutputMuter()

    muter.mute()
    muter.mute()

    assert sum("muted true" in call for call in fake.calls) == 1


def test_restore_is_idempotent(monkeypatch):
    fake = _patch(monkeypatch, _FakeOsascript(muted=False))
    muter = system_audio.OutputMuter()

    muter.mute()
    muter.restore()
    before = len(fake.calls)
    muter.restore()

    assert len(fake.calls) == before


def test_failure_to_mute_does_not_raise_and_restore_is_a_noop(monkeypatch):
    fake = _patch(monkeypatch, _FakeOsascript(fail=True))
    muter = system_audio.OutputMuter()

    muter.mute()  # must not raise — muting is a nicety, not a requirement
    before = len(fake.calls)
    muter.restore()

    assert len(fake.calls) == before


def test_failure_to_restore_does_not_raise(monkeypatch):
    fake = _FakeOsascript(muted=False)
    _patch(monkeypatch, fake)
    muter = system_audio.OutputMuter()
    muter.mute()

    def _boom(_script):
        raise subprocess.SubprocessError("timeout")

    monkeypatch.setattr(system_audio, "_osascript", _boom)
    muter.restore()  # must not raise
