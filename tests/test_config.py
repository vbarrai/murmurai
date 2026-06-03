"""Tests for murmurai.config — load/save and defaults merging."""

import json

import murmurai.config as cfg


def test_load_missing_file_returns_defaults_without_creating(tmp_config):
    assert not tmp_config.exists()

    config = cfg.load()

    # A missing file must NOT be (re)created on load — defaults just apply.
    assert not tmp_config.exists()
    assert config["whisper_model"] == cfg._DEFAULTS["whisper_model"]
    assert config["transcript_key"] == cfg._DEFAULTS["transcript_key"]


def test_load_fills_missing_keys_from_defaults(tmp_config):
    tmp_config.write_text(json.dumps({"whisper_model": "medium"}), encoding="utf-8")

    config = cfg.load()

    # User value wins...
    assert config["whisper_model"] == "medium"
    # ...but absent keys fall back to defaults.
    assert config["agent_model"] == cfg._DEFAULTS["agent_model"]
    assert config["transcript_key"] == cfg._DEFAULTS["transcript_key"]


def test_user_value_overrides_default(tmp_config):
    tmp_config.write_text(
        json.dumps({"transcript_key": "Fn", "agent_key": "Left Control"}),
        encoding="utf-8",
    )

    config = cfg.load()

    assert config["transcript_key"] == "Fn"
    assert config["agent_key"] == "Left Control"


def test_save_then_load_roundtrip(tmp_config):
    original = {
        "whisper_model": "large-v3",
        "transcript_key": "Left Shift",
        "agent_key": "Right Shift",
        "agent_model": "llama3:8b",
        "jargon": {"kubectl": ["kubecétéèle"]},
    }

    cfg.save(original)
    loaded = cfg.load()

    for key, value in original.items():
        assert loaded[key] == value


def test_save_writes_utf8_with_trailing_newline(tmp_config):
    cfg.save({"jargon": {"déléguer": ["delegate"]}})

    raw = tmp_config.read_text(encoding="utf-8")

    # Non-ASCII is preserved (ensure_ascii=False) and file ends with newline.
    assert "déléguer" in raw
    assert raw.endswith("\n")


def test_load_corrupt_json_falls_back_to_defaults(tmp_config):
    tmp_config.write_text("{ this is not valid json", encoding="utf-8")

    config = cfg.load()

    # Corrupt file must not crash; defaults are returned instead.
    assert config["whisper_model"] == cfg._DEFAULTS["whisper_model"]
    assert config["agent_key"] == cfg._DEFAULTS["agent_key"]


def test_is_file_valid_true_when_missing(tmp_config):
    assert not tmp_config.exists()
    # Absent file is valid: defaults apply, nothing to flag.
    assert cfg.is_file_valid() is True


def test_is_file_valid_true_for_valid_json(tmp_config):
    cfg.save({"whisper_model": "base"})
    assert cfg.is_file_valid() is True


def test_is_file_valid_false_for_corrupt_json(tmp_config):
    tmp_config.write_text("{ this is not valid json", encoding="utf-8")
    assert cfg.is_file_valid() is False


def test_config_file_alias_points_to_same_path():
    # Public CONFIG_FILE and the legacy private alias must agree.
    assert cfg.CONFIG_FILE == cfg._CONFIG_FILE
