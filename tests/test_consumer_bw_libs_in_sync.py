"""``bw_libs`` liegt als Kopie in jedem Programm: Gleichnamige Dateien müssen überall gleich sein.

Die Datei kann nicht aus bw-gui kommen, weil sie bw-gui erst auffindbar macht. Darum prüft
dieser eine Test alle Geschwister-Checkouts, statt in jedem Programm eine Prüfung zu halten.
Ohne Geschwister (z. B. in einer CI) wird er übersprungen.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pytest

BW_GUI_ROOT = Path(__file__).resolve().parents[1]


def _sibling_bw_libs() -> list[Path]:
    """Findet ``bw_libs`` in Programmen neben bw-gui, auch eine Ebene tiefer (``tools4school/...``)."""
    parent = BW_GUI_ROOT.parent
    return sorted(p for pattern in ("*/bw_libs", "*/*/bw_libs") for p in parent.glob(pattern) if p.is_dir())


def _text_variants() -> dict[str, dict[bytes, list[str]]]:
    """Ordnet jeder relativen Datei ihre Textvarianten mit den Programmen zu (Zeilenenden egal)."""
    variants: dict[str, dict[bytes, list[str]]] = defaultdict(lambda: defaultdict(list))
    for root in _sibling_bw_libs():
        for path in root.rglob("*.py"):
            text = path.read_bytes().replace(b"\r\n", b"\n")
            variants[path.relative_to(root).as_posix()][text].append(root.parent.name)
    return variants


def test_bw_libs_copies_are_identical_across_programs():
    if len(_sibling_bw_libs()) < 2:
        pytest.skip("keine Geschwister-Checkouts vorhanden")
    drifted = {name: list(texts.values()) for name, texts in _text_variants().items() if len(texts) > 1}
    assert not drifted, f"bw_libs auseinandergelaufen: {drifted}"
