"""Tests for murmurai.jargon — franglais variant replacement and merging."""

import json

import murmurai.jargon as jargon


def test_builtin_jargon_is_non_empty():
    assert "commit" in jargon.BUILTIN_JARGON
    assert "push" in jargon.BUILTIN_JARGON


def test_fix_jargon_replaces_builtin_variant(tmp_config):
    # No user jargon configured.
    assert jargon.fix_jargon("je vais poucher la branche") == "je vais push la branche"


def test_fix_jargon_is_case_insensitive(tmp_config):
    # "Commiter" → "commit" regardless of input case.
    assert jargon.fix_jargon("Commiter le code") == "commit le code"


def test_fix_jargon_empty_string(tmp_config):
    assert jargon.fix_jargon("") == ""
    assert jargon.fix_jargon(None) == ""


def test_fix_jargon_leaves_unknown_words_untouched(tmp_config):
    text = "le chat dort sur le canapé"
    assert jargon.fix_jargon(text) == text


def test_load_jargon_merges_user_dict(tmp_config):
    tmp_config.write_text(
        json.dumps({"jargon": {"kubectl": ["kubecétéèle"]}}),
        encoding="utf-8",
    )

    merged = jargon.load_jargon()

    # User term added on top of built-ins.
    assert merged["kubectl"] == ["kubecétéèle"]
    assert "commit" in merged  # built-ins still present


def test_load_jargon_user_variant_extends_builtin(tmp_config):
    tmp_config.write_text(
        json.dumps({"jargon": {"commit": ["komitte"]}}),
        encoding="utf-8",
    )

    merged = jargon.load_jargon()

    # New variant appended, existing built-in variants kept, no duplicates.
    assert "komitte" in merged["commit"]
    assert "commiter" in merged["commit"]
    assert merged["commit"].count("komitte") == 1


def test_load_jargon_legacy_list_format(tmp_config):
    tmp_config.write_text(
        json.dumps({"jargon": ["graphql"]}),
        encoding="utf-8",
    )

    merged = jargon.load_jargon()

    # Legacy plain-list terms are registered with no variants.
    assert merged["graphql"] == []


def test_fix_jargon_uses_user_variant(tmp_config):
    tmp_config.write_text(
        json.dumps({"jargon": {"terraform": ["terraformeur"]}}),
        encoding="utf-8",
    )

    assert jargon.fix_jargon("lance terraformeur") == "lance terraform"
