from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .settings_dialog import SettingsDialogSpec, open_tabbed_settings_dialog


@dataclass
class SettingsDialogOrchestrator:
    """Coordinate spec/value providers with one shared settings dialog entrypoint."""

    title: str
    theme_key_provider: Callable[[], str]
    spec_provider: Callable[[], SettingsDialogSpec]
    values_provider: Callable[[], dict[str, object]]
    commit_handler: Callable[[dict[str, object]], None]
    live_apply_handler: Callable[[dict[str, object]], None] | None = None

    def open(self, parent, *, initial_section: str | None = None) -> dict[str, object] | None:
        """Open one orchestrated settings dialog using current provider state."""

        return open_tabbed_settings_dialog(
            parent,
            title=self.title,
            theme_key=self.theme_key_provider(),
            spec=self.spec_provider(),
            initial_values=self.values_provider(),
            initial_section=initial_section,
            on_live_apply=self.live_apply_handler,
            on_commit=self.commit_handler,
        )
