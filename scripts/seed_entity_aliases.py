"""Seed the entity alias table from Jira and the user configuration.

Run once to populate the names people actually use. Idempotent: existing
aliases are left alone, so it is safe to re-run after adding a project or a
teammate.

    python scripts/seed_entity_aliases.py --dry-run
    python scripts/seed_entity_aliases.py --execute
"""
from __future__ import annotations

import argparse
import sys

from jira_telegram_bot import LOGGER
from jira_telegram_bot.adapters.repositories.file_storage.entity_alias_repository import (
    EntityAliasRepository,
)
from jira_telegram_bot.app_container import get_container
from jira_telegram_bot.entities.assistant_entities import EntityAlias
from jira_telegram_bot.entities.assistant_entities import EntityKind
from jira_telegram_bot.use_cases.interfaces.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)
from jira_telegram_bot.utils.persian_text import normalize

# Persian names for products, and the keys their work is actually tracked
# under. Avakherad is the reason this file exists: its issues live in
# FOLLOWUP, which no amount of string similarity would ever discover.
PRODUCT_ALIASES = {
    "PARSCHAT": ["پارس‌چت", "پارسچت", "parschat", "پارس چت"],
    "PCT": ["تیکتینگ پارس‌چت", "تیکتینگ پارسچت", "parschat ticketing"],
    "FOLLOWUP": ["آواخرد", "اواخرد", "avakherad", "فالوآپر", "followupper"],
    # AVA exists but is nearly empty; the real work is under FOLLOWUP, so
    # its own project name must not compete for the word "Avakherad".
    "AVA": ["آواخرد قدیمی", "avakherad legacy"],
    "KHERADYAR": ["خردیار", "kheradyar", "کیهان صنعت", "keyhan sanat"],
    "ECDAROO": ["اکودارو", "echo daroo", "echoo-daroo"],
    "RETARGET": ["ری‌تارگت", "ریتارگت", "retargeting"],
    "RETKAN": ["ری‌تارگت کبن", "retargeting kbn"],
    "DASH": ["داشبورد", "dashboard"],
    "PARS": ["پارستک", "parstech"],
    "VOICE": ["تحلیل صدا", "voice analysis"],
}

# Persian surnames for the team, keyed by jira username. Only surnames are
# listed: "خانوم لطفیان" normalises to "لطفیان" before matching.
PERSON_ALIASES = {
    "a_kazemi": ["کاظمی", "علی کاظمی", "kazemi", "ali"],
    "z_lotfian": ["لطفیان", "زهرا لطفیان", "lotfian", "zahra"],
    "M_Samei": ["سمیعی", "samei"],
    "a_janloo": ["جانلو", "janloo"],
    "a_nasim": ["نسیم", "nasim"],
    "m_Mousavi": ["موسوی", "mousavi"],
    "A_heravi": ["هروی", "heravi"],
    "m_ebrahimi": ["ابراهیمی", "ebrahimi"],
    "j_hamed": ["حامد", "hamed"],
    "o_sadeghnezhad": ["صادق‌نژاد", "صادقنژاد", "sadeghnezhad"],
    "h_sayyedmousavi": ["سیدموسوی", "sayyed mousavi"],
    "z_hosseini": ["حسینی", "hosseini"],
    "a_khaboshani": ["خابوشانی", "khaboshani"],
    "m_oruji": ["عروجی", "oruji"],
    "d_fazeli": ["فاضلی", "fazeli"],
    "m_rezvani": ["رضوانی", "rezvani"],
    "sh_zanganeh": ["زنگنه", "zanganeh"],
}


def build_aliases(container) -> list[EntityAlias]:
    """Build the alias rows from Jira projects and the user configuration.

    Args:
        container: The dependency injection container

    Returns:
        Every alias worth seeding.
    """
    aliases: list[EntityAlias] = []

    jira = container[TaskManagerRepositoryInterface].jira
    try:
        projects = {project.key: project.name for project in jira.projects()}
    except Exception as exc:
        LOGGER.error(f"Could not list Jira projects: {exc}")
        projects = {}

    # Names that a curated alias already claims for a different key. Jira
    # calls AVA "Avakherad", but Avakherad's issues are tracked in FOLLOWUP,
    # so the project name must not override the curated mapping.
    # Map each curated alias to the key it belongs to, so a Jira project
    # name is only skipped when it is claimed by a *different* key.
    claimed = {
        normalize(text): key
        for key, texts in PRODUCT_ALIASES.items()
        for text in texts
    }

    for key, name in projects.items():
        # The key and the real project name are aliases in their own right,
        # unless a curated alias already points that name somewhere else.
        for text in {key, name}:
            owner = claimed.get(normalize(text))
            if owner is not None and owner != key:
                LOGGER.info(
                    f"Skipping Jira name {text!r} for {key}; curated for {owner}"
                )
                continue
            aliases.append(
                EntityAlias(
                    alias=text,
                    alias_norm=normalize(text),
                    kind=EntityKind.PROJECT,
                    canonical=key,
                    display_name=name,
                ),
            )
        for text in PRODUCT_ALIASES.get(key, []):
            aliases.append(
                EntityAlias(
                    alias=text,
                    alias_norm=normalize(text),
                    kind=EntityKind.PROJECT,
                    canonical=key,
                    display_name=name,
                ),
            )

    user_config = container[UserConfigInterface]
    for username, names in PERSON_ALIASES.items():
        for text in {username, *names}:
            aliases.append(
                EntityAlias(
                    alias=text,
                    alias_norm=normalize(text),
                    kind=EntityKind.PERSON,
                    canonical=username,
                    display_name=names[0] if names else username,
                ),
            )

    return [alias for alias in aliases if alias.alias_norm]


def main() -> int:
    """Seed the aliases."""
    parser = argparse.ArgumentParser(description="Seed entity aliases")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    container = get_container()
    aliases = build_aliases(container)
    repository = EntityAliasRepository()

    projects = sum(1 for a in aliases if a.kind is EntityKind.PROJECT)
    people = sum(1 for a in aliases if a.kind is EntityKind.PERSON)
    print(f"built {len(aliases)} aliases: {projects} project, {people} person")

    if args.dry_run:
        for alias in aliases[:15]:
            print(f"  {alias.alias!r:28} -> {alias.canonical}")
        print(f"  ... and {max(0, len(aliases) - 15)} more")
        print("\ndry run; nothing written")
        return 0

    repository.add_many(aliases)
    print(f"alias table now holds "
          f"{len(repository.all_of(EntityKind.PROJECT))} project and "
          f"{len(repository.all_of(EntityKind.PERSON))} person aliases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
