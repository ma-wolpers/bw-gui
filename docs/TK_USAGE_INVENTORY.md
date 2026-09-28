# Inventory: Direct Tk Usage in Consumer Apps (2026-09-27)

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

## Proposed contracts (follow-up)

| Gap | Proposed bw-gui contract |
|---|---|
| Keyboard binds outside the binder; hand-built runtime contexts | Migrate to `WindowShortcutBinder` (+ `mode_provider`); widget-local key handling (e.g. arrow keys on a canvas) as a binder variant scoped to one widget |
| `.keysym`/`.char` interpretation (typing, navigation) | Semantic key-event model (`KeyEvent(keysym, char, modifiers)`) produced by bw-gui |
| Mouse binds with modifier semantics (Ctrl+click, Shift+click, wheel) | Pointer-gesture contract (click/drag/wheel with `KeyModifiers`, normalised wheel delta per backend) |
| Focus/Configure/Map binds | Lifecycle/focus-change hooks on bw-gui widgets |
| Virtual events (`<<ListboxSelect>>`, `<<TreeviewSelect>>` ...) | Intent callbacks on the bw-gui widget wrappers |
| `bind_all` (global handlers) | Explicit cross-window scope contract, only if genuinely needed |
| Remaining `tkinter` imports | Replace with `bw_gui.runtime` primitives; add missing primitives |
