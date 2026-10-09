# Keybinding Contract

bw-gui is the only place that understands Tk's keyboard semantics. Consumer apps
declare *which* key should trigger *which* intent in *which* UI mode. They never see
Tk binding strings (`"<Control-z>"`), Tk's `"break"`, `keysym`/`char`/`event.state`
or Tk event objects, and they never decide whether a held modifier blocks a shortcut.

If an app needs Tk keyboard knowledge that this contract does not offer, the contract
is incomplete. Extend it here instead of writing a local helper.

| Module | Responsibility |
|---|---|
| `contracts/key_spec.py` | `KeySpec`, `Key`, `Mod`, notation (`parse`/`str`), `KeyIdentity`, **`matches`**, `overlaps` |
| `contracts/key_event.py` | `classify_key`: the only interpretation of `keysym`/`char`/`state` → `KeyEvent` + `KeyIdentity` |
| `contracts/key_modifiers.py` | Tk backends, `KeyModifiers`, `event.state` decoding (masks below) |
| `contracts/events.py` | `EventResult` (`HANDLED`/`NOT_HANDLED`), `coerce_result` |
| `contracts/subscription.py` | `Subscription` lifecycle handle (`SUBSCRIPTION_CONTRACT.md`) |
| `contracts/keybinding.py`, `keybinding_conflicts.py` | `KeyBindingDefinition`, gating, registry, model-A conflicts |
| `runtime/_key_channel.py` | one catch-all per bindtag, gesture slot |
| `runtime/key_router.py` | owner of the `all` tag, roles, `TK_DEFAULT` wrapping, `verify()` |
| `runtime/shortcuts.py` | `WindowShortcutBinder`, `ApplicationShortcutBinder` |
| `runtime/widget_keys.py` | `WidgetShortcutBinder`, `on_key` |
| `runtime/text_input.py` | text-input context (`accepts_text_input`, `register_text_input`) |
| `runtime/_tk_identity.py` | per-interpreter state on the `tkinter.Tk` root |

## `KeySpec`: the only public shortcut syntax

- **Named keys:** `KeySpec(Key.ESCAPE)`, `KeySpec(Key.TAB, {Mod.SHIFT})`.
- **Characters:** `KeySpec.char("z", {Mod.CTRL})`.
  - The character is exactly one printable, non-whitespace character as the **current
    keyboard layout** produces it, Shift included (`"Z"`).
  - `Mod.SHIFT` is invalid for characters.
- **Whitespace keys are named keys only:** `Key.SPACE`, `Key.TAB`, `Key.ENTER`. `char(" ")` is a `ValueError`.
- **Exact modifiers:** `modifiers` is exact. `char("z", {CTRL})` matches Ctrl+Z, not Ctrl+Shift+Z and not Ctrl+Alt+Z.
  - Extra held modifiers are allowed only through the explicit `tolerate` set (`modifiers ∩ tolerate = ∅`).
  - Lock keys (NumLock, CapsLock) never take part.
- **Shift tolerance on a character:** bind several specs, e.g. `[char("z", {CTRL}), char("Z", {CTRL})]`. Several specs on one binding are any-of alternatives.
- **Logical keys:** matching uses the layout-produced character (Tk `keysym`), never a physical keycode. On another layout (e.g. Cyrillic) the same physical key produces another character and `char("z", …)` does not match there. This is intended.
- **Backend check:** `Mod.CMD` exists only on aqua; binding it on win32/x11 raises `ValueError`.

### Notation (`KeySpec.parse` / `str(spec)`)

```
spec   := mods key [" (tolerate: " Mod (", " Mod)* ")"]
mods   := (Mod "+")*            Mod ∈ {Ctrl, Alt, Shift, Cmd}, case-insensitive
```

- **Parsing:** known modifier prefixes are peeled from the left. The rest up to the first space is the key token:
  - **(a)** a name (`Space`, `Escape`, `Enter`, `Tab`, `Up`, `PageDown`, `F1`–`F12`, …; case-insensitive)
  - **(b)** one *letter*, case-insensitive. `Shift` folds into it: `"Ctrl+Shift+Z"` = `char("Z", {CTRL})`, and `"Ctrl+Z"` = `"Ctrl+z"` = `char("z", {CTRL})`.
  - **(c)** any other printable character, taken literally: `"Ctrl++"` = `char("+", {CTRL})`, `"€"`. `Shift` is invalid here, so write the produced character (`"!"`, not `"Shift+1"`).
- **Letter:** a character with a lossless one-character upper/lower mapping. `ß` (→ `SS`) and `µ` (→ Greek `Μ` → `μ`) fall under rule (c).
- **Tolerate suffix:**
  - One space separates it. Whitespace around `:` and `,` is allowed, names are case-insensitive.
  - Errors: an empty list, a duplicate, an overlap with `modifiers`, `Shift` on a character, an unknown name, or text after `)`.
- **Canonical output:**
  - Fixed order `Ctrl+Alt+Shift+Cmd`.
  - Letters are upper-case, and `Shift+` appears exactly when the character is upper-case.
  - Tolerate suffix: `" (tolerate: Ctrl, Shift)"`.
- **Roundtrip:** `KeySpec.parse(str(s)) == s` for every valid spec.

## Two levels: `KeyIdentity.character` vs. `KeyEvent.text`

| | `KeyIdentity.character` (internal) | `KeyEvent.text` (public) |
|---|---|---|
| meaning | logical, layout-based key/character | character actually typed |
| used for | shortcut matching, menu mnemonics | type-ahead, filtering |
| Ctrl+Z / Alt+Z | `"z"` | `None` |
| AltGr character (`@`) | `"@"` | `"@"` |
| whitespace keys | never (named key) | `" "` for Space |

`text` rule:

1. No character, or `Cc`/`Cf` → `None`.
2. A printable character with no shortcut modifier → the character.
3. A printable character with shortcut modifiers → `None`, except for the per-backend exception table. The table currently holds only aqua Option, which is not verified live. For those combinations the modifier is removed from `KeyEvent.modifiers` and the identity.

On win32, AltGr characters arrive with Ctrl/Alt already stripped by Tk (measured, `KEYBINDING_AUDIT.md`), so rule 2 applies. There is **no** `state == 0` heuristic.

## Architecture: one semantic matching layer

**Channels.** Every bw-gui-owned bindtag carries exactly **one** keyboard catch-all (`<KeyPress>`). Its script is a constant Tcl line calling a registered dispatcher, and it `break`s when the dispatcher returns `handled`. No concrete shortcut is ever registered with Tk, so Tk's specificity rule has nothing to decide. Runtime and conflict analysis use the same `matches`.

**Ownership.** A tag that carries a bw-gui channel must not carry foreign keyboard bindings:

- Creating a channel next to one raises `ValueError`.
- `router.verify()` reports later additions on `all`.
- Non-keyboard bindings (e.g. `<Configure>`) may coexist.

**Dispatch channels.** For every semantic dispatch channel (keyboard, wheel, click, drag, lifecycle) there is one central bw-gui dispatcher.

- Internal Tk bindings may use extra raw sequences to recognise gestures (double press for `bind_click(count=2)`).
- Consumers never see Tk syntax, and no shortcut/role decision is delegated to Tk's matcher.

### Bindtag order (binding)

```
widget -> bwkeys:<path> -> Class -> bwkeys-after:<path> -> toplevel path -> all
```

| Tag | Content |
|---|---|
| `bwkeys:<path>` | `WidgetShortcutBinder` definitions, then `on_key(phase="before")` |
| Class | native Tk bindings (text insertion, native navigation) |
| `bwkeys-after:<path>` | `on_key(phase="after")`; only exists when registered |
| toplevel path | `WindowShortcutBinder` (decision 36); popup overrides live here |
| `all` | router: `OBSERVER` → `APP_SHORTCUT` → `MENU_MNEMONIC` → wrapped Tk default |

- **Why the toplevel path:** Tk adds it to the bindtags of every current and future descendant. A separate `bwwindow:*` tag would have to be inserted into every widget, including widgets created later, and Tk offers no hook for that.
- **Effect on popups:** a binding on a popup's toplevel runs before `all`, so it beats `ApplicationShortcutBinder`. The main window's `WindowShortcutBinder` never sees popup events.

### The `all` router (`runtime/key_router.py`)

- **Ownership:** exactly one router per interpreter (decision 31).
  - It is stored as an attribute of the interpreter's `tkinter.Tk` root.
  - It is not kept in a global map keyed by `root.tk`, because `_tkinter.tkapp` is not weak-referenceable.
  - `interpreter_root(widget)` is the only place relying on tkinter internals.
  - Several toplevels of one interpreter resolve to the same router; several `Tk()` instances get separate routers.
  - Root destroy drops everything.
- **Bootstrap (step 2-0):** `TkRootHost` / `create_root()` installs the router **directly after `Tk()`**, before any consumer code runs. `TkRootHost.create(build=...)` runs consumer code strictly afterwards. Everything on `all` at installation time is therefore by definition a Tk default.
- **`TK_DEFAULT` wrapping (decision 32):**
  - Every keyboard-press sequence and every virtual event found on `all` gets the script `prefix + "\n" + original`.
    - The original is read via `bind all S` as one opaque Tcl string. It includes `+`-appended parts and is never parsed, escaped or formatted in Python.
    - It stays at the top level of the binding script, so Tk's `%`-substitution and Tcl parsing are unchanged.
  - Tk's own matcher keeps choosing which binding runs. The dispatcher runs once per key press, and only on `NOT_HANDLED` does the original of exactly that binding follow.
  - Key-release defaults are not touched.
  - Virtual events without key information (`%K` = `??`) produce an identity without key, so only observers and the original run.
  - `uninstall()` restores every original byte-for-byte.
  - Tk 8.6 / win32 defaults found by the spike: `<<PrevWindow>>`, `<<NextWindow>>`, `<Key-F10>`, `<Alt-Key>`, `<Key-Alt_L/R>` (plus releases).
- **Roles:**
  - Observers always run and cannot consume. In the other roles, the first `HANDLED` ends processing.
  - `APP_SHORTCUT` before `MENU_MNEMONIC` reproduces today's outcome: a concrete app `Alt+Z` beat the generic menu `<Alt-KeyPress>` by Tk specificity. It is now guaranteed.
  - The mnemonic matches `KeyIdentity.character`, never `KeyEvent.text` (which is `None` for Alt+Z).
- **Exceptions:** handler errors are reported through `report_callback_exception` and end the event's processing. A failing observer does not end the observer phase.

### Binders

`WindowShortcutBinder(window, ...)`, `ApplicationShortcutBinder(root, ...)` and `WidgetShortcutBinder(widget, ...)` share one API:

```
bind(keys, handler, *, binding_id, intent, modes=(GLOBAL,), allow_when_text_input=False,
     allow_when_offline=True, description="", applies_when=None) -> ShortcutRegistration
```

- **Handler:** `handler(KeyEvent) -> EventResult | None`.
  - `None` means `NOT_HANDLED` (propagates). `HANDLED` makes bw-gui stop the Tk event.
  - Returning a string (e.g. a legacy `"break"`) raises `TypeError`.
- **Constructor hooks:** `registry`, `hsm_contract.validate_intent`, `is_text_input` (transitional override), `dialog_open`, `offline`, `mode_provider` (base mode from domain state), `on_dispatch(intent, success=...)`, `backend`.
- **Gating order:** mode → offline → text input → dialog (`evaluate_binding`). Modifiers are not part of gating; exact matching decides them.
- **Model A (decision 21):**
  - Per scope there is at most one applicable definition per key event and runtime context.
  - The static check rejects overlaps (`overlaps()` × every gating context), across all binders on the same toplevel and across all application binders.
  - `applies_when` never makes definitions disjoint; definitions differing only by a predicate must be merged.
  - At runtime, `applies_when=False` → the handler does not run, `on_dispatch` is not called, the result is `NOT_HANDLED` and the event propagates. No further definition is searched.
- **Lifecycle:**
  - `bind` returns a `ShortcutRegistration` (`Subscription` + `.definition`).
  - `dispose()` removes everything. It runs automatically when the toplevel/widget is destroyed.

### `on_key(widget, handler, *, phase="before" | "after")`

- **Precedence:** if a widget shortcut executed in `bwkeys:<path>`, `on_key` is not called for that event.
- **`before`:** runs ahead of the native class bindings. In a text widget the character is not inserted yet.
- **`after`:** means *after successful propagation through every preceding bindtag*. If anything before consumed the event (a shortcut or `before` `HANDLED`, or a native class binding breaking), Tk never reaches `bwkeys-after:<path>`.
- **`HANDLED`:** stops the event. In `before` this also skips the class bindings, `after`, the toplevel and `all`.
- **Completion order:**
  1. Popup navigation as widget shortcuts with `applies_when=popup_open` → `HANDLED`.
  2. Filtering in `after` → `NOT_HANDLED`.
  3. Pure type-ahead in `before` → `HANDLED` on a hit.

## Text-input context (`runtime/text_input.py`)

A widget accepts text input when a key without shortcut modifier would insert or delete text in it.

- **Closed Tk table:**
  - Entry/Spinbox (tk and ttk) unless `disabled`/`readonly`
  - `ttk.Combobox` unless `readonly`
  - `Text` when `normal`
- **Custom widgets:** only via `bw_accepts_text_input()` or `register_text_input(widget, predicate)`. Any other widget is never text input.
- **Which widget:** the event widget, else the focus widget; there is no ancestor walk.
- **Deliberate change:** a read-only combobox and a disabled entry are no text input any more.

## Modifier decoding (`contracts/key_modifiers.py`)

`KeyModifiers(shift, control, alt, command)` is semantic: lock keys and mouse buttons are not represented. The modifier bits depend on the Tk backend (`tk windowingsystem`), not on the OS.

| Modifier | win32 | aqua | x11 |
|---|---|---|---|
| Shift | `0x1` | `0x1` | `0x1` |
| Control | `0x4` | `0x4` | `0x4` |
| Alt / Option | `0x20000` | `0x10` (Option) | `0x8` (Mod1) |
| Command | – | `0x8` (Mod1) | – |
| NumLock (ignored) | `0x8` | – | usually `0x10` (Mod2) |

- **win32** is verified live (Windows 11, Tk 8.6.15, `tests/live/`). NumLock adds `0x8` to every state. Code reading `0x8` as Alt (X11 habit) breaks as soon as NumLock is on. That is the trap this contract removes.
- **AltGr / Ctrl+Alt** combinations that produce a character arrive with `state=0x0` on win32.
- **aqua** is derived from Tk's sources and not verified live.
- **x11** depends on the user's modifier mapping.
- **Undecodable states** (a missing or non-integer `state`) become `UNKNOWN_MODIFIERS`, so no `KeySpec` matches (fail-closed).

## Rule for apps

- No Tk binding strings and no `return "break"` in app code. Use `KeySpec` and `EventResult`.
- No keyboard `bind`/`bind_all` outside bw-gui. Use the binders and `on_key`.
- No `event.state`, `keysym` or `char` interpretation.
- Guards in `bw_gui.testing` enforce this; see each guard's docstring for what it detects and what it deliberately misses. `find_offenders(...) == {}` means "no known statically detectable violation", not a formal proof.

## Testing

- **Headless:** `tests/test_shortcut_binders.py`, `tests/test_key_router.py`, `tests/test_key_spec.py` and `tests/test_key_event.py` feed the dispatcher entry directly, so no keyboard focus is needed.
  - The `TK_DEFAULT` wrapping is verified with a deliberately nasty fake default on a virtual event. Virtual events reach widgets without focus.
- **Real Tk key routing (opt-in):** `tests/test_shortcut_binder_tk.py` with `TK_FOCUS_TESTS=1`.
- **Consumer repos:** import the `bw_gui.testing.background_windows` hooks in `tests/conftest.py`.
- **Live keyboard (opt-in):** `BW_GUI_LIVE_KEYBOARD=1 pytest -m live_keyboard tests/live`.
