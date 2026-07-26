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
