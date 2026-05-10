# Theme Contract

This document defines the stable token contract returned by `bw_gui.theming.get_theme(...)`.

## Goal

- Keep one shared theme registry for all consumer apps.
- Support both Kursplaner and Blattwerk theme families everywhere.
- Provide deterministic fallback and alias tokens to avoid app-specific breakage.

## Core Keys

Every registered theme must define or derive these base keys:

- `bg_main`
- `bg_surface`
- `fg_primary`
- `fg_muted`
- `accent`
- `accent_hover`
- `accent_soft`
- `danger`
- `border`

## Guaranteed Contract Keys

`get_theme(...)` guarantees all keys listed by `theme_contract_keys()`.

This currently includes:

- Base and structure: `label`, `bg_panel`, `panel_strong`, `secondary`, `secondary_soft`
- Selection: `selection_bg`, `selection_fg`
- State colors: `success`, `success_hover`, `success_soft`, `warning`, `warning_hover`, `warning_soft`, `danger_hover`, `danger_soft`
- Foreground helpers: `button_fg`, `fg_on_accent`, `fg_on_success`, `fg_on_warning`, `fg_on_danger`
- Focus: `focus_ring`
- Alias family: `error`, `error_hover`, `error_soft`, `fg_on_error`
- Domain extension: `hospitation`, `hospitation_hover`, `hospitation_soft`, `fg_on_hospitation`

## Alias Rules

The following aliases are resolved for every theme:

- `error` -> `danger`
- `error_hover` -> `danger_hover`
- `error_soft` -> `danger_soft`
- `fg_on_error` -> `fg_on_danger`

## Domain Fallback Rules

For themes that do not define Kursplaner-specific domain colors, `get_theme(...)` derives safe defaults:

- `hospitation` as a blend of `accent` and `warning`
- `hospitation_hover` as hover shade of `hospitation`
- `hospitation_soft` as panel blend with `hospitation`
- `fg_on_hospitation` as contrast-aware foreground
