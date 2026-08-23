"""Tests for the launch-at-login LaunchAgent."""

import plistlib
from pathlib import Path

import murmurai.login_item as login_item


def _patch_paths(monkeypatch, tmp_path):
    plist = tmp_path / "com.vbarrai.murmurai.plist"
    monkeypatch.setattr(login_item, "PLIST_PATH", plist)
    monkeypatch.setattr(login_item, "_launchctl", lambda *a: True)
    return plist


def test_bundle_path_detected_from_executable(monkeypatch):
    monkeypatch.setattr(
        login_item.sys, "executable",
        "/Applications/murmurai.app/Contents/MacOS/murmurai",
    )

    assert login_item.app_bundle_path() == Path("/Applications/murmurai.app")


def test_bundle_path_is_none_when_running_from_source(monkeypatch):
    monkeypatch.setattr(login_item.sys, "executable", "/usr/bin/python3")

    assert login_item.app_bundle_path() is None
    assert login_item.is_available() is False


def test_enable_writes_launch_agent(monkeypatch, tmp_path):
    plist_path = _patch_paths(monkeypatch, tmp_path)
    bundle = Path("/Applications/murmurai.app")
    monkeypatch.setattr(login_item, "app_bundle_path", lambda: bundle)

    assert login_item.set_enabled(True) is True
    assert login_item.is_enabled() is True

    plist = plistlib.loads(plist_path.read_bytes())
    assert plist["Label"] == login_item.LABEL
    assert plist["RunAtLoad"] is True
    # `open -a` goes through LaunchServices so macOS keeps the Accessibility
    # and Microphone grants attached to the bundle rather than to launchd.
    assert plist["ProgramArguments"] == ["/usr/bin/open", "-a", str(bundle)]


def test_disable_removes_launch_agent(monkeypatch, tmp_path):
    plist_path = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        login_item, "app_bundle_path", lambda: Path("/Applications/murmurai.app"))
    login_item.set_enabled(True)

    assert login_item.set_enabled(False) is False
    assert not plist_path.exists()
    assert login_item.is_enabled() is False


def test_enable_is_refused_without_a_bundle(monkeypatch, tmp_path):
    plist_path = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(login_item, "app_bundle_path", lambda: None)

    # Running from source: there is nothing for launchd to relaunch.
    assert login_item.set_enabled(True) is False
    assert not plist_path.exists()


def test_disable_is_safe_when_nothing_installed(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        login_item, "app_bundle_path", lambda: Path("/Applications/murmurai.app"))

    assert login_item.set_enabled(False) is False
