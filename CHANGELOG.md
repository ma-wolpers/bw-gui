# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Shared runtime root host `bw_gui.runtime.TkRootHost` for composed Tk root delegation in app adapters.
- Shared scrollable popup host `bw_gui.dialogs.ScrollablePopupWindow` with modal focus/escape handling and reusable theme hooks.
- Shared multiline form widget `bw_gui.widgets.WrappedTextField` with editor-like Ctrl+Backspace/Ctrl+Delete behavior.
- Unit tests for root host, scrollable popup behaviors, and wrapped text field helpers (`tests/test_runtime_root_host.py`, `tests/test_scrollable_popup.py`, `tests/test_wrapped_text_field.py`).
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
- Runtime and widget/dialog package exports now include the new Step-4 primitives (`TkRootHost`, `ScrollablePopupWindow`, `WrappedTextField`) as stable shared import paths.
- Shared primitives now also delegate `__str__` to their composed Tk widgets (`TkRootHost.tk_root`, `ScrollablePopupWindow._popup_window`, `WrappedTextField._container`) so parent/transient calls that stringify masters stay valid across consuming apps.
- Shared theme manager now exposes explicit contract helpers (`THEME_CORE_KEYS`, `THEME_CONTRACT_KEYS`, `theme_contract_keys`) for cross-repo theming integration.
- `get_theme(...)` now guarantees alias and domain-extension tokens for every theme (`error*` aliases and `hospitation*` fallback keys) while preserving per-theme overrides.
- Theming tests now validate presence of both Kursplaner and Blattwerk theme families plus full contract coverage for all registered themes.
- Shortcut label formatting now includes readable Tk-sequence normalization and intent-aware helper functions for button labels and hover overlays.
- Keybinding registry now provides intent-based shortcut resolution (`shortcut_for_intent`) used by shared button/tooltip contracts.
- Custom menu bar now keeps active top-level menu state visually in sync and reapplies theme updates to already opened popup levels.
- Custom menu bar now supports replacing menu definitions at runtime via `set_definitions(...)` and rebuilding safely.
- Custom menu bar now renders mnemonic underlines for top-level buttons and resolves Alt navigation through one centralized keypress handler.
- Open menu overlays now close reliably on focus changes (inside and outside the app window), and popups no longer enforce a global topmost flag.
- Shared hover tooltip now uses delayed display, resolves active theme keys from the hosting window, clamps position to visible screen bounds, and cancels pending shows on focus/visibility changes.
- Shared ttk theming now includes settings-dialog helper styles (`Settings.Panel.TFrame`, `Settings.Sidebar.TFrame`, `SettingsHint.TLabel`) and refined scrollbar contrast/active mappings.

## [0.1.0] - 2026-05-04

### Added
- Initial shared GUI core scaffold.
- Central contracts (`keybinding`, `popup`, `hsm`).
- Unified theme manager with Kursplaner and Blattwerk theme families.
- Themed custom menubar primitive.
- Shared hover tooltip widget.
- Shortcut label formatting helpers.
