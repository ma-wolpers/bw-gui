"""Shortcut binders on top of the semantic key dispatch (``KEYBINDING_CONTRACT.md``).

All binders share :class:`_ShortcutScope`: definitions with ``KeySpec`` keys,
runtime gating (mode, offline, text input, dialog), model-A conflict checks and the
``applies_when`` rule. They differ only in *where* their keyboard channel sits:

* :class:`WindowShortcutBinder` -- the toplevel path tag (Tk puts it into the
  bindtags of every current and future descendant; decision 36). bw-gui owns all
  keyboard bindings on that tag.
* :class:`ApplicationShortcutBinder` -- the ``all`` router, role ``APP_SHORTCUT``
  (cross-window; replaces consumer ``bind_all`` shortcuts).
* ``WidgetShortcutBinder`` (``bw_gui.runtime.widget_keys``) -- a ``bwkeys:<path>``
  tag directly after the widget's own path tag.

``applies_when`` (model A): gating yields at most one applicable definition per key;
if its predicate is ``False`` the handler does not run, ``on_dispatch`` is not called,
the result is ``NOT_HANDLED`` and the Tk event propagates. No further definition is
searched. Handlers receive a :class:`~bw_gui.contracts.key_event.KeyEvent` and return
:class:`~bw_gui.contracts.events.EventResult` (``None`` = ``NOT_HANDLED``).
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from bw_gui.contracts.events import EventResult, coerce_result
from bw_gui.contracts.key_event import KeyEvent
from bw_gui.contracts.key_modifiers import TkBackend
from bw_gui.contracts.key_spec import KeySpec, matches
from bw_gui.contracts.keybinding import (
    UI_MODE_GLOBAL,
    KeyBindingDefinition,
    KeybindingRegistry,
    KeybindingRuntimeContext,
    derive_active_mode,
)
from bw_gui.contracts.keybinding_conflicts import definitions_overlap
from bw_gui.contracts.subscription import Subscription

from ._key_channel import KeyChannel, KeyDispatch, detect_backend
from ._tk_identity import interpreter_root, runtime_for
from .key_router import ROLE_APP_SHORTCUT, router_for
from .text_input import accepts_text_input

__all__ = [
    "ApplicationShortcutBinder",
    "ShortcutRegistration",
    "WindowShortcutBinder",
    "detect_backend",
]

PHASE_SHORTCUT = 10


class ShortcutRegistration(Subscription):
    """Subscription of one shortcut binding; ``definition`` serves manifest/debug tools."""

    __slots__ = ("definition",)

    def __init__(self, definition: KeyBindingDefinition, remove: Callable[[], None]) -> None:
        super().__init__(remove)
        self.definition = definition


class _ShortcutScope:
    """Definitions, gating and dispatch shared by every binder kind."""

    def __init__(
        self,
        anchor: Any,
        *,
        registry: KeybindingRegistry | None = None,
        hsm_contract: Any = None,
        is_text_input: Callable[[object], bool] | None = None,
        dialog_open: Callable[[], bool] | None = None,
        offline: Callable[[], bool] | None = None,
        mode_provider: Callable[[], str] | None = None,
        on_dispatch: Callable[..., None] | None = None,
        backend: TkBackend | None = None,
    ) -> None:
        """See the binder subclasses for the meaning of each hook."""
        self.anchor = anchor
        self.registry = registry if registry is not None else KeybindingRegistry()
        self._hsm_contract = hsm_contract
        self._is_text_input = is_text_input or accepts_text_input
        self._dialog_open = dialog_open or (lambda: False)
        self._offline = offline or (lambda: False)
        self._mode_provider = mode_provider or (lambda: UI_MODE_GLOBAL)
        self._on_dispatch = on_dispatch
        self.backend = backend if backend is not None else detect_backend(anchor)
        self._entries: list[tuple[KeyBindingDefinition, Callable[[KeyEvent], object], Callable[[KeyEvent], bool] | None]] = []
        self._subscriptions: list[Subscription] = []
        self.disposed = False

    # -- definition -----------------------------------------------------------------

    def _peer_definitions(self) -> Iterable[KeyBindingDefinition]:
        """Definitions that share this scope's keyboard channel (conflict universe)."""
        return [entry[0] for entry in self._entries]

    def bind(
        self,
        keys: KeySpec | Iterable[KeySpec],
        handler: Callable[[KeyEvent], object],
        *,
        binding_id: str,
        intent: str,
        modes: tuple[str, ...] = (UI_MODE_GLOBAL,),
        allow_when_text_input: bool = False,
        allow_when_offline: bool = True,
        description: str = "",
        applies_when: Callable[[KeyEvent], bool] | None = None,
    ) -> ShortcutRegistration:
        """Register one shortcut definition (one or more ``KeySpec`` alternatives).

        Raises:
            ValueError: Unknown intent (with an HSM contract), a key unsupported on the
                backend, or a model-A conflict with a definition in the same scope.
        """
        if self.disposed:
            raise RuntimeError("binder has been disposed")
        if self._hsm_contract is not None:
            intent_ok, reason = self._hsm_contract.validate_intent(intent)
            if not intent_ok:
                raise ValueError(f"Unknown runtime shortcut intent: {intent} ({reason})")
        definition = KeyBindingDefinition(
            binding_id=binding_id,
            keys=tuple(keys) if not isinstance(keys, KeySpec) else (keys,),
            intent=intent,
            modes=modes,
            description=description,
            allow_when_text_input=allow_when_text_input,
            allow_when_offline=allow_when_offline,
        )
        for spec in definition.keys:
            spec.check_backend(self.backend)
        for existing in self._peer_definitions():
            if definitions_overlap(existing, definition):
                raise ValueError(
                    f"Keybinding conflict: {definition.binding_id!r} overlaps {existing.binding_id!r} "
                    "in at least one runtime context"
                )
        self.registry.register(definition)
        entry = (definition, handler, applies_when)
        self._entries.append(entry)

        def _remove() -> None:
            if entry in self._entries:
                self._entries.remove(entry)

        registration = ShortcutRegistration(definition, _remove)
        self._subscriptions.append(registration)
        return registration

    # -- runtime --------------------------------------------------------------------

    def build_context(self, widget: Any = None) -> KeybindingRuntimeContext:
        """Build the gating context for a key event on *widget* (focus widget if ``None``)."""
        focused = widget
        if focused is None:
            try:
                focused = self.anchor.focus_get()
            except Exception:
                focused = None
        text_input = bool(self._is_text_input(focused))
        dialog_open = bool(self._dialog_open())
        offline = bool(self._offline())
        return KeybindingRuntimeContext(
            active_mode=derive_active_mode(
                offline=offline, dialog_open=dialog_open, text_input_focused=text_input, base_mode=self._mode_provider()
            ),
            offline=offline,
            text_input_focused=text_input,
            dialog_open=dialog_open,
        )

    def handle(self, item: KeyDispatch) -> EventResult | None:
        """Run the applicable definition for *item*; ``None`` if no definition executed."""
        candidates = [e for e in list(self._entries) if any(matches(k, item.identity) for k in e[0].keys)]
        if not candidates:
            return None
        context = self.build_context(item.widget)
        for definition, handler, applies_when in candidates:
            if not self.registry.evaluate_runtime(definition, context)[0]:
                continue
            if applies_when is not None and not applies_when(item.event):
                return None
            try:
                result = coerce_result(handler(item.event))
            except Exception:
                if self._on_dispatch is not None:
                    self._on_dispatch(definition.intent, success=False)
                raise
            if self._on_dispatch is not None:
                self._on_dispatch(definition.intent, success=True)
            return result
        return None

    def channel_handler(self, item: KeyDispatch) -> EventResult:
        """Adapter for a key channel/router role (no execution -> ``NOT_HANDLED``)."""
        return self.handle(item) or EventResult.NOT_HANDLED

    def dispose(self) -> None:
        """Remove every registration of this binder (idempotent)."""
        self.disposed = True
        subscriptions, self._subscriptions = self._subscriptions, []
        for subscription in subscriptions:
            subscription.remove()
        self._entries.clear()


class _TagScopes:
    """Per-tag key channel shared by every window binder on that toplevel."""

    def __init__(self, root: Any, tag: str) -> None:
        self.channel = KeyChannel(root, tag)
        self.scopes: list[_ShortcutScope] = []
        self.channel.add(PHASE_SHORTCUT, self._dispatch)

    def _dispatch(self, item: KeyDispatch) -> EventResult:
        for scope in list(self.scopes):
            result = scope.handle(item)
            if result is not None:
                return result
        return EventResult.NOT_HANDLED


class WindowShortcutBinder(_ShortcutScope):
    """Shortcuts of one toplevel window (popups have their own binder).

    Args (keyword): ``registry``, ``hsm_contract`` (``validate_intent``),
    ``is_text_input`` (transitional override of the text-input contract),
    ``dialog_open``, ``offline``, ``mode_provider`` (base mode from domain state),
    ``on_dispatch(intent, success=...)``, ``backend``.
    """

    def __init__(self, window: Any, **kwargs: Any) -> None:
        super().__init__(window, **kwargs)
        self.window = window
        toplevel = window.tk_root if hasattr(window, "tk_root") else window.winfo_toplevel()
        self._tag = str(toplevel)
        runtime = runtime_for(toplevel)
        tags: dict[str, _TagScopes] = runtime.part("window_tags", lambda _rt: {})
        group = tags.get(self._tag)
        if group is None:
            group = tags[self._tag] = _TagScopes(interpreter_root(toplevel), self._tag)

            def _on_destroy(event: Any, *, _top: Any = toplevel, _tag: str = self._tag) -> None:
                if event.widget is not _top:
                    return
                removed = tags.pop(_tag, None)
                if removed is not None:
                    for scope in list(removed.scopes):
                        scope.dispose()
                    removed.channel.uninstall()

            toplevel.bind("<Destroy>", _on_destroy, add="+")
        self._group = group
        group.scopes.append(self)

    def _peer_definitions(self) -> Iterable[KeyBindingDefinition]:
        return [entry[0] for scope in self._group.scopes for entry in scope._entries]

    def dispose(self) -> None:
        if self in self._group.scopes:
            self._group.scopes.remove(self)
        super().dispose()


class ApplicationShortcutBinder(_ShortcutScope):
    """Cross-window shortcuts of the whole application (router role ``APP_SHORTCUT``).

    Fires for key events in every toplevel of the interpreter unless an earlier
    bindtag (widget, class, popup toplevel) consumed the event; popup overrides on a
    toplevel therefore win. Gating context is built from the event's widget. Several
    application binders may coexist; the model-A conflict check spans all of them.
    """

    def __init__(self, root: Any, **kwargs: Any) -> None:
        super().__init__(root, **kwargs)
        runtime = runtime_for(root)
        self._peers: list[_ShortcutScope] = runtime.part("app_scopes", lambda _rt: [])
        self._peers.append(self)
        self._subscriptions.append(router_for(root).register(ROLE_APP_SHORTCUT, self.channel_handler, owner=self))

    def _peer_definitions(self) -> Iterable[KeyBindingDefinition]:
        return [entry[0] for scope in self._peers for entry in scope._entries]

    def dispose(self) -> None:
        if self in self._peers:
            self._peers.remove(self)
        super().dispose()
