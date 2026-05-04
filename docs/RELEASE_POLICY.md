# Release Policy

This repository follows strict release governance.

## Versioning

- SemVer is mandatory.
- Patch: bugfixes only, no API break.
- Minor: backward-compatible features.
- Major: breaking changes with migration guide.

## Breaking Change Rules

- Every breaking change requires:
  - A migration section in docs/MIGRATION_GUIDE.md.
  - A changelog entry under a dedicated "Breaking" heading.
  - Compatibility impact notes for all consumer repos.

## Quality Gates

- CI must pass on each release tag.
- Contract tests must pass for keybinding, popup, and hsm modules.
- Manual GUI sanity checklist must be completed before major or minor release.

## Consumer Notification

- Each release includes a short "consumer action" note.
- Consumer repos pin explicit tags when stability is required.
