---
paths: ["docs/changelog/**/*.md", "jira_telegram_bot/__init__.py"]
---
# Changelog rules

## Version source of truth

`__version__` in `jira_telegram_bot/__init__.py`. `setup.py` reads it from
there. A changelog and that constant are always updated in the same change.

## SemVer

| Change | Bump |
|---|---|
| Breaking contract change | MAJOR |
| New feature or capability | MINOR |
| Bug fix, cleanup, docs | PATCH |

A feature never ships inside a patch release.

## Files

- One file per version: `docs/changelog/{MAJOR}.{MINOR}.{PATCH}.md`.
- Never rewrite an existing version file to describe a different release.

## Contents

Open with a `## Summary` that says what changed for the people using the bot,
then `## Features`, `## Fixes`, `## DevOps`, `## Dependencies` as they apply.

Write what was wrong and why it mattered, not only what moved:

> An issue only became `SHOULD_BE_STARTED` when its Target start was set and
> had passed, so anything undated fell through to `OK` and was dropped. Only
> 8 of 47 issues survived for one user.

A `## Notes` section records what is knowingly still broken. A known
limitation written down is a decision; one left out is a trap.
