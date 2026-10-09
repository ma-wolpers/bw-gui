from pathlib import Path

import pytest

from bw_gui.testing import import_source


def _fake_package(monkeypatch, file_path: Path):
    import bw_gui

    monkeypatch.setattr(bw_gui, "__file__", str(file_path))


def test_accepts_direct_sibling(tmp_path, monkeypatch):
    repo = tmp_path / "app"
    _fake_package(monkeypatch, tmp_path / "bw-gui" / "src" / "bw_gui" / "__init__.py")
    assert import_source.assert_bw_gui_from_sibling(repo) == (tmp_path / "bw-gui" / "src").resolve()


def test_accepts_grandparent_sibling(tmp_path, monkeypatch):
    repo = tmp_path / "tools" / "app"
    _fake_package(monkeypatch, tmp_path / "bw-gui" / "src" / "bw_gui" / "__init__.py")
    assert import_source.assert_bw_gui_from_sibling(repo) == (tmp_path / "bw-gui" / "src").resolve()


def test_rejects_nested_copy(tmp_path, monkeypatch):
    repo = tmp_path / "app"
    _fake_package(monkeypatch, repo / "bw-gui" / "src" / "bw_gui" / "__init__.py")
    with pytest.raises(AssertionError, match="verschachtelten"):
        import_source.assert_bw_gui_from_sibling(repo)


def test_rejects_unrelated_location(tmp_path, monkeypatch):
    _fake_package(monkeypatch, tmp_path / "elsewhere" / "bw_gui" / "__init__.py")
    with pytest.raises(AssertionError, match="erwartet"):
        import_source.assert_bw_gui_from_sibling(tmp_path / "x" / "app")
