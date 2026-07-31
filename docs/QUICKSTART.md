# Quickstart — bw-gui

## What is bw-gui?

bw-gui is a toolkit that gives your Python desktop program a working window straight
away — with a themed menubar, a color scheme switcher, dialog utilities, and keyboard
shortcut management — so you can focus on your program's content instead of building
all that window infrastructure yourself.

Without bw-gui you'd need to set up the Tk root window, configure its title, add a
menubar, wire up the close button, apply a color theme, make popups behave correctly,
and more. bw-gui does all of that for you. You just describe what's *in* your window.

---

## What is `bw_libs`?

`bw_libs` is **not** the library. It is a tiny bootstrap helper that each
consuming program copies into itself. Its sole job is to find the real `bw-gui`
installation on the file system and add it to `sys.path`, so that
`import bw_gui` works regardless of how the program is launched.

```
my_program/
  bw_libs/
    shared_gui_core.py   ← bootstrap: finds bw-gui/src/ and adds it to sys.path
  main.py                ← your program
```

You never modify `bw_libs`. If `import bw_gui` fails, check that:
1. `bw-gui` is at `c:\Users\7thpl\Desktop\Code\bw-gui`
2. `bw_libs/shared_gui_core.py` is calling `ensure_bw_gui_on_path()` at startup

---

## How bw-gui works — the core idea

bw-gui gives you a **base window class** called `BwBaseWindow`. You build your
program by *inheriting* from it — meaning your window class starts from
`BwBaseWindow` as a foundation and fills in only the parts specific to your program.

You do this by overriding two methods:

- **`build_content(frame)`** — place your widgets (buttons, labels, text fields)
  inside `frame`
- **`build_menu()`** — return a list of menu sections you want in the menubar

"Overriding" means: `BwBaseWindow` already has empty versions of these methods that
do nothing. You replace those empty versions with your own code. Everything else —
the window setup, the menubar strip, the theme switcher, the close behavior — is
handled for you automatically.

---

## Minimal Example — 10 lines

```python
# main.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bw_libs"))
from shared_gui_core import ensure_bw_gui_on_path
ensure_bw_gui_on_path()

from bw_gui import BwBaseWindow

class MyApp(BwBaseWindow):
    def build_content(self, frame):
        from bw_gui.runtime import widgets
        widgets.Label(frame, text="Hello, Welt!").pack(padx=40, pady=40)

if __name__ == "__main__":
    MyApp(title="Mein Programm").run()
```

**What each part does:**

| Line | What it does |
|---|---|
| `sys.path.insert(...)` + `ensure_bw_gui_on_path()` | Locates bw-gui on disk and makes `import bw_gui` work |
| `class MyApp(BwBaseWindow)` | Your window class *starts from* BwBaseWindow (inherits it) |
| `def build_content(self, frame)` | Your override — place your widgets inside `frame` |
| `widgets.Label(...)` | Creates a text label using bw-gui's widget set |
| `MyApp(title="Mein Programm").run()` | Creates the window and starts the event loop |

That's it. You get:
- A themed window (default: `mono_day`)
- A **Datei** menu with a "Einstellungen…" item (calls `open_settings()`, a no-op by default)
- An **Ansicht** menu with a theme-switcher for all 10 built-in themes

---

## Adding a Menu

Override `build_menu()` and return a list of `MenuSectionSpec` objects. Each
`section_spec(...)` call describes one top-level menu button and the function that
produces its items when clicked.

```python
from bw_gui import BwBaseWindow
from bw_gui.menu import section_spec, MenuItem

class MyApp(BwBaseWindow):
    def build_menu(self):
        return [
            section_spec("file", items_provider=self._file_items),
            section_spec("edit", items_provider=self._edit_items),
        ]

    def _file_items(self):
        return [
            MenuItem(type="command", label="Öffnen…",   command=self._on_open),
            MenuItem(type="command", label="Speichern", command=self._on_save),
            MenuItem(type="separator"),
            MenuItem(type="command", label="Beenden",   command=self.close),
        ]

    def _edit_items(self):
        return [
            MenuItem(type="command", label="Rückgängig", command=self._on_undo),
        ]

    def _on_open(self):  pass
    def _on_save(self):  pass
    def _on_undo(self):  pass
```

The `items_provider` is a function that is called fresh every time the menu opens —
so if your menu items change depending on state (e.g. "Speichern" only enabled when
there is unsaved content), they always reflect the current situation.

The standard keys `"file"`, `"edit"`, `"view"`, `"help"` map to the four fixed
positions. Any other key becomes an extra section inserted between View and Help.

Built-in items (Settings in File, theme switcher in View) are always added
automatically — you do not need to include them.

---

## Adding Widgets

Put all widget creation inside `build_content(frame)`. Use `bw_gui.runtime.widgets`
(ttk) and `bw_gui.runtime.ui` (plain tk) — do **not** import tkinter directly.

```python
from bw_gui.runtime import widgets, ui

class MyApp(BwBaseWindow):
    def build_content(self, frame):
        # ttk widgets (follow the active theme automatically)
        self._label = widgets.Label(frame, text="Name:")
        self._label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self._entry = widgets.Entry(frame, width=40)
        self._entry.grid(row=0, column=1, padx=10, pady=10)

        btn = widgets.Button(frame, text="Los!", command=self._on_go)
        btn.grid(row=1, column=0, columnspan=2, pady=20)

        # plain tk Canvas (not available in ttk) — theme applied in apply_theme()
        self._canvas = ui.Canvas(frame, width=300, height=200)
        self._canvas.grid(row=2, column=0, columnspan=2)

    def _on_go(self):
        name = self._entry.get()
        self._label.configure(text=f"Hallo, {name}!")
```

### Theming raw tk widgets (Canvas, Text, Listbox)

ttk widgets pick up colours from the ttk style system automatically.  Raw tk
widgets need explicit color configuration — call the bw-gui helpers inside
`apply_theme()`:

```python
from bw_gui.theming import configure_ttk_theme, theme_canvas, theme_text

class MyApp(BwBaseWindow):
    def build_content(self, frame):
        self._canvas = ui.Canvas(frame, width=300, height=200)
        self._notes  = ui.Text(frame, height=5)

    def apply_theme(self, theme_key: str) -> None:
        super().apply_theme(theme_key)
        configure_ttk_theme(self.tk_root, theme_key)  # sets the global current theme
        theme_canvas(self._canvas)   # no theme_key argument — theme is ambient
        theme_text(self._notes)      # same
```

> **Theme is ambient:** `configure_ttk_theme(root, theme_key)` records the
> active theme globally inside bw-gui.  All subsequent calls to `theme_canvas`,
> `theme_text`, `tinted_color`, etc. — *without* a `theme_key` argument — read
> that global automatically.  This means consumer code never needs to forward
> `theme_key` to anything: set it once in `configure_ttk_theme`, then let
> every utility pick it up for free.  The `theme_key_provider=lambda: self.theme_key`
> lambda in `SettingsDialogOrchestrator` reads the theme *at call time* for the
> same reason — the correct value is always available from the global.

---

## Opening a Settings Dialog

Override `open_settings()` and use `SettingsDialogOrchestrator`:

```python
from bw_gui.dialogs import SettingsDialogOrchestrator, SettingsDialogSpec, SettingsSectionSpec, SettingsFieldSpec

MY_SPEC = SettingsDialogSpec(sections=(
    SettingsSectionSpec(key="general", label="Allgemein", fields=(
        SettingsFieldSpec(key="autosave", label="Automatisch speichern", field_type="bool", default=True),
        SettingsFieldSpec(key="font_size", label="Schriftgröße", field_type="int",
                          default=12, min_value=8, max_value=24),
    )),
))

class MyApp(BwBaseWindow):
    def __init__(self, **kwargs):
        self._settings = {"autosave": True, "font_size": 12}
        super().__init__(**kwargs)
        self._orchestrator = SettingsDialogOrchestrator(
            title="Einstellungen",
            theme_key_provider=lambda: self.theme_key,
            spec_provider=lambda: MY_SPEC,
            values_provider=lambda: self._settings.copy(),
            commit_handler=self._on_settings_saved,
        )

    def open_settings(self):
        self._orchestrator.open(self)

    def _on_settings_saved(self, values):
        self._settings.update(values)
```

> **Note:** Do not add a theme field to your settings dialog. `BwBaseWindow` already
> provides theme switching in the **Ansicht** menu — adding a second entry would be
> redundant and would require keeping it in sync manually.

---

## Running the Program

```python
if __name__ == "__main__":
    MyApp(
        title="Mein Programm",
        geometry="1200x800",
        theme_key="warm_day",
    ).run()
```

See also:
- [MENUBAR.md](MENUBAR.md) — menu sections, item types, submenus
- [THEMING.md](THEMING.md) — themes, tokens, custom themes
- [DIALOGS.md](DIALOGS.md) — popups, message boxes, settings dialog
- [KEYBINDINGS.md](KEYBINDINGS.md) — keyboard shortcuts
- [WIDGETS.md](WIDGETS.md) — HoverTooltip, WrappedTextField
- [LAUFKERN.md](LAUFKERN.md) — shortcut reachability verification
