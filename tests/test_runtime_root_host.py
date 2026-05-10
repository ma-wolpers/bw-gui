from bw_gui.runtime.root_host import TkRootHost


class _FakeRoot:
    def __init__(self):
        self.title = "Root"

    def geometry(self):
        return "1200x800"


def test_tk_root_host_exposes_composed_root():
    fake_root = _FakeRoot()
    host = TkRootHost(root=fake_root)

    assert host.tk_root is fake_root


def test_tk_root_host_delegates_unknown_attributes():
    fake_root = _FakeRoot()
    host = TkRootHost(root=fake_root)

    assert host.title == "Root"
    assert host.geometry() == "1200x800"
