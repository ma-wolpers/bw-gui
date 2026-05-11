"""Runtime context helpers for LaufKern."""

from __future__ import annotations

from bw_gui.contracts.keybinding import KeybindingRuntimeContext
from bw_gui.contracts.popup import PopupPolicyRegistry


def build_runtime_context(
    *,
    active_mode: str,
    popup_registry: PopupPolicyRegistry | None = None,
    offline: bool = False,
    text_input_focused: bool = False,
) -> KeybindingRuntimeContext:
    """Build one runtime context from base UI state and popup policy state."""

    dialog_open = False
    if popup_registry is not None:
        dialog_open = popup_registry.has_mode_blocking_popup()

    return KeybindingRuntimeContext(
        active_mode=active_mode,
        offline=offline,
        text_input_focused=text_input_focused,
        dialog_open=dialog_open,
    )
