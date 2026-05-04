# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Shared dialog service module `bw_gui.dialogs` with `MessageDialogService`, `TextPromptDialogService`, and `FileDialogService`.
- Modal-call routing in dialog services that respects popup-policy aware hosts via `_run_modal_dialog_call` when present.
- Unit tests for shared dialog services covering modal routing, default-root fallback, and file dialog result normalization.

## [0.1.0] - 2026-05-04

### Added
- Initial shared GUI core scaffold.
- Central contracts (`keybinding`, `popup`, `hsm`).
- Unified theme manager with Kursplaner and Blattwerk theme families.
- Themed custom menubar primitive.
- Shared hover tooltip widget.
- Shortcut label formatting helpers.
