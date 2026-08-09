"""WindowShortcutBinder — declarative keyboard-shortcut registration for one window.

Wraps the low-level ``window.bind(sequence, handler)`` call with the mode/focus/
dialog-open gating already defined in ``bw_gui.contracts.keybinding``, so consuming
apps register shortcuts once instead of hand-rolling the register+context+gate+bind
boilerplate locally.
"""

from __future__ import annotations

from typing import Callable

from bw_gui.contracts.keybinding import (
    UI_MODE_DIALOG,
    UI_MODE_EDITOR,
    UI_MODE_GLOBAL,
    UI_MODE_OFFLINE,
    KeyBindingDefinition,
    KeybindingRegistry,
    KeybindingRuntimeContext,
)

from .primitives import ui, widgets


def _default_is_text_input(widget) -> bool:
    if widget is None:
        return False
    return isinstance(widget, (ui.Entry, ui.Text, ui.Spinbox, widgets.Entry, widgets.Combobox))


class WindowShortcutBinder:
    """Registers keyboard shortcuts on one window with centralized mode/focus gating.

    Each ``bind()`` call registers a :class:`KeyBindingDefinition`, builds the
    runtime context (which widget is focused, is a dialog open, is offline mode
    active) for every keypress, and only invokes ``handler`` when
    :meth:`KeybindingRegistry.evaluate_runtime` allows it — before finally calling
    the real ``window.bind(sequence, ...)``. ``window`` can be any object exposing
    ``bind()``/``focus_get()``, e.g. a ``tk.Tk``/``tk.Toplevel`` or a
    :class:`~bw_gui.runtime.BwBaseWindow` (which delegates to its Tk root).
    """

    def __init__(
        self,
        window,
        *,
        registry: KeybindingRegistry | None = None,
        hsm_contract=None,
        is_text_input: Callable[[object], bool] | None = None,
        dialog_open: Callable[[], bool] | None = None,
        offline: Callable[[], bool] | None = None,
        on_dispatch: Callable[[str, bool], None] | None = None,
    ) -> None:
        """Create a binder for one window.

        Args:
            window: The window shortcuts are bound to (anything with ``bind``/``focus_get``).
            registry: Reused registry instance, e.g. for manifest/reachability tooling.
                A new empty one is created if omitted.
            hsm_contract: Optional object with ``validate_intent(intent) -> (bool, reason)``.
                When omitted, intents are not validated (suitable for simple dialogs).
            is_text_input: Predicate to detect an editable widget. Defaults to an
                isinstance check against the common Entry/Text/Combobox/Spinbox types.
            dialog_open: Zero-arg predicate for "is a modal dialog currently open".
                Defaults to always False.
            offline: Zero-arg predicate for "is offline/debug mode active".
                Defaults to always False.
            on_dispatch: Optional ``on_dispatch(intent, success=...)`` telemetry hook,
                called after every handler invocation that actually ran (``success``
                passed as a keyword argument).
        """

        self.window = window
        self.registry = registry if registry is not None else KeybindingRegistry()
        self._hsm_contract = hsm_contract
        self._is_text_input = is_text_input or _default_is_text_input
        self._dialog_open = dialog_open or (lambda: False)
        self._offline = offline or (lambda: False)
        self._on_dispatch = on_dispatch

    def build_context(self, event=None) -> KeybindingRuntimeContext:
        """Build the runtime context (mode/offline/text-input/dialog) for one event."""

        focused_widget = getattr(event, "widget", None) or self.window.focus_get()
        text_input_focused = self._is_text_input(focused_widget)
        dialog_open = self._dialog_open()
        offline = self._offline()

        if offline:
            active_mode = UI_MODE_OFFLINE
        elif dialog_open:
            active_mode = UI_MODE_DIALOG
        elif text_input_focused:
            active_mode = UI_MODE_EDITOR
        else:
            active_mode = UI_MODE_GLOBAL

        return KeybindingRuntimeContext(
            active_mode=active_mode,
            offline=offline,
            text_input_focused=text_input_focused,
            dialog_open=dialog_open,
        )

    def bind(
        self,
        sequence: str,
        handler: Callable[[object], object],
        *,
        binding_id: str,
        intent: str,
        modes: tuple[str, ...] = (UI_MODE_GLOBAL,),
        allow_when_text_input: bool = False,
        allow_when_offline: bool = True,
    ) -> KeyBindingDefinition:
        """Register one shortcut and bind it to ``window`` with runtime gating applied.

        Mirrors ``window.bind(sequence, handler)`` plus the declarative gating
        parameters from :class:`KeyBindingDefinition`. Returns the registered
        definition so callers can inspect it (e.g. for manifest/debug tooling).
        """

        if self._hsm_contract is not None:
            intent_ok, reason = self._hsm_contract.validate_intent(intent)
            if not intent_ok:
                raise ValueError(f"Unknown runtime shortcut intent: {intent} ({reason})")

        definition = KeyBindingDefinition(
            binding_id=binding_id,
            sequence=sequence,
            intent=intent,
            modes=modes,
            allow_when_text_input=allow_when_text_input,
            allow_when_offline=allow_when_offline,
        )
        self.registry.register(definition)

        def _wrapped(event):
            context = self.build_context(event)
            can_execute, _reason = self.registry.evaluate_runtime(definition, context)
            if not can_execute:
                return None
            try:
                result = handler(event)
            except Exception:
                if self._on_dispatch is not None:
                    self._on_dispatch(intent, success=False)
                raise
            if self._on_dispatch is not None:
                self._on_dispatch(intent, success=True)
            return result

        self.window.bind(sequence, _wrapped)
        return definition
