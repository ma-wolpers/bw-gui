"""Public API for the tabbed settings dialog.

Consumers import from here or from ``bw_gui.dialogs``::

    from bw_gui.dialogs import (
        SettingsFieldSpec,
        SettingsSectionSpec,
        SettingsDialogSpec,
        coerce_settings_payload,
        TabbedSettingsDialog,
        open_tabbed_settings_dialog,
    )

Implementation is split across two private modules:

- ``_settings_spec.py`` — data classes and value-coercion helpers
- ``_settings_dialog.py`` — ``TabbedSettingsDialog`` UI class
"""

from __future__ import annotations

from ._settings_dialog import TabbedSettingsDialog
from ._settings_spec import (
    SettingsDialogSpec,
    SettingsFieldSpec,
    SettingsSectionSpec,
    coerce_settings_payload,
)

__all__ = [
    "SettingsFieldSpec",
    "SettingsSectionSpec",
    "SettingsDialogSpec",
    "coerce_settings_payload",
    "TabbedSettingsDialog",
    "open_tabbed_settings_dialog",
]


def open_tabbed_settings_dialog(
    parent,
    *,
    title: str,
    theme_key: str,
    spec: SettingsDialogSpec,
    initial_values: dict[str, object],
    initial_section: str | None = None,
    on_live_apply=None,
    on_commit=None,
) -> dict[str, object] | None:
    """Open a modal settings dialog and return the saved values dict.

    Constructs a ``TabbedSettingsDialog``, blocks until the user closes it,
    and returns the committed values or ``None`` when the user cancels.

    Args:
        parent:          Tk parent window.
        title:           Window title bar text.
        theme_key:       Active theme key forwarded to bw_gui theming.
        spec:            Full dialog spec (sections + fields).
        initial_values:  Pre-populated values keyed by field key.
        initial_section: Section key to navigate to on open; first section used
                         when ``None`` or not found.
        on_live_apply:   Callback fired with current values on every live-apply
                         field change.
        on_commit:       Callback fired with current values on Apply and Save.

    Returns:
        Coerced values dict when the user clicks Save or Apply; ``None`` when
        the dialog is cancelled or closed via the window button.
    """
    dialog = TabbedSettingsDialog(
        parent,
        title=title,
        theme_key=theme_key,
        spec=spec,
        initial_values=initial_values,
        initial_section=initial_section,
        on_live_apply=on_live_apply,
        on_commit=on_commit,
    )
    return dialog.result
