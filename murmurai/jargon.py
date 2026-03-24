"""Technical jargon helpers — reads from centralized config."""

from murmurai.config import load, save


def load_jargon() -> list[str]:
    """Return the current jargon list from config."""
    return load()["jargon"]


def save_jargon(words: list[str]):
    """Update the jargon list in config."""
    config = load()
    config["jargon"] = words
    save(config)
