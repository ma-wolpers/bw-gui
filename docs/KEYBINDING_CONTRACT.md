# Keybinding Contract

bw-gui is the single place that understands Tk's keyboard semantics. Consumer apps
declare *which* shortcut should trigger *which* intent in *which* UI mode. They never
interpret `event.state`, never parse or compare Tk sequence strings and never decide
themselves whether a held modifier should block a shortcut.

If an app needs Tk keyboard knowledge that this contract does not offer yet, the
contract is incomplete. Extend it here instead of writing a local helper.

Modules:

| Module | Responsibility |
|---|---|
| `bw_gui.contracts.key_modifiers` | Tk backend normalisation, `KeyModifiers`, `event.state` decoding |
| `bw_gui.contracts.key_sequence` | Parsing keyboard sequences, declared modifiers, `BindingSignature` |
| `bw_gui.contracts.keybinding` | `KeyBindingDefinition`, runtime context, `evaluate_binding`, registry |
| `bw_gui.contracts.keybinding_conflicts` | Semantic conflict detection over the full runtime applicability |
| `bw_gui.runtime.shortcuts` | `WindowShortcutBinder`: binding, gating, multiplexing for one toplevel |

## Platform vs. Tk backend

The modifier bits depend on the windowing system Tk talks to (the Tk backend), not
on the operating system.

| `sys.platform` | Tk backend |
|---|---|
| `win32`, `cygwin` | `win32` |
| `darwin` | `aqua` |
| `linux*`, `freebsd*`, `openbsd*`, `netbsd*` | `x11` |
| anything else | `ValueError` |

`sys.platform` never returns `"x11"`. At runtime the binder asks the window itself
(`tk windowingsystem`), which is authoritative. `backend_for_platform()` is only the
fallback without a Tk interpreter.

## Modifier model

`KeyModifiers(shift, control, alt, command)` is a deliberately **semantic** model,
not a mirror of the Tk bit field. Lock keys and mouse buttons are not represented.

A **shortcut modifier** is Control, Alt/Option or Command: a modifier that turns a
key into a different command (`has_shortcut_modifier`). Shift is not a shortcut
modifier, because it changes the produced character (`a` becomes `A`, `=` becomes
`+`) rather than the command.

### `event.state` masks

| Modifier | win32 | aqua | x11 |
|---|---|---|---|
| Shift | `0x1` | `0x1` | `0x1` |
| Control | `0x4` | `0x4` | `0x4` |
| Alt / Option | `0x20000` | `0x10` (Option) | `0x8` (Mod1) |
| Command | – | `0x8` (Mod1) | – |
| NumLock (ignored) | `0x8` | – | usually `0x10` (Mod2) |

How far each column is verified:

- **win32 is verified live.** It was measured with real key strokes on Windows 11 and
  Tk 8.6.15 (`tests/live/test_live_keyboard.py`). NumLock adds `0x8` to *every* state
  while it is on.
- **This is the Windows NumLock trap.** Code that reads `0x8` as "Alt" (correct on X11)
  treats every key as Alt-modified as soon as NumLock is on. That exact bug disabled
  the single-letter shortcuts in Kartograph and Blattwerk.
- **AltGr is never gated on win32.** AltGr and Ctrl+Alt combinations that produce a
  character arrive with `state=0x0`, because Tk strips the Control and Alt bits.
- **Tk's binding matcher also treats `0x10` as Alt on win32.** Real keyboards did not
  produce `0x10` in the measurement, so the contract decodes only `0x20000` as Alt.
- **aqua is not verified live.** Its column is derived from Tk's macOS sources.
- **x11 depends on the user's modifier mapping.** Mod1 is Alt only under the usual
  xmodmap assignment.

### Unknown vs. absent modifier information

| Value | Meaning | Gating |
|---|---|---|
| `KeybindingRuntimeContext.modifiers = None` | This runtime path supplies no modifier information (legacy contexts) | none |
| `UNKNOWN_MODIFIERS` | An event exists, but its `state` is missing or not an `int` | fail-closed |
| `KeyModifiers(...)` | State decoded | rule below |

`modifiers_from_event(event) -> KeyModifiers | UnknownModifiers` never returns `None`.
`UNKNOWN_MODIFIERS` has no truth value. Always compare it with `is`.

## Sequence syntax (keyboard shortcuts only)

`parse_sequence()` supports exactly the keyboard-shortcut subset of Tk's syntax:

- a single character (`"a"`, `"+"`)
- `<[Modifier-]*[KeyPress-|Key-]detail>` with one event

Single-character details are normalised to keysym names, so `<Control-,>` equals
`<Control-comma>`. Keysyms stay case-sensitive: `a` and `A` are different keys.

The parser rejects the following with `ValueError`:

- virtual events
- mouse and other event types
- `KeyRelease`
- detail-less `<KeyPress>`
- `Double` / `Triple` / `Any` / `Lock` / `Extended`
- button modifiers
- multi-event sequences

Other kinds of GUI semantics need their own contract.

### Modifier tokens per backend

| Token | win32 | aqua | x11 |
|---|---|---|---|
| `Control` | control | control | control |
| `Shift` | shift | shift | shift |
| `Alt` | alt | rejected | alt |
| `Command` | rejected | command | rejected |
| `Mod1` / `M1` | rejected | command | alt |
| `Option`, `Mod2` / `M2` | rejected | alt | rejected |
| `Meta` / `M` | rejected | rejected | rejected |

"Rejected" means the contract defines no meaning for that token on that backend, so
binding it raises `ValueError` instead of guessing.

On win32, `<Command-a>` and `<Mod1-a>` match only `state=0x8`, which is the NumLock
bit (measured with Tk 8.6.15). So `Command` is **not** Control on Windows.

`binding_signature(sequence, backend)` returns the event type, keysym and semantic
modifiers. It is the only accepted way to compare two bindings.

## Runtime gating (`evaluate_binding` / `KeybindingRegistry.evaluate_runtime`)

The checks run in this order:

1. mode
2. offline
3. text-input focus
4. dialog priority
5. modifiers

The modifier rule:

- `modifiers is None`: no check (legacy behaviour).
- `allow_modifiers=True`: additional, undeclared shortcut modifiers are allowed.
- Otherwise:
  - `UNKNOWN_MODIFIERS` gives `(False, "modifier-unknown")`. This applies even to
    bindings that declare modifiers, because Tk also matches `<Control-a>` while
    extra modifiers are held.
  - A held shortcut modifier that the sequence does not declare gives
    `(False, "modifier-held")`.

| Event | Binding | Result (`allow_modifiers=False`) |
|---|---|---|
| `a` | `a` | allowed |
| `Shift+a` | `a` | allowed |
| `Ctrl+a` | `a` | blocked |
| `Alt+a` | `a` | blocked |
| `Cmd+a` | `a` | blocked |
| `Ctrl+Shift+a` | `a` | blocked |
| `Ctrl+a` | `<Control-a>` | allowed |
| `Alt+a` | `<Alt-a>` | allowed |
| `Ctrl+Alt+a` | `<Control-a>` | blocked |
| NumLock+`a` (win32) | `a` | allowed |

`derive_active_mode()` defines the mode priority: offline, then dialog, then text
input (editor), then the app's base mode. The binder and the conflict analysis both
use this function.

## Conflicts

Two definitions **conflict** if both conditions hold:

- They have the same `binding_signature`.
- At least one runtime context exists in which both would be allowed to execute.

The contexts considered cover every dispatch criterion:

- every relevant base mode
- the offline, dialog and text-input flags
- the modifier state: exactly the declared modifiers, one additional shortcut
  modifier, or unknown

Each context is judged by `evaluate_binding` itself, so the analysis cannot drift from
the runtime rules. Use `KeybindingRegistry.find_conflicts(backend)` or
`find_conflicts(definitions, backend)`. The older `KeybindingRegistry.conflicts()`
compares raw strings and is deprecated.

## `WindowShortcutBinder`

- **Scope and bindtag:** one binder serves exactly one toplevel and binds on that
  window's bindtag (`window.bind`). Widgets in other toplevels, such as popups, do not
  see its shortcuts. `bind_all` is not equivalent and is not used. A cross-window
  shortcut scope would be a separate contract.
- **Mode provider:** `mode_provider` is a generic binder feature. It returns the app's
  base mode (default `UI_MODE_GLOBAL`) and should come from domain state, not from
  widget visibility.
- **Multiplexing:**
  - Tk keeps one script per (tag, sequence) and silently replaces it on a second
    `bind`. The binder therefore binds each signature once and dispatches to the first
    allowed definition in registration order.
  - Overlapping definitions with the same signature are rejected at bind time. So are
    sequences outside the contract and unknown intents.
- **Propagation:** a blocked shortcut returns `None`, never `"break"`, so later
  bindtags still see the event. An example is a global `<Alt-KeyPress>` menu handler
  on `all`. An executed shortcut returns its handler's result.
- **Observability:** `on_dispatch(intent, success=...)` runs after every handler
  invocation.

## Rule for apps

This rule is enforced by `bw_gui.testing.tk_state_guard.find_offenders(repo / "app")` in every consumer's test suite.

- **No raw `event.state`:** never write `event.state & <mask>` or
  `getattr(event, "state") & ...`. Use the binder, or `modifiers_from_event()` where a
  handler genuinely needs the modifier state (for example Ctrl+click semantics).
- **No local sequence helpers:** never parse, normalise or compare sequence strings
  yourself.
- **No `bind_all` for shortcuts.**

## Testing

- **Headless:** `tests/test_shortcut_binder_headless.py` uses a window test double. It
  covers gating, multiplexing and return values without opening windows.
- **Real Tk key routing (opt-in):** tests that route real synthetic key events need
  the OS keyboard focus. They are opt-in via `TK_FOCUS_TESTS=1` and should be run while
  nobody is typing.
- **Consumer repos:** import the `bw_gui.testing.background_windows` hooks in
  `tests/conftest.py`. Every mapped Tk test window then immediately returns the OS
  foreground to the developer's window.
- **Live keyboard (opt-in):** `BW_GUI_LIVE_KEYBOARD=1 pytest -m live_keyboard
  tests/live` re-measures the win32 masks with real key strokes.
