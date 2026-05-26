from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from bw_gui.theming import apply_window_theme, configure_ttk_theme

from .primitives import ui


@dataclass(frozen=True)
class AppShellConfig:
    """Shared shell configuration for Tk root windows."""

    title: str
    geometry: str
    min_width: int
    min_height: int
    theme_key: str | None = None


class TkinterAppShell:
    """Apply common root window setup and close lifecycle handling."""

    def __init__(
        self,
        root: ui.Tk,
        config: AppShellConfig,
        *,
        on_close: Callable[[], bool | None] | None = None,
    ) -> None:
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
        """Return the currently applied shell theme key."""

        return self._theme_key

    def apply_theme(self, theme_key: str) -> None:
        """Apply a theme to the root and configured ttk styles."""

        self._theme_key = theme_key
        apply_window_theme(self.root, theme_key)
        configure_ttk_theme(self.root, theme_key)

    def _handle_close(self) -> None:
        if self._on_close is not None:
            should_close = self._on_close()
            if should_close is False:
                return
        self.root.destroy()
