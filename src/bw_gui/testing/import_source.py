"""Consumer-side check that ``bw_gui`` is imported from the sibling checkout.

Every consumer app loads bw-gui from a sibling checkout (``<repo>/../bw-gui/src``,
or ``../../bw-gui/src`` for apps nested one level deeper such as Kartograph).
Old nested copies (``<repo>/bw-gui``) must never be picked up, otherwise
development and tests silently run against different bw-gui versions. See
``docs/CONSUMER_SETUP.md``.

Usage in a consumer test::

    from bw_gui.testing.import_source import assert_bw_gui_from_sibling

    def test_bw_gui_import_source():
        assert_bw_gui_from_sibling(REPO_ROOT)
"""

from __future__ import annotations

from pathlib import Path


def sibling_candidates(repo_root: Path) -> tuple[Path, ...]:
    """Return the accepted sibling ``bw-gui/src`` locations for *repo_root*.

    Args:
        repo_root: Root directory of the consumer repository.

    Returns:
        The resolved candidate directories, nearest sibling first.
    """
    root = Path(repo_root).resolve()
    return (
        (root.parent / "bw-gui" / "src").resolve(),
        (root.parent.parent / "bw-gui" / "src").resolve(),
    )


def assert_bw_gui_from_sibling(repo_root: Path) -> Path:
    """Assert that the imported ``bw_gui`` package comes from a sibling checkout.

    Args:
        repo_root: Root directory of the consumer repository.

    Returns:
        The ``src`` directory the package was actually loaded from.

    Raises:
        AssertionError: If ``bw_gui`` lives inside ``repo_root`` (a nested copy)
            or outside every accepted sibling location.
    """
    import bw_gui

    package_file = Path(bw_gui.__file__).resolve()
    root = Path(repo_root).resolve()
    nested = root / "bw-gui"
    assert not package_file.is_relative_to(nested), (
        f"bw_gui wird aus der verschachtelten Kopie {nested} geladen statt aus dem Geschwister-Checkout"
    )
    for candidate in sibling_candidates(root):
        if package_file.is_relative_to(candidate):
            return candidate
    raise AssertionError(
        f"bw_gui stammt aus {package_file}, erwartet wird einer von "
        f"{[str(c) for c in sibling_candidates(root)]}"
    )
