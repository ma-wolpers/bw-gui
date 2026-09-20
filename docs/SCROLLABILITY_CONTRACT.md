# Scrollability Contract

This document defines bw-gui's convention for when and how content areas scroll.

> **Ownership rule:** `bw_gui.widgets.ScrollableFrame` is the sole shared
> scroll mechanism (Canvas + Scrollbar + scrollregion + mousewheel) for
> embedded, non-popup content. `bw_gui.dialogs.ScrollablePopupWindow` is the
> sole shared popup host with scrolling, and builds directly on
> `ScrollableFrame` internally rather than maintaining its own parallel
> Canvas/Scrollbar implementation. Consumer apps must not hand-roll a third
> Canvas+Scrollbar+mousewheel combination for a popup or an embedded panel -
> use these two instead, or extend them if they are missing something.

## The invariant

> **No relevant content may become unreachable because of a limited
> window/viewport size.**

This is *not* the same as "every window needs a scrollbar". A window whose
content is guaranteed to always fit (a small confirmation dialog with two
buttons, say) needs none. The point is that scrollability is the **default**
posture for anything that *could* outgrow its available space - not an
optimization added later once content "happens to no longer fit". Building
a popup or panel without scroll support because its content currently fits
is not, by itself, a justified exception: a later addition to that same
popup/panel (one more form field, one more Kategorie, one more Aufgabe)
would silently reintroduce the exact "can't see everything, have to resize
the window" problem this contract exists to prevent.

## Defaults

| Shape | Default |
|---|---|
| Popup / Dialog | `bw_gui.dialogs.ScrollablePopupWindow` |
| Embedded content area / Pane / Panel (not a popup) | `bw_gui.widgets.ScrollableFrame` |

Both are opt-out, not opt-in: reach for them first, and only skip them with
a documented reason (see below).

## Exceptions

A popup or panel may skip these defaults when:

- **it already scrolls internally in a way an outer wrapper would only
  compete with** - e.g. a popup combining a self-scrolling graph `Canvas`
  with a separately scrolled sidebar (see
  `ScrollablePopupWindow(..., scrollable=False)`, and Kursplaner's
  `kompetenzgraph_dialog.py` for a real example: the sidebar gets its own
  small Canvas+Scrollbar wrapper, `kompetenzgraph_sidebar_scroll.py`,
  precisely so the outer popup does not also try to own scrolling); or
- **all its content is structurally guaranteed to always fit** (a short,
  fixed confirmation dialog).

"Nobody has reported it as broken yet" and "the content currently fits" are
**not** valid exceptions on their own - both are true right up until the
next field/row/section is added. Document the actual reason in the
consuming app (a code comment on the popup/panel construction site is
enough; this file does not need to enumerate every consumer's exceptions).

`BwBaseWindow` deliberately does **not** wrap every view in a
`ScrollableFrame` automatically - each view decides for itself whether it
has a content area that needs one, the same way each view decides its own
layout.

## `ScrollableFrame`

A real `ttk.Frame` subclass (not a delegating wrapper) - it can be placed
anywhere a plain `ttk.Frame` could, including as a `PanedWindow` pane via
`paned.add(scrollable_frame, weight=...)`. `.content` is the actual target
`ttk.Frame` for building content into.

```python
from bw_gui.widgets import ScrollableFrame

panel = ScrollableFrame(parent_paned_window, style="Surface.TFrame")
parent_paned_window.add(panel, weight=2)

widgets.Label(panel.content, text="...").pack(fill="x")
```

Geometry contract:

- Content height grows -> the Canvas `scrollregion` grows to match.
- Canvas/viewport width changes (window resize, `PanedWindow` splitter
  drag) -> `.content`'s width is kept equal to the canvas width.
- Content taller than the viewport -> the mousewheel scrolls it; content
  shorter than or equal to the viewport -> the mousewheel handler is a
  no-op.

**Mousewheel dispatch** is centralized, not per-instance: exactly one
`bind_all("<MouseWheel>")` per Tk interpreter (not per `Toplevel` - several
`Toplevel` windows under one `Tk()` application share a single interpreter
and therefore a single `"all"` bindtag), lazily registered by whichever
`ScrollableFrame` is constructed first under that interpreter. The shared
handler resolves the actual event-target widget's enclosing `ScrollableFrame`
by walking its `.master` chain, so any number of simultaneously visible
instances - nested or side-by-side - never clobber each other's binding,
and a wheel event over a *child* widget inside `.content` (a button, an
entry, not just bare canvas background) still resolves correctly.

Vertical-only by design - see "Horizontal scrolling" below.

## `ScrollablePopupWindow`

Unchanged public contract from before this document existed: construct
with `title`/`geometry`/`minsize`/`theme_key`/`scrollable` (default
`True`), build into `.content`. Internally, the `scrollable=True` case is
now just `self._scroll = ScrollableFrame(self)`; `scrollable=False` stays a
plain `Frame` for popups that manage their own internal scrolling (see
Exceptions above).

## Horizontal scrolling

A repo-wide audit (bw-gui, korrektor, blattwerk, namenfit, Kursplaner) for
`xview`/`xscrollcommand`/horizontal-scroll usage before this contract was
written found:

- **No consumer anywhere relies on `ScrollablePopupWindow`'s previous
  horizontal scrollbar** (`_h_scroll`). It was already functionally dead
  there: `_on_canvas_configure` always forced content width to match
  canvas width, so there was never anything to scroll horizontally. It has
  been removed; `ScrollableFrame` is vertical-only.
- **Kursplaner has its own, separate, actively-used horizontal-scroll
  architecture** for its spreadsheet-like grid `Canvas`
  (`kursplaner/adapters/gui/grid_viewport_sync.py`, guarded by its own
  `tests/test_horizontal_scroll_architecture_guard.py`). This is unrelated
  to `ScrollablePopupWindow`/`ScrollableFrame` - a different widget shape
  entirely (a data grid, not a popup or a simple content panel) - and is
  untouched by this contract.
- **Kursplaner *does* use `ScrollablePopupWindow` productively**, across
  roughly a dozen dialogs (`kursplaner/adapters/gui/popup_window.py`
  subclasses it directly). None of them reference its internal
  Canvas/Scrollbar attributes - only the public `.content`/`scrollable`/
  theme-hook contract, which this refactor preserves exactly.

Should a real horizontal-scroll need for `ScrollableFrame`/
`ScrollablePopupWindow` specifically (not a bespoke widget like Kursplaner's
grid) appear later, it belongs in `ScrollableFrame` once, not duplicated
across the two classes again.

## What not to do

- Do not build a second Canvas+Scrollbar+mousewheel implementation in a
  consumer app for a popup or a simple embedded panel - use these two
  classes.
- Do not add a third shared scroll primitive to bw-gui. `ScrollableFrame`
  is the scroll mechanism; `ScrollablePopupWindow` is the popup host built
  on it; that is the complete set.
