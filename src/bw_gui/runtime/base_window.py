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
from bw_gui.theming import DEFAULT_THEME, THEME_ORDER, get_theme, is_dark_color

from .app_shell import AppShellConfig, TkinterAppShell
from .platform import apply_window_chrome_theme
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
        """Initialise the window, menu bar, and content frame.

        Calls ``build_menu()`` and ``build_content(frame)`` on the concrete
        subclass immediately, so subclass state must be set before
        ``super().__init__(...)`` is called.

        Args:
            title:      Window title bar text.
            geometry:   Tk geometry string, e.g. ``"1200x800"``.
            min_width:  Minimum resizable width in pixels.
            min_height: Minimum resizable height in pixels.
            theme_key:  Initial theme; falls back to ``DEFAULT_THEME``.
            on_close:   Optional callback invoked before the window closes.
                        Return ``False`` to cancel the close.
        """
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
        theme = get_theme(theme_key)
        apply_window_chrome_theme(self.tk_root, prefer_dark=is_dark_color(theme["bg_main"]))

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
        """Wrap *user_provider* with a trailing ``Einstellungen`` command item.

        Returns a zero-argument callable suitable for ``section_spec()``.
        If the subclass supplied ``file`` section items they appear first,
        followed by a separator and the settings entry.
        """
        def items():
            """Yield the merged file-section menu items."""
            user_items = list(user_provider()) if user_provider is not None else []
            settings_item = MenuItem(type="command", label="Einstellungen", command=self.open_settings)
            if user_items:
                return user_items + [MenuItem(type="separator"), settings_item]
            return [settings_item]
        return items

    def _make_view_provider(self, user_provider):
        """Wrap *user_provider* with the built-in theme radio group appended.

        Returns a zero-argument callable suitable for ``section_spec()``.
        Subclass view items appear first; the theme radios follow after a
        separator.
        """
        def items():
            """Yield the merged view-section menu items."""
            user_items = list(user_provider()) if user_provider is not None else []
            theme_items = list(self._builtin_theme_items())
            if user_items:
                return user_items + [MenuItem(type="separator")] + theme_items
            return theme_items
        return items

    def _builtin_theme_items(self) -> tuple[MenuItem, ...]:
        """Build one radio ``MenuItem`` per registered theme for the View menu.

        Each radio is pre-checked when its key matches the current theme and
        calls ``apply_theme(key)`` on selection.
        """
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
