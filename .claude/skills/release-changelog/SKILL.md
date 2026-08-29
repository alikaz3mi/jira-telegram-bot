---
name: release-changelog
description: Cut a release — decide the version, write the changelog, bump __version__. Use when asked to prepare a release, write a changelog, or bump the version.
---

# Cutting a release

## 1. Establish the scope

```bash
git log --oneline $(git describe --tags --abbrev=0 2>/dev/null || echo HEAD~20)..HEAD
git status --short
```

Read the diffs, not only the subjects. A commit titled as a fix often carries
a behaviour change worth naming.

## 2. Choose the version

Current value is `__version__` in `jira_telegram_bot/__init__.py`.

| Change | Bump |
|---|---|
| Breaking contract change | MAJOR |
| New feature or capability | MINOR |
| Bug fix, cleanup, docs | PATCH |

A feature never ships in a patch. When in doubt between two, take the larger.

## 3. Write `docs/changelog/{version}.md`

Open with `## Summary` in terms of what changed for the people using the bot,
not the modules that moved. Then `## Features`, `## Fixes`, `## DevOps`,
`## Dependencies` as they apply.

For each fix, say what was wrong and why it mattered:

> An issue only became `SHOULD_BE_STARTED` when its Target start was set and
> had passed, so undated sprint work was dropped — 8 of 47 issues survived and
> the assistant answered "you have no tasks" with confidence.

That sentence is worth more than five bullets naming functions.

A dependency change records the constraint that forced it — the next person
hitting the same wall needs the reason, not the number.

## 4. Record what is still broken

A `## Notes` section for known limitations shipping with the release. A known
problem written down is a decision; the same problem unwritten is a trap for
whoever meets it next.

## 5. Bump and verify

Update `__version__`, then:

```bash
python -c "import jira_telegram_bot; print(jira_telegram_bot.__version__)"
```

`setup.py` reads that constant, so this is the only place to change it.

Do not commit or tag unless asked.
