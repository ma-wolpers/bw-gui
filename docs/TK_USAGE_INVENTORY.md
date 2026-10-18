# Inventory: Direct Tk Usage in Consumer Apps

## Status 2026-10-17 (after the keyboard, pointer, overlay and widget-events migration)

The same regex categories as the 2026-09-27 baseline below, plus the AST guards that now
run in every app's test suite (`tk_usage_guard`, `tk_state_guard`):

| Category | Kartograph | Blattwerk | Korrektor | Kursplaner | Namenfit | aiza |
|---|---|---|---|---|---|---|
| Keyboard `bind(...)` outside the binder | 1* | 1* | 0 | 1* | 0 | 0 |
| Mouse `bind(...)` (Button/Motion/Wheel/Enter/Leave) | 0 | 0 | 0 | 2* | 0 | 0 |
| Focus/Configure/Map `bind(...)` | 0 | 0 | 0 | 0 | 0 | 0 |
| Virtual-event `bind("<<...>>")` | 0 | 0 | 0 | 0 | 0 | 0 |
| `bind_all(...)` | 0 | 0 | 0 | 0 | 0 | 0 |
| `.keysym` / `.char` reads | 0 | 0 | 0 | 0 | 0 | 0 |
| `import tkinter` | 2 files** | 0 | 0 | 0 | 0 | 0 |
| `tk_usage_guard` findings (AST) | 0 | 0 | 0 | 0 | 0 | 0 |
| `tk_state_guard` findings (AST) | 0 | 0 | 0 | 0 | 0 | 0 |

\* Regex hits in docstrings that describe the former code (e.g. "früher
`widget.bind("<Button-1>")`"); the AST guard skips docstrings and reports none.
\** Developer benchmark scripts under `kartograph/app/tools/` (not part of the GUI).

Every consumer GUI now goes through `KEYBINDING_CONTRACT.md` (binders, `on_key`),
`POINTER_CONTRACT.md` (`bind_click`/`bind_drag`/`bind_wheel`/`on_global_click`,
`PointerGroup`, `bind_hover`, `bind_canvas_item`), `OVERLAY_STACK_CONTRACT.md` (popup
gating, Escape target) and `WIDGET_EVENTS_CONTRACT.md` (lifecycle, selection,
activation). Deliberate exceptions would carry `# bw-tk: <reason>`; there are none.

## Baseline 2026-09-27

Principle E in `ARCHITECTURE.md` says apps need no Tk knowledge. Where an app still
needs it, a bw-gui contract is missing. This inventory lists the direct Tk usage that
remains after the keybinding/modifier contract was introduced. It is the basis for a
follow-up plan and is tracked in `tools4school/Wunschliste.md` under bw-gui.

The counts come from a plain regex scan of the app sources (tests, `.venv`, `dist`
and vendored `bw-gui` are excluded), so they are indicative, not exact:

- `event.state` also matches unrelated attributes such as `controller.state`.
- The Kartograph figures predate its shortcut migration in the same change, which
  removes its keyboard `bind_all` calls and bitmask checks.

| Category | Kartograph | Blattwerk | Korrektor | Kursplaner | Namenfit |
|---|---|---|---|---|---|
| Keyboard `bind(...)` outside the binder | 53 | 79 | 24 | 65 | 1 |
| Mouse `bind(...)` (Button/Motion/Wheel/Enter/Leave) | 19 | 22 | 14 | 23 | 0 |
| Focus/Configure/Map `bind(...)` | 12 | 5 | 6 | 15 | 0 |
| Virtual-event `bind("<<...>>")` | 6 | 8 | 7 | 4 | 0 |
| `bind_all(...)` | 10 | 1 | 2 | 4 | 0 |
| `.keysym` / `.char` reads | 2 | 10 | 0 | 1 | 0 |
| `.state` reads (incl. false positives) | 21 | 7 | 4 | 4 | 1 |
| `import tkinter` | 2 files | 1 file | 0 | 0 | 0 |

In addition, Blattwerk, Korrektor, Kursplaner and aiza build their own
`KeybindingRuntimeContext` and wrap `bind` themselves, which duplicates the binder
(see `KEYBINDING_AUDIT.md`). They get no modifier gating until they migrate.

Binary controls (`Checkbutton`, `add_checkbutton`) are covered separately by the
toggle contract (`TOGGLE_CONTRACT.md`): all consumers migrate to
`Checkbox`/`Switch`, enforced by `bw_gui.testing.checkbutton_guard`.

## Proposed contracts (follow-up) and what implemented them

The right column was the 2026-09-27 proposal; the status column shows the contract that
closed the gap.

| Gap | Proposed bw-gui contract | Status 2026-10-17 |
|---|---|---|
| Keyboard binds outside the binder; hand-built runtime contexts | Migrate to `WindowShortcutBinder` (+ `mode_provider`); widget-local key handling (e.g. arrow keys on a canvas) as a binder variant scoped to one widget | `WindowShortcutBinder`/`ApplicationShortcutBinder`/`WidgetShortcutBinder` with `KeySpec` (`KEYBINDING_CONTRACT.md`) |
| `.keysym`/`.char` interpretation (typing, navigation) | Semantic key-event model (`KeyEvent(keysym, char, modifiers)`) produced by bw-gui | `KeyEvent(key, text, modifiers)`, `on_key(phase)` |
| Mouse binds with modifier semantics (Ctrl+click, Shift+click, wheel) | Pointer-gesture contract (click/drag/wheel with `KeyModifiers`, normalised wheel delta per backend) | `bind_click`/`bind_drag`/`bind_wheel`, `PointerGroup`, `bind_hover`, `bind_canvas_item` (`POINTER_CONTRACT.md`) |
| Focus/Configure/Map binds | Lifecycle/focus-change hooks on bw-gui widgets || Lifecycle/focus-change hooks on bw-gui widgets | `on_resize`, `on_focus_change`, `on_visibility`, `on_destroy`, `on_text_modified`, `on_tab_changed` (`WIDGET_EVENTS_CONTRACT.md`) |
| Virtual events (`<<ListboxSelect>>`, `<<TreeviewSelect>>` ...) | Intent callbacks on the bw-gui widget wrappers || Intent callbacks on the bw-gui widget wrappers | `on_listbox_select`/`on_treeview_select`/`on_combobox_select` + mutation objects, `on_activate` |
| `bind_all` (global handlers) | Explicit cross-window scope contract, only if genuinely needed | `ApplicationShortcutBinder` (`all` router), `on_global_click`; consumer `bind_all` is gone |
| Remaining `tkinter` imports | Replace with `bw_gui.runtime` primitives; add missing primitives | no GUI module imports `tkinter` any more |
