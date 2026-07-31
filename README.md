# bw-gui

Shared GUI core for Blattwerk-family apps.

## Architecture

bw-gui is built on four principles that all consumer programs must follow:

**A. bw-gui is the only entity that knows about colours.** Programs never
construct hex strings, call `get_theme()` for raw values, or maintain their
own colour variables.

**B. Programs express intent; the framework acts.** A program says "a canvas
that belongs to the theme" or "an icon button tinted for Hospitation" — bw-gui
decides what that looks like and applies it.

**C. The theme is ambient.** After `configure_ttk_theme(root, key)` is called,
all utility calls (`theme_canvas`, `tinted_color`, …) resolve the current theme
automatically — no `theme_key` argument is passed around.

**D. Composite widgets are the right abstraction.** `icon_button(parent, photo,
command, color_tint=seed)` creates, colors, and auto-recolors the button on every
theme switch — the consumer does zero colour work, forever.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full rationale,
anti-pattern table, and API guidance.

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
