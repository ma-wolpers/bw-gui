"""ttk styles, state matrix and image lifecycle for Checkbox and Switch (private).

Called once per theme switch from ``configure_ttk_theme``; consumers never call
anything here. The rules implemented below are specified in
``docs/TOGGLE_CONTRACT.md`` (sections "Visual states" and "Scaling"):

* **State matrix**: ``resolve()`` is the single source of truth for which image a
  combination of ttk states shows. The ttk state specs are *generated* from it
  (``state_specs()``), so priority never depends on code order.
* **Image objects**: one ``PhotoImage`` per (control, image key) and Tk interpreter,
  kept alive by ``_IMAGES`` and reconfigured *in place* on every theme or density
  change. ttk image elements reference images by name, so the elements never need
  to be recreated.
* **Elements**: created once per interpreter and *actually active* ttk theme, checked
  via ``style.element_names()``.
* **Relayout**: ttk does not re-measure widgets when an image changes size in place;
  the ``style.configure`` calls *after* the image update fire ``<<ThemeChanged>>``,
  which does. Keep that order.
"""

from __future__ import annotations

import tkinter as tk
from itertools import product
from tkinter import ttk

from ._toggle_assets import CONTROLS, OVERLAYS, density_for_scaling, image_data, image_keys

STATES = ("disabled", "alternate", "selected", "active", "pressed", "focus")
STYLE_NAMES = {"checkbox": "Checkbox.TCheckbutton", "switch": "Switch.TCheckbutton"}
ELEMENT_NAMES = {"checkbox": "Checkbox.indicator", "switch": "Switch.indicator"}
LABEL_GAP = 6  # pixels between indicator and label at density 1.0

# (control, image_key) -> PhotoImage, per Tk interpreter. Strong references keep the
# images alive for as long as their interpreter; dropped when its root is destroyed.
_IMAGES: dict[object, dict[tuple[str, str], tk.PhotoImage]] = {}
_LAST_DATA: dict[object, dict[tuple[str, str], str]] = {}


def resolve(states: frozenset[str] | set[str]) -> str:
    """Return the image key a set of ttk states must display.

    Priority (documented in the contract): shape from ``alternate`` > ``selected`` >
    off; ``disabled`` wins over every overlay and yields the muted shape; otherwise
    hover when ``active`` or ``pressed`` (``pressed`` is intentionally identical to
    ``active``), focus ring when ``focus``.

    Args:
        states: Any subset of ``STATES``.

    Returns:
        An image key such as ``"on-hover_focus"`` or ``"mixed-muted"``.
    """
    shape = "mixed" if "alternate" in states else "on" if "selected" in states else "off"
    if "disabled" in states:
        return f"{shape}-muted"
    hover = "active" in states or "pressed" in states
    focus = "focus" in states
    overlay = "hover_focus" if hover and focus else "hover" if hover else "focus" if focus else "rest"
    return f"{shape}-{overlay}"


def state_specs() -> list[tuple[tuple[str, ...], str]]:
    """Generate ttk ``(states..., image_key)`` specs in first-match priority order.

    Specs only use positive states; ordering from most to least specific makes the
    first matching spec equal ``resolve()`` for every one of the 64 state
    combinations (verified by the test suite). The last entry (``()``, off-rest) is
    the element's default image.
    """
    shape_specs = [(("disabled", "alternate"), "mixed"), (("disabled", "selected"), "on"), (("disabled",), "off"),
                   (("alternate",), "mixed"), (("selected",), "on"), ((), "off")]
    overlay_specs = [(("active", "focus"), "hover_focus"), (("pressed", "focus"), "hover_focus"),
                     (("active",), "hover"), (("pressed",), "hover"), (("focus",), "focus"), ((), "rest")]
    specs: list[tuple[tuple[str, ...], str]] = []
    for shape_states, shape in shape_specs:
        if "disabled" in shape_states:
            specs.append((shape_states, f"{shape}-muted"))
            continue
        for overlay_states, overlay in overlay_specs:
            specs.append((shape_states + overlay_states, f"{shape}-{overlay}"))
    return specs


def first_match(specs: list[tuple[tuple[str, ...], str]], states: frozenset[str] | set[str]) -> str:
    """Emulate ttk's first-match lookup over *specs* (used by the tests)."""
    return next(key for spec_states, key in specs if set(spec_states) <= set(states))


def all_state_combinations() -> list[frozenset[str]]:
    """All 2**6 subsets of ``STATES``."""
    return [frozenset(s for s, on in zip(STATES, flags) if on) for flags in product((0, 1), repeat=len(STATES))]


def toggle_image(widget: tk.Misc, control: str, image_key: str) -> tk.PhotoImage:
    """Return the shared, themed ``PhotoImage`` for one indicator state.

    Used by the menu surfaces to show the same glyphs as the widgets. If
    ``configure_ttk_theme`` has not run for the widget's interpreter yet (e.g. a
    startup dialog with a native menu that only calls ``apply_window_theme``), the
    images are built on demand from the current global theme; the next
    ``configure_ttk_theme`` then updates them in place like always.
    """
    root = widget._root()
    if root.tk not in _IMAGES:
        from ._theme_manager import get_theme  # late import: theme manager imports this module lazily too
        _update_images(root, get_theme(), density_for_scaling(float(root.tk.call("tk", "scaling"))))
    return _IMAGES[root.tk][(control, image_key)]


def _images_for(root: tk.Tk) -> dict[tuple[str, str], tk.PhotoImage]:
    """Return (creating on first use) the image registry of *root*'s interpreter."""
    interp = root.tk
    if interp not in _IMAGES:
        _IMAGES[interp] = {
            # No width/height: a fixed size would clip later data; unsized photos
            # grow and shrink with every in-place configure(data=...).
            (control, key): tk.PhotoImage(master=root)
            for control in CONTROLS for key in image_keys()
        }
        _LAST_DATA[interp] = {}

        def _forget(event: tk.Event, interp=interp, root=root) -> None:
            if event.widget is root:
                _IMAGES.pop(interp, None)
                _LAST_DATA.pop(interp, None)

        root.bind("<Destroy>", _forget, add="+")
    return _IMAGES[interp]


def _update_images(root: tk.Tk, theme: dict[str, str], density: float) -> dict[tuple[str, str], tk.PhotoImage]:
    """Reconfigure every toggle image of *root*'s interpreter in place."""
    images = _images_for(root)
    last = _LAST_DATA[root.tk]
    for (control, key), photo in images.items():
        data = image_data(theme, control, key, density)
        if last.get((control, key)) != data:
            photo.configure(format="png", data=data)
            last[(control, key)] = data
    return images


def _ensure_elements(style: ttk.Style, images: dict[tuple[str, str], tk.PhotoImage], density: float) -> None:
    """Create the indicator elements in the active ttk theme if they are missing.

    The label gap (element padding) is fixed at creation time for the density active
    then; later density changes resize the images but keep that gap - elements cannot
    be reconfigured and are deliberately never recreated.
    """
    existing = set(style.element_names())
    specs = state_specs()
    for control, element in ELEMENT_NAMES.items():
        if element in existing:
            continue
        default = images[(control, specs[-1][1])]
        mapped = [(*spec_states, images[(control, key)]) for spec_states, key in specs[:-1]]
        style.element_create(element, "image", default, *mapped,
                             padding=(0, 0, round(LABEL_GAP * density), 0), sticky="")


def configure_toggle_styles(widget: tk.Misc, style: ttk.Style, theme: dict[str, str]) -> None:
    """Apply the current theme to the Checkbox/Switch styles (called per theme switch).

    Order matters: images first (in place), then elements (only if missing in the
    active ttk theme), then ``style.configure``/``style.map`` - the latter fires
    ``<<ThemeChanged>>`` so widgets re-measure after a density change.

    Args:
        widget: Any widget of the target interpreter.
        style:  The ``ttk.Style`` of that interpreter (active ttk theme already set).
        theme:  Resolved bw-gui theme dict.
    """
    root = widget._root()
    density = density_for_scaling(float(root.tk.call("tk", "scaling")))
    images = _update_images(root, theme, density)
    _ensure_elements(style, images, density)
    for control, style_name in STYLE_NAMES.items():
        style.layout(style_name, [("Checkbutton.padding", {"sticky": "nswe", "children": [
            (ELEMENT_NAMES[control], {"side": "left", "sticky": ""}),
            ("Checkbutton.label", {"side": "left", "sticky": "nswe"}),
        ]})])
        # No padding here: it is inherited from TCheckbutton, which apps tune for their
        # UI density (e.g. Blattwerk's compact mode) - setting it would override that.
        style.configure(style_name, background=theme["bg_main"], foreground=theme["fg_primary"])
        style.map(style_name,
                  background=[("active", theme["bg_main"]), ("disabled", theme["bg_main"])],
                  foreground=[("disabled", theme["fg_muted"])])


__all__ = ["OVERLAYS", "STATES", "STYLE_NAMES", "all_state_combinations", "configure_toggle_styles",
           "first_match", "resolve", "state_specs", "toggle_image"]
