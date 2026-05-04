# LTS Policy

## LTS Branches

- Every major line may have one LTS branch.
- LTS receives security and critical fixes only.

## Support Window

- Minimum LTS support window: 12 months.
- Overlap period between LTS lines: 3 months.

## Backport Rules

- Backports must not alter public APIs.
- Backports require dedicated changelog entries.

## Consumer Guidance

- Stable production repos should track an LTS tag.
- Pilot repos can track latest minor versions.
