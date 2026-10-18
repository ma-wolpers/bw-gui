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
- State colors: `success`, `success_hover`, `success_soft`, `warning`, `warning_hover`, `warning_soft`, `danger_hover`, `danger_soft`
- Foreground helpers: `button_fg`, `fg_on_accent`, `fg_on_success`, `fg_on_warning`, `fg_on_danger`
- Focus: `focus_ring`
- Alias family: `error`, `error_hover`, `error_soft`, `fg_on_error`

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

## Theme lifecycle: listeners

`configure_ttk_theme(root, theme_key)` first applies the ttk styles, then runs the theme listeners **exactly once** (`bw_gui.theming._theme_listeners`).

- **`register_theme_listener(callback, *, owner) -> Subscription`** calls `callback(ThemeChange(theme_key, intensity, is_dark))` after every switch while `owner` lives.
  - `owner` is mandatory and must be weak-referenceable; `None` or a non-weakref-able object raises `TypeError`.
  - A bound method is held as `WeakMethod`. Any other callable is held strongly and removed when `owner` is finalized, so it must **not** capture `owner` strongly (documented limit, tested).
  - `remove()` ends a registration earlier and is idempotent.
- **Order:** styles first, then the listeners over a snapshot in registration order. A listener added during the phase runs from the next switch on. A listener that raises does not stop the others; the error goes to the root's `report_callback_exception`.
- **Re-entrancy (decision 24):** a `configure_ttk_theme` call during the listener phase is deferred. The last request wins and runs once, completely (styles and listeners), after the phase. A deferred request equal to the state just applied (theme key and intensity) is dropped. Within one sequence of follow-up switches bw-gui remembers the applied states: a request that repeats one of them is a cycle, so the sequence stops with a reported `RuntimeError` and the last applied state stays. Independently, at most `MAX_FOLLOW_UPS = 8` follow-up switches run. That number is only a safety limit against endless sequences of *different* states and has no other meaning; normal use never reaches it.
- **Who listens inside bw-gui:**
  - **Icon buttons** (`icon_button`): one listener per button with the button as owner. The registry has weak keys, so a destroyed, unreferenced button disappears (formerly a global list held every button strongly).
  - **Native scrollbars** (`bw_gui.runtime.widgets.Scrollbar`, see `SCROLLABILITY_CONTRACT.md`).
- **Not a listener, on purpose:** the Checkbox/Switch indicator images (`_toggle_styles`) are reconfigured **in place** during the style phase (`PhotoImage.configure(data=...)`). Every widget and menu entry that shows them follows the switch without a listener, so a listener would add nothing.

