# Theme Contract

This document defines the stable token contract returned by `bw_gui.theming.get_theme(...)`.

> **Ownership rule:** bw-gui is the sole authority on colour values.  Consumer
> programs must not call `get_theme()` to extract raw hex values, construct colour
> strings manually, or maintain their own colour variables.  Use the utility
> functions documented here (`theme_canvas`, `tinted_color`, `tinted_foreground`,
> `icon_button`) instead.  See [ARCHITECTURE.md](ARCHITECTURE.md) for the full
> set of principles.

## Goal

- Keep one shared theme registry for all consumer apps.
- Support both Kursplaner and Blattwerk theme families everywhere.
- Provide deterministic fallback and alias tokens to avoid app-specific breakage.

## Core Keys

Every registered theme must define or derive these base keys:

- `bg_main`
- `bg_surface`
- `fg_primary`
- `fg_muted`
- `accent`
- `accent_hover`
- `accent_soft`
- `danger`
- `border`

## Guaranteed Contract Keys

`get_theme(...)` guarantees all keys listed by `theme_contract_keys()`.

This currently includes:

- Base and structure: `label`, `bg_panel`, `panel_strong`, `secondary`, `secondary_soft`
- Selection: `selection_bg`, `selection_fg`
- State colors: `success`, `success_hover`, `success_soft`, `warning`, `warning_hover`, `warning_soft`, `info`, `info_hover`, `info_soft`, `danger_hover`, `danger_soft`
- Domain helper: `hospitation`, `hospitation_hover`, `hospitation_soft`, `fg_on_hospitation`
- Foreground helpers: `button_fg`, `fg_on_accent`, `fg_on_success`, `fg_on_warning`, `fg_on_info`, `fg_on_danger`, `fg_on_hospitation`
- Focus: `focus_ring`
- Alias family: `error`, `error_hover`, `error_soft`, `fg_on_error`

Themes that do not define `info` get sky blue (`#0284C7` on light, `#38BDF8` on dark
themes); `info_hover`, `info_soft` and `fg_on_info` derive from it like the other
state colours, and the intensity levels mute them the same way.

## Unknown tokens

`tinted_color` (and everything built on it: `tinted_foreground`, `theme_label_tinted`,
`theme_text_tinted`, `canvas_tinted_fill`, `icon_button`, CardBoard row tints) accepts a
`#RRGGBB` literal or a token of the active theme for both the tint and `base_token`.
Any other name raises `ValueError`.  Previously it was blended as if it were a colour and
produced an arbitrary grey, so a token missing from some themes went unnoticed.

## Alias Rules

The following aliases are resolved for every theme:

- `error` -> `danger`
- `error_hover` -> `danger_hover`
- `error_soft` -> `danger_soft`
- `fg_on_error` -> `fg_on_danger`

## Domain Colours

Colours for domain-specific lesson types (Hospitation, Ausfall, Lzk) are **not**
part of the bw-gui token contract.  They are computed at switch time by the
consumer program using `tinted_color` and `tinted_foreground`:

```python
from bw_gui.theming import tinted_color, tinted_foreground

hospitation    = tinted_color("#7C3AED", degree=0.70, base_token="bg_panel")
fg_on_hosp     = tinted_foreground("#7C3AED", degree=0.70, base_token="bg_panel")
column_lzk_bg  = tinted_color("success_soft", degree=0.72, base_token="panel_strong")
```

The seed colour (`"#7C3AED"`) is domain knowledge owned by the consumer; the
colour math stays in bw-gui.  This pattern works automatically across all 15
registered themes, including dark themes, with no branching in consumer code.

## Classic Tk widgets

**No widget keeps Tk's system colours.** Classic Tk widgets (`ui.Frame`, `ui.PanedWindow`, `ui.Menu`, `ui.Label` …) have no ttk style; on their own they show the compiled-in system colours (on Windows `SystemButtonFace`, `SystemWindow` …). `theming/_classic_widgets.py` is the single source for their colours:

- `CLASSIC_WIDGET_TOKENS` maps each Tk class name (as `winfo_class()` reports it, e.g. `Panedwindow`, `Labelframe`) and option (Tk database name) to a theme token. `CLASSIC_WIDGET_CONSTANTS` holds theme-independent options of the same widgets (flat splitter handle).
- `configure_ttk_theme` applies the table in the style phase, before the listeners: it writes it into Tk's option database (widgets created later start themed) and walks the existing widget tree of the interpreter (the root counts as a `Toplevel`). An option that still holds Tk's compiled-in default, or the value the table gave it for the previous theme, takes the new value. Colours set explicitly stay, and consumer listeners run afterwards.
- `theme_canvas`, `theme_text` and `theme_listbox` build on the same table (`classic_widget_colors`) and add only their 1-px border, so they never disagree with it. The bw-gui `Scrollbar` takes its non-win32 colours from the table too.
- Guard: `tests/test_classic_widget_theme.py` discovers every classic widget class of `tkinter`, fails for a class missing from the table, checks every table option against the theme and, on win32, fails for any colour option still starting with `System`.
- GRENZE: a classic widget created with a custom `class_=` is not matched by its class name (no program uses `class_=`, checked 2026-11-08).

## Theme lifecycle: listeners

`configure_ttk_theme(root, theme_key)` first applies the ttk styles, then runs the theme listeners **exactly once** (`bw_gui.theming.register_theme_listener`, implemented in `_theme_listeners`).

- **`register_theme_listener(callback, *, owner, widget=None) -> Subscription`** calls `callback(ThemeChange(theme_key, intensity, is_dark))` after every switch while `owner` lives.
  - **Widget-bound lifetime:** the listener also ends on the `<Destroy>` of a Tk widget: `widget`, or `owner` itself if it is a widget. This is not only when the Python object is collected. A destroyed widget may still be referenced, or its interpreter may already be gone, and then `winfo_exists()` raises instead of returning 0. Consumers therefore never add their own `on_destroy` for this. Components whose owner is not a widget pass `widget=` (e.g. `DataGrid` passes its frame).
  - `owner` is mandatory and must be weak-referenceable; `None` or a non-weakref-able object raises `TypeError`.
  - A bound method is held as `WeakMethod`. Any other callable is held strongly and removed when `owner` is finalized, so it must **not** capture `owner` strongly (documented limit, tested).
  - `remove()` ends a registration earlier and is idempotent.
- **Order:** styles first, then the listeners over a snapshot in registration order. A listener added during the phase runs from the next switch on. A listener that raises does not stop the others; the error goes to the root's `report_callback_exception`.
- **Re-entrancy (decision 24):** a `configure_ttk_theme` call during the listener phase is deferred. The last request wins and runs once, completely (styles and listeners), after the phase. A deferred request equal to the state just applied (theme key and intensity) is dropped. Within one sequence of follow-up switches bw-gui remembers the applied states: a request that repeats one of them is a cycle, so the sequence stops with a reported `RuntimeError` and the last applied state stays. Independently, at most `MAX_FOLLOW_UPS = 8` follow-up switches run. That number is only a safety limit against endless sequences of *different* states and has no other meaning; normal use never reaches it.
- **Who listens inside bw-gui:**
  - **Icon buttons** (`icon_button`): one listener per button with the button as owner. The registry has weak keys, so a destroyed, unreferenced button disappears (formerly a global list held every button strongly).
  - **Native scrollbars** (`bw_gui.runtime.widgets.Scrollbar`, see `SCROLLABILITY_CONTRACT.md`).
- **Not a listener, on purpose:** the Checkbox/Switch indicator images (`_toggle_styles`) are reconfigured **in place** during the style phase (`PhotoImage.configure(data=...)`). Every widget and menu entry that shows them follows the switch without a listener, so a listener would add nothing.

