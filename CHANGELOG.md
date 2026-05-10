# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Shared dialog service module `bw_gui.dialogs` with `MessageDialogService`, `TextPromptDialogService`, and `FileDialogService`.
- Shared tabbed settings dialog module `bw_gui.dialogs.settings_dialog` with schema-driven sections/fields and payload coercion helpers for cross-app settings integration.
- Shared button contract module `bw_gui.contracts.button` (`ButtonDefinition`, `ButtonRegistry`) for icon-first labels and intent-linked hover text generation.
- Modal-call routing in dialog services that respects popup-policy aware hosts via `_run_modal_dialog_call` when present.
- Unit tests for shared dialog services covering modal routing, default-root fallback, and file dialog result normalization.
- Unit tests for settings schema and payload coercion (`tests/test_settings_dialog.py`).
- Unit tests for button contract rendering and duplicate-id protection (`tests/test_button_contract.py`).
- `MessageDialogService.askretrycancel(...)` for startup/path-validation flows that need retry semantics via the shared dialog layer.
- Shared runtime aliases `bw_gui.runtime.ui` and `bw_gui.runtime.widgets` as a central import path for tkinter/ttk primitives.
- Shared runtime alias `bw_gui.runtime.fonts` for tkinter font primitives, enabling app modules to avoid direct `tkinter.font` imports.
- Theme contract documentation in `docs/THEME_CONTRACT.md` including guaranteed token keys, alias mapping, and domain fallback behavior.

### Changed
- Shared theme manager now exposes explicit contract helpers (`THEME_CORE_KEYS`, `THEME_CONTRACT_KEYS`, `theme_contract_keys`) for cross-repo theming integration.
- `get_theme(...)` now guarantees alias and domain-extension tokens for every theme (`error*` aliases and `hospitation*` fallback keys) while preserving per-theme overrides.
- Theming tests now validate presence of both Kursplaner and Blattwerk theme families plus full contract coverage for all registered themes.
- Shortcut label formatting now includes readable Tk-sequence normalization and intent-aware helper functions for button labels and hover overlays.
- Keybinding registry now provides intent-based shortcut resolution (`shortcut_for_intent`) used by shared button/tooltip contracts.

## [0.1.0] - 2026-05-04

### Added
- Initial shared GUI core scaffold.
- Central contracts (`keybinding`, `popup`, `hsm`).
- Unified theme manager with Kursplaner and Blattwerk theme families.
- Themed custom menubar primitive.
- Shared hover tooltip widget.
- Shortcut label formatting helpers.
