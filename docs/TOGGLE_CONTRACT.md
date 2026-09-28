# Toggle Contract (Checkbox & Switch)

bw-gui offers exactly two binary controls: **Checkbox** and **Switch**. They look
different because they *mean* different things:

- **Checkbox = staged selection.** Its business effect happens only when the user
  performs a submit action.
- **Switch = immediate effect.** Its business effect happens on the user
  interaction itself.

This contract applies to **every binary interactive control**, including menu entries.
Their rendering may differ per surface (form widget, custom menu, native menu); their
classification does not.

Modules (see "Surfaces" below for status):

| Module | Responsibility |
|---|---|
| `bw_gui.widgets.toggles` | `Checkbox`, `Switch` (form widgets) |
| `bw_gui.theming._toggle_assets` | private: role masks → themed PNG image data |
| `bw_gui.theming._toggle_styles` | private: ttk elements, state specs, image lifecycle |
| `bw_gui.menu` | `MenuItem(type="switch" / "checkbox")`, native-menu helpers |
| `bw_gui.testing.checkbutton_guard` | AST guard against raw Tk/ttk checkbuttons in consumer apps |

## Terms

- **Business effect**: the change the control represents becomes effective in the
  running application (the main table re-filters, a mode switches, people are marked
  finished, ...).
- **Runtime/model state**: in-memory app state. A business effect usually shows up here.
- **Persistence**: writing to disk/config. Independent of effect timing. "Immediate
  effect" does **not** mean "saved immediately".
- **Submit action**: an explicit user action that commits or executes the currently
  selected values. Defined by this role, not by a list of button captions.
- **Local presentation state**: state *within the same staged form*: selecting or
  deselecting other controls, enabling/disabling controls, a dialog-internal preview,
  filtering the choices shown in the form. Not a business effect.
- **UI state vs. domain state**: a widget's `variable` is UI state. Domain state lives
  in the consumer.

## Rules

| # | Rule | Enforced by |
|---|---|---|
| R1 | A Switch's business effect happens on user interaction and **never depends on a later submit**. A form may mix Switches (immediate) and Checkboxes (effective on submit); only the Switch's own effect must not wait for the submit. | API (`on_change` is required) + review |
| R2 | A Checkbox has **no business effect before submit**. Local presentation state may change immediately. | Convention |
| R3 | `Checkbox.on_select` changes local presentation state only. It never commits, persists or otherwise applies the represented action. | Convention |
| R4 | The widget does not invoke its own `on_change`/`on_select` callback as a consequence of a programmatic `variable.set` or `set_mixed`. External observers and traces are outside the widget's callback contract. | API (tested) |
| R5 | Business effects are never attached to `variable` traces. Traces observe UI state. | Convention |
| R6 | Consumer code uses no raw Tk/ttk checkbuttons and no native menu checkbuttons. Binary menu entries go through bw-gui's menu abstraction. | Guard |
| R7 | Mixed is always derived by the consumer from domain state. | Convention + API (the widget never computes mixed) |

"Convention" rules are architecture rules: code review enforces them, the API cannot.

### Why two controls

- A switch *is* a toggle button. Requiring a submit button after flipping it confuses
  users, because it is not what they expect.
- The visual cue differs: "on" implies instant effect, a checkmark only indicates
  selection. Users therefore expect an immediate change from a switch but not from a
  checkbox.
- A checkbox plus submit lets users review their settings before they commit, which
  prevents accidental activation.
- Checkboxes suit batches: the system can apply many changes at once instead of one
  by one.

**UX heuristic, not a rule:** if users often change a *batch* of settings, checkboxes
plus submit tend to save time; if they often change only a *few single* settings,
switches tend to work better. Use this when designing a flow. Effect timing (R1/R2)
always wins.

### Classifying a control

Ask: **when does the control's relevant business effect happen?** Not: when is some
local variable written or read.

| Example | Why | Control |
|---|---|---|
| "Select all" in an export dialog ticks all entries immediately | ticking is local presentation; exporting only happens on "Export" | Checkbox |
| "Include solutions" immediately updates a page-count preview in the same dialog | the preview is local; nothing is exported or saved | Checkbox |
| A filter-panel entry immediately re-filters the app's main view | the filtering *is* the effect | Switch |
| A menu entry that toggles a view mode when clicked | menu entries act on click | Switch |
| A menu entry whose value is only read by a later "Run" action | staged | Checkbox |

Filter lists whose result is the app's main view and that apply immediately are
Switches, without exception.

## API

```python
Checkbox(parent, *, text: str, variable: BooleanVar,
         on_select: Callable[[bool], None] | None = None,
         mixed: bool = False, mixed_click_target: bool = True)

Switch(parent, *, text: str, variable: BooleanVar,
       on_change: Callable[[bool], None],             # required
       mixed: bool = False, mixed_click_target: bool = False)

widget.set_mixed(value: bool) -> None
widget.is_mixed() -> bool
```

- The callback always receives the **requested bool**.
- `command` is reserved: passing it to the constructor or to `configure()` raises
  `TypeError`. There is no argument-less Tk command.
- `variable` must be a `BooleanVar`, `text` must be non-empty.

### Callback timing and mechanism

Callbacks fire only on **user interaction**: click, Space, or `invoke()` (which counts
as simulated user interaction).

The internal `ttk.Checkbutton` is bound to a **widget-owned display variable**, never
to the consumer `variable`. A single write trace on the consumer `variable` mirrors
its value into the display variable and re-renders; it never fires a callback. The
mixed flag lives in Python and is re-asserted as ttk's `alternate` state after every
display write (ttk clears `alternate` whenever its variable changes).

Invariant: outside the moment between Tk's internal toggle and the widget's handler,
**display variable == consumer `variable`**.

### Programmatic changes

`variable.set(...)` changes the consumer variable. External traces fire as usual (not
covered by this contract), the display follows, and the widget's own callback does
**not** fire. This includes calls made from inside the callback. `set_mixed(...)` never
fires the callback either.

### Mixed state

- While `mixed=True`, the value of `variable` is **irrelevant** for the visual and
  aggregate meaning; the display shows the mixed indicator.
- `set_mixed(False)` leaves `variable` untouched; the display then shows its value.
- `variable.set(...)` while mixed changes the value, **keeps** `mixed=True` and keeps
  the mixed display.
- No automatic synchronisation in either direction; the consumer coordinates both,
  derived from domain state.
- A click while mixed resolves to `mixed_click_target` (Switch default `False`,
  Checkbox default `True`).

Reference case: Korrektor's "everyone finished" is a mixed Switch
(`mixed_click_target=False`): mixed when some but not all people are finished; a click
from mixed or "all" requests `False` (reset), a click from "none" requests `True`.

### Click sequence

When the handler runs, Tk has already toggled the **display variable**; the consumer
`variable` is untouched.

1. Re-entrancy check (next section).
2. `prev_value = variable.get()`, `prev_mixed = mixed`.
3. `requested = mixed_click_target if prev_mixed else not prev_value`, computed from
   the consumer variable, never from the display variable Tk flipped.
4. `mixed = False`.
5. `variable.set(requested)`: optimistic set. External traces see only `requested`;
   the display follows and re-renders.
6. `callback(requested)` with the re-entrancy flag set (skipped when `on_select` is
   `None`).
7. Clear the flag (`finally`).

### Re-entrancy

A re-entrant invocation (a click or `invoke()` while the widget's own callback is
running) must leave the display variable, the mixed state and the consumer variable
exactly as they were before it. It must not cause a partial state transition and must
not invoke the callback recursively.

Tk toggles the display variable before the handler runs, so the invocation cannot be
prevented; it is neutralised: the handler resets the display variable to
`variable.get()`, re-renders (restoring `alternate` from the unchanged mixed flag) and
returns without touching `variable`, the mixed flag or the callback.

### Exceptions

If the callback raises, the widget restores `variable.set(prev_value)` and the previous
mixed flag, re-renders and **re-raises**. The rollback is an ordinary programmatic
change (external traces see it, the widget callback does not fire). The exception ends
up in Tk's `report_callback_exception`, like every Tk callback. The rollback also
applies when the callback had already changed `variable` itself.

A pending/error mechanism for asynchronous effects is out of scope. A consumer whose
effect fails later resets programmatically with `variable.set(old)`.

## Visual states

States considered: `disabled`, `alternate` (mixed), `selected`, `active`, `pressed`,
`focus`. **`pressed` is intentionally rendered identically to `active`** and is not a
separate visual state.

- Shape: `alternate` → mixed, else `selected` → on, else off.
- `disabled` wins over every overlay: the muted shape, `active`/`pressed`/`focus`
  ignored.
- Overlay (not disabled): hover if `active` or `pressed`, focus ring if `focus`, both
  if both, else rest.

| disabled | alternate | selected | active or pressed | focus | Image |
|---|---|---|---|---|---|
| 1 | 1 | any | any | any | mixed, muted |
| 1 | 0 | 1 | any | any | on, muted |
| 1 | 0 | 0 | any | any | off, muted |
| 0 | 1 | any | 0/1 | 0/1 | mixed + overlay |
| 0 | 0 | 1 | 0/1 | 0/1 | on + overlay |
| 0 | 0 | 0 | 0/1 | 0/1 | off + overlay |

15 images per control. The ttk state specs are generated from this table, so priority
never depends on code order; all 64 state combinations are tested.

State is never conveyed by colour alone: check mark, dash and knob position differ in
shape.

## Scaling

Density `f = tk_scaling / (96 / 72)` (relative to 96 DPI). Supported densities are
exactly **1.0, 1.25, 1.5, 1.75, 2.0**; assets exist for each, nothing is scaled at
runtime. `f` is clamped to `[1.0, 2.0]` and mapped to the nearest supported density,
ties rounding up (1.125 → 1.25, 1.375 → 1.5). Above 200 % the indicator stays at the
2.0 asset.

The density is evaluated on every `configure_ttk_theme` call. There is no DPI
listener: after changing `tk scaling`, call `configure_ttk_theme` (normally via
`apply_theme`).

## Accessibility

- **Native ttk interaction** is retained because the widgets *are*
  `ttk.Checkbutton`s: Tab focus traversal, Space activation, disabled state. Tested.
- **Screen readers**: Tk 8.6 on Windows exposes no usable screen-reader semantics for
  ttk widgets, before and after this change. Not tested, out of scope; the image-based
  indicator neither improves nor worsens it.
- **Visual**: indicator contrast ≥ 3:1 for every registered theme **and every theme
  intensity** (boundary against `bg_main`/`bg_surface`, mark/knob against its fill),
  state not by colour alone, visible focus ring, mandatory label that is part of the
  click target. Tested. At low intensities ("dezent", "mittel") the accent alone falls
  below 3:1; a **contrast guard** then shifts the indicator colours in 5 % steps just far
  enough (towards `fg_primary`, marks towards black/white), so toggles may look slightly
  stronger than the rest of the UI there. At the default intensity nothing is shifted.
  Disabled states are exempt, as in WCAG.

## Settings dialog: `live_apply`, Cancel and persistence

- `SettingsFieldSpec.live_apply=True` means: the value takes effect in the running app
  immediately, by being passed to `on_live_apply` (runtime state). It says nothing
  about persistence. Bool fields with `live_apply=True` render as a Switch, with
  `live_apply=False` as a Checkbox.
- `on_commit` is the **configuration-commit interface**: it receives the resulting
  configuration; the consumer decides how and when to persist it.
- **Cancel** (a deliberate settings-dialog decision): staged values revert to their
  initial values, while live-applied values retain their current runtime values. If at
  least one live value changed, the consumer receives this resulting configuration
  (`initial_values` overlaid with the current live values) through `on_commit`.
  `result` stays `None`, because the staged changes were cancelled. This keeps the
  persisted configuration from silently contradicting a runtime state that is already
  in effect.
- Save/Apply behave as before.

## Surfaces

| Surface | Checkbox | Switch |
|---|---|---|
| Form widget | `Checkbox(...)` | `Switch(...)` |
| Custom menu bar | `MenuItem(type="checkbox", on_toggle=...)` | `MenuItem(type="switch", on_toggle=...)` |
| Native `tk.Menu` | `add_menu_checkbox(...)` | `add_menu_switch(...)` |

Menu entries receive the requested bool like the widgets and support `mixed`.

## Guard

`bw_gui.testing.checkbutton_guard` scans consumer app sources (not bw-gui itself) and
reports raw Tk/ttk checkbuttons and native menu checkbuttons. The exact set of detected
and deliberately undetected forms is documented in the guard's module docstring.
