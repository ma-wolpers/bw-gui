# Migration Guide

## 0.x to 0.1.0

Initial adoption steps:

1. Add repository as git submodule in consumer repo.
2. Ensure `bw_gui` import path is available from the consumer runtime.
3. Replace local duplicated contract modules with imports from `bw_gui.contracts`.
4. Route theme configuration via `bw_gui.theming.theme_manager`.
5. Inherit `BwBaseWindow`; implement `build_menu()`, `build_content(frame)`, `open_settings()`.
6. Replace ad-hoc tooltip snippets with `bw_gui.widgets.hover_tooltip.HoverTooltip`.

> **Note:** `CustomMenuBar`, `TkRootHost`, and `TkinterAppShell` are low-level building
> blocks used internally by `BwBaseWindow`. They are not part of the public API.
> Do not use them directly — use `BwBaseWindow` instead.

## Consumer Checklist

- No duplicate local contract copies remain.
- No native Tk menubar in target windows.
- Shortcut labels and hover help are centralized.
- Theme application covers all major widgets.
- No `THEME_ORDER` or `THEMES` references in program code — theme switching is handled by `BwBaseWindow`'s View menu.
- **Principle C (theme is ambient):** no `theme_key` forwarded to utility calls.
  After `configure_ttk_theme(root, key)` runs, all `theme_canvas(w)`,
  `tinted_color(seed, degree=x)`, etc. resolve the key automatically from
  the global.  Consumer `apply_theme()` overrides must not pass `theme_key`
  to any bw-gui utility — that would imply the consumer holds independent
  theme knowledge, which it does not.

## Replacing Checkbuttons with Checkbox / Switch

First classify each site by asking **when does its business effect happen?**
(`docs/TOGGLE_CONTRACT.md`, "Classifying a control"). If it happens only on a submit
action, use a Checkbox; if it happens immediately, use a Switch.

| Before | After |
|---|---|
| `widgets.Checkbutton(f, text=t, variable=v)`, value read on OK/Export | `Checkbox(f, text=t, variable=v)` |
| `widgets.Checkbutton(f, text=t, variable=v, command=apply)` (effect at once) | `Switch(f, text=t, variable=v, on_change=lambda on: apply())` |
| effect hung on `v.trace_add("write", ...)` | move it into `on_change`; traces now only observe UI state |
| `command=` that only ticks other boxes / enables controls | `Checkbox(..., on_select=...)` |
| `cb.state(["alternate"])` / `cb.state(["!alternate"])` | `cb.set_mixed(True)` / `cb.set_mixed(False)` |
| callback reads the (already flipped) variable or domain state to guess intent | use the `requested` argument |
| `IntVar`/`StringVar` with `onvalue`/`offvalue` | `BooleanVar` (convert at the domain boundary) |
| `MenuItem(type="checkbox", checked=c, command=toggle)` (acts on click) | `MenuItem(type="switch", checked=c, on_toggle=lambda on: ...)` |
| `menu.add_checkbutton(label=l, variable=v, command=apply)` | `add_menu_switch(menu, label=l, variable=v, on_change=lambda on: apply())` |

Checklist:

- No `Checkbutton(...)`/`add_checkbutton(...)` left in app code (enforced later by
  `bw_gui.testing.checkbutton_guard`).
- Every Switch's effect works without any submit button, and no Checkbox's value
  takes effect before submit.
- Settings dialogs: `on_commit` is your configuration-commit interface. It is now
  also called on Cancel when a live value changed.

## Checklist: removing a kursplaner-style "extended theme dict"

If your program has a function like `my_theme(key)` that calls `get_theme(key)`
and adds computed domain colours on top:

1. Delete the function.
2. Extract any domain hex seeds as module constants (e.g. `MY_SEED = "#7C3AED"`).
3. Replace `mix_hex(base, seed, degree)` calls in consumer code with
   `tinted_color(seed, degree=degree)` from `bw_gui.theming`.
4. Replace `contrast_text_color(bg)` calls with `tinted_foreground(seed, degree=degree)`.
5. Replace `is_dark_color(bg)` dark/light branches with `tinted_color`'s `base_token`
   parameter — bw-gui picks the right base automatically.
6. Verify: `grep -r "get_theme\|mix_hex\|is_dark_color\|contrast_text_color"` in
   consumer code → zero matches outside the theming-configuration layer.
