# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- New centralized settings flow helper `bw_gui.dialogs.SettingsDialogOrchestrator` to wire theme/spec/value providers and commit handlers behind one reusable open call.
- Standardized menu-definition builder in `bw_gui.menu.standard_menu` (`section_spec`, `build_standard_menu_definitions`) for consistent core menu ordering with app-specific extension sections.
- New `bw_gui.laufkern` core package with manifest validation, route reachability checks, step/reason-code standards, and completion-tracking aggregation for LaufKern-based app integration.
- Unit tests for LaufKern manifest/reachability/tracking behavior (`tests/test_laufkern.py`).
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
- Shared grid-span layout helper `bw_gui.widgets.grid_span` (`GridSpanSegment`, `compute_contiguous_spans`) for mapping a contiguous run of Tk grid columns to minimal `columnspan` segments.
- New `checkbox` `MenuItem` type in `bw_gui.menu`, rendered with ☑/☐ prefixes alongside the existing `radio` type.
- `BwBaseWindow`: neue Basisklasse fuer Standard-App-Fenster mit integriertem Theme-Management, zentraler Menu-Leiste und `BwBaseWindowConfig` fuer einheitliche Fenster-Initialisierung.
- `TkinterAppShell`: Shell-Helfer zum einmaligen Aufspannen des Tk-Root-Fensters mit zentraler Identity- und Lifecycle-Konfiguration.
- Neue Theming-Hilfsfunktionen: `tinted_color`, `tinted_foreground` und `recolor_photo_token` fuer konsistente Farbberechnung auf Basis zentraler Token-Werte.
- `get_theme(None)` gibt jetzt das gerade aktive Theme zurueck (ambient lookup) ohne explizite Namensangabe.
- `icon_button`: neuer Widget-Baustein fuer beschriftungslose Icon-Schaltflaechen mit konsistenter Hover- und Theme-Anbindung.
- Neue Canvas-Zeichenprimitive: `recolor_photo`, `canvas_domain_fill`, `canvas_domain_outline` fuer domain-faerbbare Canvas-Grafikbausteine.
- `ring_chart`: neues Widget fuer einfache Ring-/Donut-Diagramme mit Theme-Anbindung.
- `MenuItem`- und `MenuDefinition`-Typen fuer typsichere deklarative Menu-Spezifikationen.

### Fixed
- `ScrollablePopupWindow`: Schließen (Fensterknopf/Escape) blendet das Fenster jetzt sofort per `withdraw()` aus, bevor der Widget-Baum zerstört wird — vermeidet einen sichtbaren Teardown-Effekt bei Popups mit vielen/verschachtelten Widgets (z. B. `Panedwindow` mit mehreren Kind-Frames), bei dem die Widgets beim Schließen sichtbar kollabierten, bevor das Fenster verschwand. `_request_close()` ist zusätzlich idempotent (ein `_closing`-Guard verhindert einen doppelten `destroy()`-Aufruf, falls zwei Close-Pfade kurz hintereinander feuern).
- `ScrollablePopupWindow`: Escape schließt das Popup jetzt immer, unabhängig vom Fokus. Vorher wurde bei fokussiertem Eingabefeld (Entry/Text/Spinbox/Combobox) nur erneut `focus_force()` auf das ohnehin schon fokussierte Popup-Fenster aufgerufen — das hatte keine sichtbare Wirkung, Escape schien beim Tippen wirkungslos.
- `TextPromptDialogService.askstring(...)`: Escape im Textprompt-Dialog stoppt jetzt zuverlässig am Dialog, statt bis zu darunterliegenden Fenstern weiterzulaufen (z. B. einem globalen `bind_all("<Escape>")`-Handler der aufrufenden App). Ursache war der eingebaute `tkinter.simpledialog.Dialog.cancel`, der `None` statt `"break"` zurückgab.
- Popups und Tooltips wurden bisher immer auf dem primaeren Monitor positioniert, auch wenn das App-Fenster auf einem anderen Monitor lief. Die Positionierung berechnet jetzt den zustaendigen Monitor anhand der aktuellen Fensterposition und platziert Popups korrekt auf dem richtigen Bildschirm.

### Changed
- LaufKern completion aggregation now enforces a strict completion gate: `summary.status` becomes `complete` only when all mandatory steps have completed artifacts with non-empty `evidence_ref` values and no trust/checksum/sequence errors are present.
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
