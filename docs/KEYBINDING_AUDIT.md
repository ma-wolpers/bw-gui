# Keybinding Audit: activating `allow_modifiers` (2026-09-27)

`KeyBindingDefinition.allow_modifiers` has been part of the contract for a long time,
but `evaluate_runtime` never enforced it. Before enforcing it, every consumer was
checked for behaviour changes.

## Who is affected

The rule only applies to runtime contexts that carry modifier information
(`KeybindingRuntimeContext.modifiers is not None`). Only `WindowShortcutBinder` fills
that field. Contexts built by hand keep `modifiers=None` and behave exactly as before.

| Consumer | How contexts are built | Definitions | `allow_modifiers=True` | Behaviour change |
|---|---|---|---|---|
| bw-gui `laufkern` (reachability, shortcut resolution) | `laufkern.context.build_runtime_context` (no modifiers) | – | – | none |
| Blattwerk | own `KeybindingRuntimeContext` in `blatt_ui_base.py`; own `ShortcutManager` modifier check | 36 | 13 | none from the contract. The local Alt check (`0x0008`) was the NumLock bug and was replaced by `modifiers_from_event` |
| Korrektor | own context in `main_window_shortcuts.py` | 25 | 0 | none |
| Kursplaner | own context in `screen_builder.py` | 25 | 0 | none |
| aiza (`tools4school/aiza`) | own context in `app/gui/main_window.py` | – | 0 | none |
| Namenfit | `WindowShortcutBinder` | 11 (main + level dialog) | 0 | **yes**, see below |
| Kartograph | migrated to `WindowShortcutBinder` in the same change | 48+ | 0 | intended: the NumLock fix |

## Namenfit (the only behaviour change outside Kartograph)

- **Bindings affected:** `<Return>`, `<KP_Enter>`, `<space>`, `<BackSpace>` and
  `<Escape>`. All are `allow_when_text_input=True`.
- **What changes:** they no longer fire while Ctrl or Alt is held. For example,
  Ctrl+BackSpace in an entry now only does the widget's word deletion and no longer
  triggers the app action as well.
- **Unchanged:** Shift, NumLock and CapsLock never block.
- **Explicit modifier bindings keep working:** `<Alt-s>`, `<Alt-S>`,
  `<Control-Shift-d>` and `<Control-Shift-o>` declare their modifiers.
- **Parser check:** all Namenfit sequences pass the contract parser, and no two
  overlap (`find_conflicts` is empty).

This is considered intended: a modified key is a different shortcut.

## AltGr

- **Measurement:** on win32, AltGr (and Ctrl+Alt) combinations that produce a
  character arrive with `state=0x0` (live measurement, see `tests/live/`).
- **Consequence:** shortcuts on AltGr characters are never blocked, so no special
  rule is needed.

## Findings recorded for the follow-up plan

- **Hand-built runtime contexts:** Blattwerk, Korrektor, Kursplaner and aiza still
  build their own runtime contexts and wrap `bind` themselves. That is binder logic
  duplicated in the apps, and they receive no modifier gating until they move to
  `WindowShortcutBinder`. This is tracked in the Wunschliste (bw-gui), together with
  `TK_USAGE_INVENTORY.md`.
