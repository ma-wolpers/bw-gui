from bw_gui.widgets.drag_drop import DragDropController


class _FakeWidget:
    """Minimal stand-in for a Tk widget: only `str()` identity and `.master` chain matter."""

    def __init__(self, path: str, master: "_FakeWidget | None" = None) -> None:
        self._path = path
        self.master = master

    def __str__(self) -> str:
        return self._path


def test_resolve_drop_callback_finds_directly_registered_target() -> None:
    target = _FakeWidget(".target")
    calls: list[object] = []
    targets = {str(target): (target, calls.append)}

    callback = DragDropController._resolve_drop_callback(target, targets)

    # Bound methods aren't `is`-stable across attribute accesses even for
    # the same underlying object - compare by (in)equality instead, which
    # bound methods define as __self__/__func__ equality.
    assert callback == calls.append


def test_resolve_drop_callback_walks_up_parent_chain_to_find_target() -> None:
    target = _FakeWidget(".target")
    child = _FakeWidget(".target.label", master=target)
    grandchild = _FakeWidget(".target.label.icon", master=child)
    calls: list[object] = []
    targets = {str(target): (target, calls.append)}

    callback = DragDropController._resolve_drop_callback(grandchild, targets)

    assert callback == calls.append


def test_resolve_drop_callback_returns_none_when_no_target_registered() -> None:
    unrelated = _FakeWidget(".somewhere.else")

    callback = DragDropController._resolve_drop_callback(unrelated, {})

    assert callback is None


def test_resolve_drop_callback_returns_none_for_none_widget() -> None:
    assert DragDropController._resolve_drop_callback(None, {}) is None


def test_resolve_drop_callback_picks_nearest_registered_ancestor() -> None:
    """A widget nested inside two registered targets resolves to the nearer (child) one."""
    outer_target = _FakeWidget(".outer")
    inner_target = _FakeWidget(".outer.inner", master=outer_target)
    leaf = _FakeWidget(".outer.inner.leaf", master=inner_target)
    outer_calls: list[object] = []
    inner_calls: list[object] = []
    targets = {
        str(outer_target): (outer_target, outer_calls.append),
        str(inner_target): (inner_target, inner_calls.append),
    }

    callback = DragDropController._resolve_drop_callback(leaf, targets)

    assert callback == inner_calls.append


def test_register_target_and_unregister_target_round_trip() -> None:
    controller = DragDropController.__new__(DragDropController)
    controller._targets = {}
    widget = _FakeWidget(".target")

    controller.register_target(widget, on_drop=lambda payload: None)
    assert str(widget) in controller._targets

    controller.unregister_target(widget)
    assert str(widget) not in controller._targets
