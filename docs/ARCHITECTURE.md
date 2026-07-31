# bw-gui Architecture — The Four Principles

These four principles govern every design decision in bw-gui and every use of it
by consumer programs.  All current code was written against them; all future
changes should be evaluated against them.

---

## The Four Principles

### A — bw-gui is the only entity that knows about colours

Consumer programs never construct colour strings, call `get_theme()` to extract
raw hex values, or maintain their own colour variables.  All colour values live
inside bw-gui and are applied by bw-gui.

The theme registry, the colour math, and every shade derivation (mix, contrast,
tinting) are bw-gui internals.  Consumers only name *what* they want to colour
and *how intensely* — never *what colour* that produces.

### B — Programs express intent; the framework acts

A program says *what it wants* — "a canvas that belongs to the theme", "an icon
button tinted for Hospitation" — and bw-gui decides what that looks like and
applies it.  No colour math, no dark/light branching, no `style.configure()` for
colour properties in consumer code.

The public API (`theme_canvas`, `tinted_color`, `icon_button`, …) is an
*intent vocabulary*, not a colour toolkit.

### C — The theme is ambient

The current active theme is tracked globally inside bw-gui.  After
`configure_ttk_theme(root, theme_key)` is called, every subsequent utility call
resolves the correct theme automatically — no `theme_key` argument is passed
around.  Consumer overrides of `apply_theme()` call bw-gui utilities with no
arguments:

```python
def apply_theme(self, theme_key: str) -> None:
    super().apply_theme(theme_key)
    configure_ttk_theme(self.tk_root, theme_key)   # sets global
    theme_canvas(self._map_canvas)                  # no argument needed
    theme_text(self._notes_editor)                  # no argument needed
```

Passing `theme_key` to utility calls from consumer code is a code smell: the
consumer has no independent theme knowledge that bw-gui lacks.

### D — Composite widgets are the right abstraction level

When creating a widget requires: creating it, coloring it, and re-applying that
color on every theme switch — that is a *composite widget* and belongs in bw-gui.

`icon_button` is the model: the consumer provides `photo_image`, `command`, and
optional `color_tint`; bw-gui handles pixel recoloring, registration, and
automatic re-recoloring on every future theme switch.  The consumer does zero
color work, forever.

---

## Anti-Patterns

These patterns violate the principles above.  If you spot them in consumer code,
refactor them.

| Anti-pattern | Principle violated | Correct replacement |
|---|---|---|
| `theme = get_theme(key); widget.configure(bg=theme["bg_surface"])` | A, C | `theme_canvas(widget)` |
| `color = mix_hex(theme["bg_panel"], "#7C3AED", 0.70)` | A, B | `tinted_color("#7C3AED", degree=0.70)` |
| `configure(bg=theme["bg_main"])` in `apply_theme()` | A | `apply_window_theme(self)` |
| `style.lookup("MyStyle.TButton", "background")` to read a colour | A | read from theme contract instead |
| `configure_ttk_theme(root, theme_key)` where `theme_key` comes from a non-framework caller | C | only the framework calls this; consumers call `apply_theme()` |
| `icon_photo = recolor(base_photo, fg_hex)` in consumer code | D | `icon_button(parent, base_photo, command, color_tint=seed)` |

---

## Why This Matters

- **Consumer programs are immune to theme system changes.**  If bw-gui changes
  how a dark theme computes its surface colour, no consumer code breaks — it
  already delegated that decision.

- **Colour expertise stays in one place.**  There is no risk of two programs
  computing "the same" colour differently.  A bug in hospitation tinting is fixed
  in one location and fixed for all programs.

- **The category of "theme switch forgot to recolor X" bugs is eliminated.**
  Because bw-gui owns the recoloring, it recolors everything it knows about on
  every switch — including icon buttons registered via `icon_button()`.

---

## Relationship to Public API

Every function in `bw_gui.theming` that accepts `theme_key=None` resolves from
the global current theme by default.  Pass an explicit key only inside bw-gui
internals (e.g. `configure_ttk_theme` itself) or in test code that exercises
specific themes in isolation.

Functions removed from `__all__` (`mix_hex`, `contrast_text_color`,
`is_dark_color`, `relative_luminance`) remain as private bw-gui internals.
Consumer code must not import them directly — their signatures and behavior are
not part of the public contract.
