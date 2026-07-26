"""BwBaseWindow — the standard entry point for all Blattwerk-family programs.

Subclass, implement the three hooks, and call run()::

    class MyApp(BwBaseWindow):
        def __init__(self) -> None:
            super().__init__(title="My App", geometry="900x600")

        def build_menu(self) -> list:
            return [section_spec("file", self._file_items)]

        def build_content(self, frame) -> None:
            widgets.Label(frame, text="Hello!").pack()

        def open_settings(self) -> None:
            self._orchestrator.open(self)

    if __name__ == "__main__":
        MyApp().run()

BwBaseWindow automatically injects a ``Einstellungen`` item into the Datei menu
(calling ``open_settings()``) and a theme radio group at the bottom of the
Ansicht menu.
"""

from __future__ import annotations

from typing import Callable

from bw_gui.menu import CustomMenuBar, MenuItem, section_spec
from bw_gui.menu.standard_menu import build_standard_menu_definitions
from bw_gui.theming import DEFAULT_THEME, THEME_ORDER, get_theme

from .app_shell import AppShellConfig, TkinterAppShell
from .primitives import widgets
from .root_host import TkRootHost


class BwBaseWindow(TkRootHost):
    """Standard window base class for all Blattwerk-family programs.

    Subclass and override ``build_menu()``, ``build_content(frame)``, and
    ``open_settings()``.  Constructor parameters are passed to
    ``TkinterAppShell`` and forwarded to the underlying ``tk.Tk`` root.

    Store instance state *before* calling ``super().__init__()``, because
    ``__init__`` immediately calls ``build_menu()`` and ``build_content(frame)``
    on the subclass instance.
    """

    def __init__(
        self,
        *,
        title: str,
        geometry: str,
        min_width: int = 600,
        min_height: int = 400,
        theme_key: str = DEFAULT_THEME,
        on_close: Callable[[], bool | None] | None = None,
    ) -> None:
        super().__init__()

        self._shell = TkinterAppShell(
            self.tk_root,
            AppShellConfig(
                title=title,
                geometry=geometry,
                min_width=min_width,
                min_height=min_height,
                theme_key=theme_key,
            ),
            on_close=on_close,
        )

        user_sections = self.build_menu()

        file_spec = next((s for s in user_sections if s.key == "file"), None)
        edit_spec = next((s for s in user_sections if s.key == "edit"), None)
        view_spec = next((s for s in user_sections if s.key == "view"), None)
        help_spec = next((s for s in user_sections if s.key == "help"), None)
        extra_specs = [s for s in user_sections if s.key not in ("file", "edit", "view", "help")]

        merged_file = section_spec(
            "file",
            self._make_file_provider(file_spec.items_provider if file_spec else None),
            label=file_spec.label if file_spec else None,
            alt=file_spec.alt if file_spec else None,
        )
        merged_view = section_spec(
            "view",
            self._make_view_provider(view_spec.items_provider if view_spec else None),
            label=view_spec.label if view_spec else None,
            alt=view_spec.alt if view_spec else None,
        )

        definitions = build_standard_menu_definitions(
            file_section=merged_file,
            edit_section=edit_spec,
            view_section=merged_view,
            help_section=help_spec,
            extra_sections=extra_specs,
        )

        self._menu_bar = CustomMenuBar(self.tk_root, definitions, theme_key=theme_key)
        self._menu_bar.build()

        content_frame = widgets.Frame(self.tk_root)
        content_frame.pack(fill="both", expand=True)

        self.build_content(content_frame)

    # ── Hooks for subclasses ─────────────────────────────────────────────────

    def build_menu(self) -> list:
        """Return program-specific ``MenuSectionSpec`` objects.

        BwBaseWindow injects ``Einstellungen`` into the file section and theme
        radios into the view section automatically — do not add them here.
        """
        return []

    def build_content(self, frame) -> None:
        """Build program widgets inside *frame*.  Override in subclass."""

    def open_settings(self) -> None:
        """Open the settings dialog.  Override in subclass to implement."""

    def apply_theme(self, theme_key: str) -> None:
        """Apply *theme_key*.  Override in subclass for widget recoloring, but call super()."""
        self._shell.apply_theme(theme_key)
        self._menu_bar.refresh_theme(theme_key)

    # ── Public API ───────────────────────────────────────────────────────────

    @property
    def theme_key(self) -> str:
        """Currently active theme key."""
        return self._shell.current_theme_key or DEFAULT_THEME

    def run(self) -> None:
        """Start the Tk event loop."""
        self.tk_root.mainloop()

    def close(self) -> None:
        """Close the window, running through the WM_DELETE_WINDOW handler."""
        self._shell._handle_close()

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _make_file_provider(self, user_provider):
        def items():
            user_items = list(user_provider()) if user_provider is not None else []
            settings_item = MenuItem(type="command", label="Einstellungen", command=self.open_settings)
            if user_items:
                return user_items + [MenuItem(type="separator"), settings_item]
            return [settings_item]
        return items

    def _make_view_provider(self, user_provider):
        def items():
            user_items = list(user_provider()) if user_provider is not None else []
            theme_items = list(self._builtin_theme_items())
            if user_items:
                return user_items + [MenuItem(type="separator")] + theme_items
            return theme_items
        return items

    def _builtin_theme_items(self) -> tuple[MenuItem, ...]:
        active = self.theme_key
        result = []
        for key in THEME_ORDER:
            theme_data = get_theme(key)
            label = theme_data.get("label", key) if isinstance(theme_data, dict) else key
            result.append(MenuItem(
                type="radio",
                label=label,
                checked=(key == active),
                command=lambda k=key: self.apply_theme(k),
            ))
        return tuple(result)
