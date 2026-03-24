"""Technical jargon: English terms with their French-ified variants.

The built-in jargon ships with the app and is updated on upgrades.
User jargon from config.json is merged on top (additions/overrides).
"""

from __future__ import annotations

import re
import logging

from murmurai.config import load

log = logging.getLogger("murmurai")

# Built-in jargon: English term → list of French-ified variants Whisper may produce.
# Lowercase variants are matched case-insensitively.
BUILTIN_JARGON: dict[str, list[str]] = {
    # Git / version control
    "commit": ["commettre", "commiter", "comité", "commette"],
    "push": ["pousser", "poucher", "pousse"],
    "pull": ["tirer", "puller"],
    "merge": ["fusionner", "merger", "fusion"],
    "rebase": ["rebaser"],
    "cherry-pick": ["cherry-picker"],
    "stash": ["stasher"],
    "branch": ["brancher", "branche"],
    "checkout": ["checker"],
    "clone": ["cloner"],
    "fetch": ["fetcher"],
    "fork": ["forker"],
    "tag": ["taguer", "tagger"],
    "diff": ["differ"],
    "squash": ["squasher"],
    "reset": ["reseter", "réinitialiser"],
    "revert": ["reverter"],
    # Development workflow
    "deploy": ["déployer", "deployer"],
    "release": ["releaser", "relâcher"],
    "build": ["builder", "construire"],
    "debug": ["déboguer", "débugger", "debugger", "débugguer"],
    "refactor": ["refactorer", "refactoriser"],
    "review": ["reviewer", "revoir"],
    "sprint": ["sprinter"],
    "standup": ["stand-up"],
    "backlog": ["backloguer"],
    "ticket": ["ticketer"],
    "feature": ["featurer"],
    "hotfix": ["hotfixer"],
    "bugfix": ["bugfixer"],
    "rollback": ["rollbacker"],
    "staging": ["stager"],
    "production": ["productionner"],
    # Code concepts
    "API": ["api"],
    "endpoint": ["point de terminaison"],
    "frontend": ["front-end", "frontal"],
    "backend": ["back-end", "dorsal"],
    "fullstack": ["full-stack"],
    "framework": ["cadriciel"],
    "library": ["librairie", "bibliothèque"],
    "package": ["paquet", "paquetage"],
    "module": [],
    "plugin": ["plugiciel", "greffon"],
    "import": ["importer"],
    "export": ["exporter"],
    "async": ["asynchrone"],
    "await": ["attendre"],
    "callback": ["rappel"],
    "promise": ["promesse"],
    "middleware": ["intergiciel"],
    "proxy": ["mandataire"],
    "cache": ["cacher", "mémoire cache"],
    "router": ["routeur"],
    "handler": ["gestionnaire"],
    "payload": ["charge utile"],
    "token": ["jeton"],
    "webhook": ["crochet web"],
    "socket": ["prise"],
    "stream": ["flux", "streamer"],
    "runtime": ["exécution"],
    "compiler": ["compilateur"],
    "linter": ["linteur"],
    "formatter": ["formateur"],
    # Infrastructure / DevOps
    "cloud": ["nuage", "infonuagique"],
    "server": ["serveur"],
    "cluster": ["grappe"],
    "container": ["conteneur"],
    "pod": [],
    "namespace": ["espace de noms"],
    "pipeline": ["tuyau", "conduit"],
    "workflow": ["flux de travail"],
    "CI/CD": [],
    "DevOps": [],
    "docker": ["dockeriser"],
    "Kubernetes": [],
    "load balancer": ["équilibreur de charge"],
    # Data
    "database": ["base de données"],
    "query": ["requête", "requêter"],
    "schema": ["schéma"],
    "migration": ["migrer"],
    "seed": ["ensemencer", "seeder"],
    "index": ["indexer"],
    "join": ["joindre", "jointure"],
    "insert": ["insérer"],
    "update": ["mettre à jour"],
    "delete": ["supprimer", "déleter"],
    # Testing
    "test": ["tester"],
    "mock": ["mocker", "simuler"],
    "stub": ["stuber", "bouchon"],
    "fixture": [],
    "coverage": ["couverture"],
    "unit test": ["test unitaire"],
    "integration test": ["test d'intégration"],
    "end-to-end": ["bout en bout"],
    # Tools / technologies
    "TypeScript": [],
    "JavaScript": [],
    "Python": [],
    "React": [],
    "Node.js": [],
    "Git": [],
    "GitHub": [],
    "GitLab": [],
    "VS Code": [],
    "Slack": [],
    "Jira": [],
    "Confluence": [],
    "Notion": [],
    "Figma": [],
    # Agile / project
    "scrum": [],
    "kanban": [],
    "roadmap": ["feuille de route"],
    "milestone": ["jalon"],
    "deadline": ["date limite", "échéance"],
    "pull request": ["demande de tirage"],
    "code review": ["revue de code"],
    "pair programming": ["programmation en binôme"],
    "onboarding": ["intégration"],
    "offboarding": ["départ"],
}


def load_jargon() -> dict[str, list[str]]:
    """Return merged jargon: built-in + user additions from config."""
    merged = dict(BUILTIN_JARGON)
    user_jargon = load().get("jargon", {})

    if isinstance(user_jargon, dict):
        for term, variants in user_jargon.items():
            if term in merged:
                # Merge variants, avoid duplicates
                existing = set(merged[term])
                for v in variants:
                    if v not in existing:
                        merged[term].append(v)
            else:
                merged[term] = list(variants)
    elif isinstance(user_jargon, list):
        # Legacy format (plain list) — add as terms with no variants
        for term in user_jargon:
            if term not in merged:
                merged[term] = []

    return merged


def fuse_local(text_fr: str, text_en: str) -> str:
    """Replace French-ified technical terms in FR transcript with English originals.

    Uses the EN transcript to confirm which terms were actually spoken in English.
    Instant — no LLM call needed.
    """
    if not text_fr:
        return text_en or ""
    if not text_en:
        return text_fr

    jargon = load_jargon()
    result = text_fr
    en_lower = text_en.lower()

    for english_term, french_variants in jargon.items():
        # Check if the English term appears in the EN transcript
        if english_term.lower() not in en_lower:
            continue

        # Try to replace each French variant in the FR transcript
        for fr_variant in french_variants:
            if not fr_variant:
                continue
            # Case-insensitive replacement, preserve surrounding text
            pattern = re.compile(re.escape(fr_variant), re.IGNORECASE)
            if pattern.search(result):
                result = pattern.sub(english_term, result)
                log.debug("Fusion: '%s' → '%s'", fr_variant, english_term)

    return result
