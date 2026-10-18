# Keybinding Audit

## Keyboard contract migration: behaviour changes per app (2026-10)

All apps moved from Tk sequences and hand-built runtime contexts to the keyboard contract
(`KEYBINDING_CONTRACT.md`): `KeySpec` with **exact** modifiers, `EventResult`, the three
binders and `on_key`. Rules applied in every migration:

- **Named keys** that an app bound without an own Shift variant tolerate Shift (Tk's
  minimum-set matching made `<Escape>` fire with Shift+Escape); everything else is exact.
  Extra Ctrl/Alt no longer reach a binding (deliberate change 9 of the plan).
- **Character keys** are exact; a Shift variant is an explicit extra `KeySpec`. CapsLock
  and NumLock never take part in matching.
- **Keypad** Enter and digits/plus/minus act like the main block.
- `<KeyRelease>` became `on_key(phase="after")`: it runs only for keys no shortcut consumed.

Behaviour changes users can notice (each app's CHANGELOG has the user-facing wording):

| App | Change |
|---|---|
| Kursplaner | Ctrl+Alt+letter no longer triggers Ctrl shortcuts; Alt+↑/↓ no longer navigate; Ctrl+Shift+E/D/O work without CapsLock; Ctrl+Z of "Stundenplanänderung" only while that window is open (bug 2). Lesson dialogs: Ctrl+↑/↓ move the text cursor, Ctrl+Tab moves on natively, keypad Enter confirms; ↑/↓ in "Inhalte"/"Methodik" now work (the former KeyRelease refresh reset the selection). |
| Korrektor | Alt+← no longer pages like ←; Ctrl+Alt+N no longer creates an exam; Ctrl+Shift+D/O work without CapsLock; NumLock no longer turns a drag into an Alt-drag (bug 1). |
| Blattwerk | Ctrl+Alt+E no longer exports; Ctrl+Shift+H/S/F/D/O work without CapsLock, CapsLock no longer blocks single-letter shortcuts; NumLock no longer counts as Alt; keypad digits/plus/minus work; completion order after Enter/Tab; the colour-profile tooltip no longer blocks shortcuts (overlay stack). |
| Kartograph | Ctrl/Alt+arrow no longer move the grid selection; keypad Enter confirms dialogs; symbol-dialog digits fixed (bug 3); the seating-plan preview no longer blocks main-window shortcuts. |
| Namenfit | Ctrl+Shift+D/O fire exactly with those keys; single-letter shortcuts are no text input in read-only fields. |
| aiza | Enter sends, Shift+Enter inserts a newline (window and input binders). |

Popup gating moved to the overlay stack (`OVERLAY_STACK_CONTRACT.md`) with a
characterization test per app (former scan vs. preset); the only deliberate deviations
are listed there and in the app logs.

## Activating `allow_modifiers` (2026-09-27)

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

## Findings recorded for the follow-up plan (resolved 2026-10)

- **Hand-built runtime contexts** (Blattwerk, Korrektor, Kursplaner, aiza): resolved --
  all of them use the bw-gui binders now (see the migration table above); the runtime
  context for diagnostics comes from `binder.build_context()`.
