"""Storage for the names people use for projects and colleagues.

The mapping lives in data rather than in a prompt. "آواخرد" resolves to
FOLLOWUP because a row says so — no similarity metric can derive it, since
the two share no characters — and a new nickname is learned by writing a
row, not by editing a prompt and redeploying.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict
from typing import Iterable
from typing import List

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.assistant_entities import EntityAlias
from jira_telegram_bot.entities.assistant_entities import EntityKind
from jira_telegram_bot.entities.assistant_entities import EntityMatch
from jira_telegram_bot.entities.assistant_entities import EntityResolution
from jira_telegram_bot.utils.persian_text import normalize
from jira_telegram_bot.utils.persian_text import similarity

# Below this a trigram hit is noise rather than a typo.
MATCH_FLOOR = 0.45

# How many candidates to offer when asking the user which one they meant.
MAX_CANDIDATES = 4


class EntityAliasRepository:
    """Reads and writes the alias table backing entity resolution."""

    def __init__(self, storage_path: Path = None):
        """Initialize the repository.

        Args:
            storage_path: Where the aliases are kept; defaults to the
                settings directory next to the other configuration.
        """
        self._path = storage_path or (
            DEFAULT_PATH / "jira_telegram_bot" / "settings" / "entity_aliases.json"
        )
        self._aliases: List[EntityAlias] = []
        self._load()

    def _load(self) -> None:
        """Read the alias file, tolerating its absence on a first run."""
        if not self._path.exists():
            LOGGER.info(f"No alias file at {self._path}; starting empty")
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._aliases = [EntityAlias(**entry) for entry in raw]
            LOGGER.info(f"Loaded {len(self._aliases)} entity aliases")
        except Exception as exc:
            LOGGER.error(f"Could not read aliases from {self._path}: {exc}")

    def _save(self) -> None:
        """Persist the alias table."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(
                    [alias.model_dump() for alias in self._aliases],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            LOGGER.error(f"Could not write aliases to {self._path}: {exc}")

    def resolve(self, query: str, kind: EntityKind) -> EntityResolution:
        """Find what the user meant by a name.

        Args:
            query: The name as the user wrote it
            kind: Whether a project or a person is expected

        Returns:
            The candidates, best first. An exact alias scores 1.0; anything
            else is a trigram score the caller may decide is too low.
        """
        resolution = EntityResolution(query=query)
        needle = normalize(query)
        if not needle:
            return resolution

        best_per_target: Dict[str, EntityMatch] = {}
        for alias in self._aliases:
            if alias.kind is not kind:
                continue
            score = similarity(needle, alias.alias_norm)
            if score < MATCH_FLOOR:
                continue
            existing = best_per_target.get(alias.canonical)
            if existing is None or score > existing.score:
                best_per_target[alias.canonical] = EntityMatch(
                    canonical=alias.canonical,
                    display_name=alias.display_name or alias.canonical,
                    kind=kind,
                    score=score,
                )

        resolution.matches = sorted(
            best_per_target.values(),
            key=lambda match: match.score,
            reverse=True,
        )[:MAX_CANDIDATES]
        return resolution

    def learn(
        self,
        alias: str,
        kind: EntityKind,
        canonical: str,
        display_name: str = "",
    ) -> None:
        """Record a name the user confirmed, so it resolves next time.

        This is what keeps the table current: a nickname nobody anticipated
        becomes permanent the moment somebody confirms it once.

        Args:
            alias: The name as the user wrote it
            kind: Whether it names a project or a person
            canonical: The Jira project key or username it means
            display_name: Human-readable name of the target
        """
        alias_norm = normalize(alias)
        if not alias_norm:
            return
        for existing in self._aliases:
            if existing.alias_norm == alias_norm and existing.kind is kind:
                return
        self._aliases.append(
            EntityAlias(
                alias=alias,
                alias_norm=alias_norm,
                kind=kind,
                canonical=canonical,
                display_name=display_name or canonical,
            ),
        )
        self._save()
        LOGGER.info(f"Learned alias {alias!r} -> {canonical}")

    def add_many(self, aliases: Iterable[EntityAlias]) -> None:
        """Seed the table, skipping aliases that already exist.

        Args:
            aliases: The aliases to add
        """
        known = {(alias.alias_norm, alias.kind) for alias in self._aliases}
        added = 0
        for alias in aliases:
            if (alias.alias_norm, alias.kind) in known:
                continue
            self._aliases.append(alias)
            known.add((alias.alias_norm, alias.kind))
            added += 1
        if added:
            self._save()
            LOGGER.info(f"Seeded {added} entity aliases")

    def all_of(self, kind: EntityKind) -> List[EntityAlias]:
        """Return every alias of one kind.

        Args:
            kind: Which sort of alias to list

        Returns:
            The matching aliases.
        """
        return [alias for alias in self._aliases if alias.kind is kind]
