# bw-gui

Shared GUI core for Blattwerk-family apps.

## Goals

- One consistent Tkinter and ttk GUI baseline across all target repos.
- No native menubar islands; themed custom menu surfaces.
- Central shortcut, popup, and HSM contracts.
- Icon-first action surfaces with hover help and shortcut visibility.
- Unified theme model based on Kursplaner, extended with Blattwerk themes.

## Scope v0.1.0

- Contracts: keybinding, popup, hsm
- Theming: unified theme registry and ttk setup
- Runtime host: composed Tk root host (`bw_gui.runtime.TkRootHost`)
- Menu: themed custom menubar widget
- Dialogs: shared settings dialog and scrollable popup host
- Widgets: hover tooltip primitive
- Widgets: wrapped multiline text field with word-delete shortcuts
- Shortcuts: shared label formatting helpers

## Integration (Submodule-first)

The consuming repos include this repository as git submodule and import from `bw_gui`.

## Governance

See:
- docs/RELEASE_POLICY.md
- docs/LTS_POLICY.md
- docs/MIGRATION_GUIDE.md
