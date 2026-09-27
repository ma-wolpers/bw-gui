"""WindowShortcutBinder — declarative keyboard-shortcut registration for one window.

Wraps the low-level ``window.bind(sequence, handler)`` call with the mode/focus/
dialog/offline/modifier gating defined in ``bw_gui.contracts.keybinding``, so
consuming apps register shortcuts once instead of hand-rolling the
register+context+gate+bind boilerplate locally -- and never interpret Tk's
``event.state`` or sequence syntax themselves.

Contract decisions (see ``docs/KEYBINDING_CONTRACT.md``):

* **Scope / bindtag.** One binder serves exactly one toplevel and binds on that
  window's own bindtag (``window.bind``). Widgets inside *other* toplevels (popups,
  dialogs) do not see these shortcuts. ``bind_all`` is deliberately not used; a
  cross-window shortcut scope would be a separate contract.
* **Multiplexing.** Tk keeps only one script per (tag, sequence) and silently
  replaces it on a second ``bind``. The binder therefore binds each semantic
  :func:`~bw_gui.contracts.binding_signature` exactly once and dispatches
  internally to the first allowed definition in registration order. Two
  definitions with the same signature whose runtime applicability overlaps are
  rejected at bind time (``ValueError``) instead of silently shadowing each other.
* **Propagation.** A blocked shortcut returns ``None`` (never ``"break"``), so
  later bindtags -- e.g. a global ``<Alt-KeyPress>`` menu handler on ``all`` --
  still see the event. An executed shortcut returns its handler's result.
"""

from __future__ import annotations

from typing import Callable

from bw_gui.contracts.key_modifiers import (
    TkBackend,
    backend_for_platform,
    backend_for_windowing_system,
    modifiers_from_event,
)
from bw_gui.contracts.key_sequence import BindingSignature, binding_signature
from bw_gui.contracts.keybinding import (
    UI_MODE_GLOBAL,
    KeyBindingDefinition,
    KeybindingRegistry,
    KeybindingRuntimeContext,
    derive_active_mode,
)
from bw_gui.contracts.keybinding_conflicts import definitions_overlap

from .primitives import ui, widgets


def _default_is_text_input(widget) -> bool:
    if widget is None:
        return False
    return isinstance(widget, (ui.Entry, ui.Text, ui.Spinbox, widgets.Entry, widgets.Combobox))


def detect_backend(window) -> TkBackend:
    """Return the Tk backend of *window* via ``tk windowingsystem``.

    Falls back to :func:`backend_for_platform` for objects without a Tk
    interpreter (e.g. test doubles).
    """
    try:
        return backend_for_windowing_system(window.tk.call("tk", "windowingsystem"))
    except Exception:
        return backend_for_platform()


class WindowShortcutBinder:
    """Registers keyboard shortcuts on one window with centralized runtime gating.

    Each ``bind()`` call registers a :class:`KeyBindingDefinition`. For every keypress
    the binder builds the runtime context (active mode, text-input focus, dialog,
    offline, decoded modifiers) and only invokes a handler when
    :meth:`KeybindingRegistry.evaluate_runtime` allows it. ``window`` can be any
    object exposing ``bind()``/``focus_get()``, e.g. a ``tk.Tk``/``tk.Toplevel`` or a
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
        mode_provider: Callable[[], str] | None = None,
        on_dispatch: Callable[[str, bool], None] | None = None,
        backend: TkBackend | None = None,
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
            mode_provider: Zero-arg callable returning the app's base UI mode, used
                whenever no higher-priority state (offline, dialog, text input) applies.
                Generic binder feature; defaults to ``UI_MODE_GLOBAL``. Apps should
                derive it from their domain state, not from widget visibility.
            on_dispatch: Optional ``on_dispatch(intent, success=...)`` telemetry hook,
                called after every handler invocation that actually ran (``success``
                passed as a keyword argument).
            backend: Tk backend override; by default detected from the window via
                ``tk windowingsystem``.
        """

        self.window = window
        self.registry = registry if registry is not None else KeybindingRegistry()
        self._hsm_contract = hsm_contract
        self._is_text_input = is_text_input or _default_is_text_input
        self._dialog_open = dialog_open or (lambda: False)
        self._offline = offline or (lambda: False)
        self._mode_provider = mode_provider or (lambda: UI_MODE_GLOBAL)
        self._on_dispatch = on_dispatch
        self.backend = backend if backend is not None else detect_backend(window)
        self._dispatch_table: dict[
            BindingSignature, list[tuple[KeyBindingDefinition, Callable[[object], object]]]
        ] = {}

    def build_context(self, event=None) -> KeybindingRuntimeContext:
        """Build the runtime context (mode/offline/text-input/dialog/modifiers) for one event.

        Without an event (e.g. debug overlays) ``modifiers`` stays ``None``.
        """

        focused_widget = getattr(event, "widget", None) or self.window.focus_get()
        text_input_focused = self._is_text_input(focused_widget)
        dialog_open = self._dialog_open()
        offline = self._offline()
        active_mode = derive_active_mode(
            offline=offline,
            dialog_open=dialog_open,
            text_input_focused=text_input_focused,
            base_mode=self._mode_provider(),
        )
        return KeybindingRuntimeContext(
            active_mode=active_mode,
            offline=offline,
            text_input_focused=text_input_focused,
            dialog_open=dialog_open,
            modifiers=None if event is None else modifiers_from_event(event, self.backend),
            backend=self.backend,
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
        allow_modifiers: bool = False,
    ) -> KeyBindingDefinition:
        """Register one shortcut and bind it to ``window`` with runtime gating applied.

        Mirrors ``window.bind(sequence, handler)`` plus the declarative gating
        parameters from :class:`KeyBindingDefinition`. Returns the registered
        definition so callers can inspect it (e.g. for manifest/debug tooling).

        Raises:
            ValueError: For unknown intents, sequences outside the keyboard-shortcut
                contract, or a conflict with an already bound definition of the same
                signature (see module docstring).
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
            allow_modifiers=allow_modifiers,
            allow_when_text_input=allow_when_text_input,
            allow_when_offline=allow_when_offline,
        )
        signature = binding_signature(sequence, self.backend)
        entries = self._dispatch_table.get(signature)
        for existing, _handler in entries or ():
            if definitions_overlap(existing, definition, self.backend):
                raise ValueError(
                    f"Keybinding conflict: {definition.binding_id!r} ({sequence}) overlaps "
                    f"{existing.binding_id!r} ({existing.sequence}) in at least one runtime context"
                )
        self.registry.register(definition)

        if entries is None:
            entries = []
            self._dispatch_table[signature] = entries
            self.window.bind(sequence, lambda event, sig=signature: self._dispatch(sig, event))
        entries.append((definition, handler))
        return definition

    def _dispatch(self, signature: BindingSignature, event):
        """Run the first allowed definition bound to *signature*; ``None`` if all are blocked."""
        context = self.build_context(event)
        for definition, handler in self._dispatch_table.get(signature, ()):
            can_execute, _reason = self.registry.evaluate_runtime(definition, context)
            if not can_execute:
                continue
            try:
                result = handler(event)
            except Exception:
                if self._on_dispatch is not None:
                    self._on_dispatch(definition.intent, success=False)
                raise
            if self._on_dispatch is not None:
                self._on_dispatch(definition.intent, success=True)
            return result
        return None
