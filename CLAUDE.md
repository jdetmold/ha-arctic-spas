# CLAUDE.md

Working notes for AI assistants and humans collaborating on this repo.

## Releases & Versioning

This project uses **manual, version-driven releases**. Workflow:

1. Bump `custom_components/arctic_spa_local/manifest.json` `"version"` in a PR (semver: `MAJOR.MINOR.PATCH`).
2. Merge the PR to `main`.
3. Trigger the **Release** workflow in the GitHub Actions tab (`workflow_dispatch`). It reads the version from `manifest.json`, fails if that tag already exists, re-runs hassfest + HACS validation, then creates the tag and GitHub Release.
4. HACS users see the update notification within a few hours.

Pre-1.0 semver: bump minor for features, patch for fixes; breaking changes are acceptable without a major bump. Once at `1.0.0`, breaking changes require a major bump.

## PR titles (release notes are auto-generated from them)

PR titles become release-note line items, so write them for end users. Lead with a verb. Don't include ticket numbers or internal jargon.

- Good: `Add jet boost switch entity`
- Good: `Fix temperature sensor offset on dual-zone tubs`
- Good: `Bump protobuf to 6.32`
- Bad: `WIP`, `fix`, `update stuff`, `addressing review comments`

## PR labels (group the release notes)

Apply at least one of these labels to every PR. They map to changelog sections via `.github/release.yml`.

| Label | When to use |
|---|---|
| `breaking` | Removes or renames entities, changes config schema, requires user action on upgrade |
| `feature` / `enhancement` | New entity, new capability, new config option |
| `bugfix` / `bug` | Fixes broken behavior |
| `docs` / `documentation` | README, docstrings, comments only |
| `chore` / `refactor` / `dependencies` | Internal cleanup, dep bumps, CI changes |
| `ignore-for-release` | Hide this PR from the release notes entirely (e.g. release-prep PRs that just bump the version) |

Unlabeled PRs land in "Other Changes."

## Commit messages and PR descriptions

**Strict rule: commit messages and PR descriptions are a point-form list of changes made. Nothing else. Ever.**

- No `Co-Authored-By` lines
- No `Generated with Claude Code` / `Generated with [tool]` footers
- No author attribution of any kind
- No prose summaries, motivation paragraphs, or "Test plan" sections
- No emojis

Example of an acceptable commit message:

```
Bump manifest.json to 0.2.0

- Add jet boost switch entity
- Fix temperature offset on dual-zone tubs
- Update protobuf pin to 6.32
```

Only the PR title appears in release notes — commit messages within a PR are not surfaced. Prefer squash-merge so `main` history stays one-commit-per-PR.
