"""TkinterAppShell — common root window setup and close lifecycle management.

The shell applies title, geometry, minsize, and theme to a ``tk.Tk`` root window,
and routes the window-close button through an optional ``on_close`` callback.

This is an internal helper used by ``BwBaseWindow``. Direct use is for programs
that need manual control over the Tk root before integrating the shell.

Typical usage::

    shell = TkinterAppShell(
        root,
        AppShellConfig(title="My App", geometry="900x600", min_width=600, min_height=400),
        on_close=lambda: ask_save_before_close(),
    )
    # Later, to switch theme:
    shell.apply_theme("warm_day")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from bw_gui.theming import apply_window_theme, configure_ttk_theme

from .primitives import ui


@dataclass(frozen=True)
class AppShellConfig:
    """Immutable configuration snapshot for ``TkinterAppShell``.

    All fields are applied to the root window during ``TkinterAppShell.__init__()``.

    Attributes:
        title: Window title bar text.
        geometry: Tk geometry string, e.g. ``"900x600"`` or ``"800x600+100+100"``.
        min_width: Minimum resizable width in pixels. Prevents the window from
            being shrunk to an unusable size.
        min_height: Minimum resizable height in pixels.
        theme_key: Optional initial theme key. If provided, theme is applied
            immediately during construction. If None, no theme is applied and
            the window uses the default Tk appearance.
    """

    title: str
    geometry: str
    min_width: int
    min_height: int
    theme_key: str | None = None


class TkinterAppShell:
    """Applies common root window setup and manages the close lifecycle.

    Low-level API — not exported from ``bw_gui`` top-level. Use ``BwBaseWindow`` instead.

    Sets up the window's title, geometry, minsize, and optional theme in one
    place. Also installs a ``WM_DELETE_WINDOW`` protocol handler that calls
    the optional ``on_close`` callback before deciding whether to destroy the
    window.

    The shell stores the currently active theme key so that ``BwBaseWindow``
    and the menubar can query it to build the View menu radio buttons.

    Attributes:
        root: The ``tk.Tk`` root window this shell manages.
        config: The frozen config snapshot used during construction.
    """

    def __init__(
        self,
        root: ui.Tk,
        config: AppShellConfig,
        *,
        on_close: Callable[[], bool | None] | None = None,
    ) -> None:
        """Apply window configuration and install the close handler.

        Args:
            root: The ``tk.Tk`` root window to configure.
            config: Frozen configuration snapshot with title, geometry, and theme.
            on_close: Optional callback invoked when the user clicks the close button.
                Return ``False`` to cancel the close (window stays open).
                Any other return value (including ``None``) allows the close.
                If None, the window closes unconditionally.
        """
        self.root = root
        self.config = config
        self._on_close = on_close
        self._theme_key = config.theme_key

        self.root.title(config.title)
        self.root.geometry(config.geometry)
        self.root.minsize(config.min_width, config.min_height)
        self.root.protocol("WM_DELETE_WINDOW", self._handle_close)

        if config.theme_key:
            self.apply_theme(config.theme_key)

    @property
    def current_theme_key(self) -> str | None:
        """Return the currently active theme key, or None if no theme has been applied.

        Used by ``BwBaseWindow._default_view_items()`` to mark the correct radio
        button as checked in the View menu.

        Returns:
            Theme key string, or None.
        """
        return self._theme_key

    def apply_theme(self, theme_key: str) -> None:
        """Apply a theme to the root window and configure ttk styles.

        Updates both the raw Tk window background/foreground colors and the
        ttk style configuration so that all themed widgets inside the window
        refresh to the new palette.

        Args:
            theme_key: Key of a registered theme from the theming module.
        """
        self._theme_key = theme_key
        apply_window_theme(self.root, theme_key)
        configure_ttk_theme(self.root, theme_key)

    def _handle_close(self) -> None:
        """WM_DELETE_WINDOW handler: call on_close callback, then destroy if allowed.

        If ``on_close`` returns ``False``, the close is cancelled. All other return
        values (including None, True, or any other truthy value) allow the window
        to be destroyed.
        """
        if self._on_close is not None:
            should_close = self._on_close()
            if should_close is False:
                return
        self.root.destroy()
