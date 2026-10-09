# Screen Placement Contract

bw-gui is the only place that knows where popups, menus, tooltips, flyouts and drag
ghosts go on a multi-monitor desktop. Consumer apps never clamp positions with
`winfo_screenwidth`/`winfo_screenheight`: on Windows these report only the primary
monitor.

| Module | Responsibility |
|---|---|
| `bw_gui.contracts.screen_geometry` | pure geometry: `Point`, `Size`, `Rect`, `MonitorInfo`, `Side`, `Placement`, `select_monitor`, `calculate_overlay_placement`, `calculate_clamped_position`, `round_rect_inward` |
| `bw_gui.runtime._win_monitors` | the only Win32 caller for monitor geometry (`EnumDisplayMonitors`, `GetMonitorInfoW`, `GetAncestor`, `GetWindowRect`) |
| `bw_gui.runtime.screen_placement` | the only Tk accesses: `get_monitor_info`, `measure_overlay`, `apply_window_position`, `widget_rect`, `place_overlay_now` |

`bw_gui.runtime.platform.get_monitor_bounds` and `center_window_over_parent` remain as
compatibility wrappers.

## Coordinates and DPI

- **Values:** All values are integer **Tk root coordinates of the virtual desktop**, the same values `winfo_rootx/rooty` and `wm geometry` use.
- **Origin:** the top-left corner of the primary monitor. Negative values are valid (a monitor left of or above the primary one).
- **Rectangles** are half-open: `[left, right) x [top, bottom)`.
- **DPI:** pixels in the DPI awareness context of the Tk process.
  - **Spike, 2026-10-09** (Win11, Tk 8.6, two monitors, second one at `x=1920` with its own task bar): Tk runs DPI-unaware (thread context 0). Win32 calls from the same thread return the same virtualised coordinates (`GetWindowRect` of the frame equals `wm geometry`; negative positions work), so no conversion is needed.
  - `_win_monitors` never changes the thread's DPI context. If a conversion ever becomes necessary it lives only there, and monitor rectangles are rounded **inward** (`ceil` left/top, `floor` right/bottom) via `round_rect_inward`.

## `get_monitor_info(target, *, tk_context) -> MonitorInfo(bounds, work_area, source, primary)`

- **`tk_context`:** any live widget of the interpreter. It supplies the Tk-screen fallback and is mandatory, also for points.
- **`target`:** a `Point`, a `Rect` or a **mapped** widget. A widget is resolved via `winfo_toplevel()` and `GetAncestor(GA_ROOT)` to the native frame rectangle. An unmapped widget raises `ValueError`.
- **Rect rule:**
  1. the monitor containing the centre
  2. otherwise the largest intersection
  3. otherwise the nearest monitor
  4. ties: the primary monitor first, then the smaller `left`, then the smaller `top`
- **Fallback:**
  - Non-Windows backends: `bounds = work_area = (0, 0, screenwidth, screenheight)` with `source=TK_SCREEN`. Under X11 this usually spans all monitors, so there is no per-monitor placement and no task-bar knowledge.
  - A failed Win32 query: the same rectangle with `source=FALLBACK` and one warning per process. In practice this is the primary monitor.
  - `MonitorQueryError` is raised only when even the Tk-screen fallback is impossible (the interpreter is gone).

## `calculate_overlay_placement(*, anchor, size, monitor, placement, gap=0, margin=8) -> Placement`

Pure: no Tk, no IO, deterministic.

- **`placement` is a priority list** of `below`, `above`, `right`, `left`, `center_over`.
  - Each candidate is aligned to the anchor on its main axis and shifted into the work area on the cross axis.
  - The first candidate that lies completely inside the work area (shrunk by `margin`) wins. There is no implicit flip outside the list.
  - `gap` is the distance to the anchor; `margin` only applies to the work-area edges.
- **No side fits:**
  - The side with the largest visible area wins (ties: list order).
  - It is clamped, and the result reports `fits=False` and `overflow` (the size that sticks out).
  - This holds even if the clamp pulls the box fully inside, in which case it covers the anchor.
- **Overlay larger than the work area:** its left/top edge sits on `work_area + margin`; the overflow goes right/down.
- **Invariants:**
  - The top-left corner is always inside the work area.
  - The size is never changed.
  - There is no "slightly outside is fine".
- **`center_over`:** centres over the anchor, then clamps.
- **Anchor partly off-screen:** allowed. An overlay detached from its anchor is accepted; visibility wins over adjacency.
- **`Placement.size`:** records the size the placement was computed for. A placement is valid only for that size.

## `calculate_clamped_position(*, desired, size, bounds, margin=0) -> Point`

A separate primitive for objects that follow the pointer, for example the drag ghost. It has no side, no flip and no anchor.

- **Pure:** no Tk, no IO, deterministic.
- **Axes:** each axis is clamped independently into `[bounds.left + margin, bounds.right - margin - size.width]` (vertically likewise).
- **Box larger than the area:** if the box is larger than the area on an axis, its left/top edge sits on `bounds + margin`.
- **Bounds:** the consumer passes the work area of the monitor under the cursor point.

## Applying

- **`apply_window_position(window, position)`:**
  - Writes `+x+y` only, never the size. Call it before showing the window.
  - Raises `ValueError` if the window was destroyed.
  - It is a one-shot call with no follow-up on monitor or size changes.
- **`place_overlay_now(window, *, anchor, placement, tk_context=None, gap=0, margin=8, max_size_policy=None)`** is the documented composition:
  1. Measure the natural size.
  2. Resolve the anchor's monitor.
  3. Calculate the placement.
  4. If the overlay overflows and `max_size_policy` is given: call it with the maximum size (work area minus `2*margin`) so the consumer can limit the window, for example cap a menu's height and let it scroll.
  5. **Re-measure and recalculate** with the same monitor information.
  6. Apply the position.

  Before applying, `RuntimeError` is raised if the size no longer matches the placement. A stale placement is never applied.

## Tk quirk (measured)

On Windows, `lift()` of a not-yet-mapped `overrideredirect` Toplevel resets an already
applied `+x+y` to `+0+0` (Tk 8.6, 2026-10-09). Call `lift()` before applying the
position, as `CustomMenuBar` does.

## Consumers

| Consumer | Placement |
|---|---|
| `center_window_over_parent` | `center_over`, margin 0, parent's work area |
| `HoverTooltip` | `(below, above)`, gap 8 |
| Menu popups, level 0 | `(below, above)`, margin 0 |
| Submenus and description flyouts | `(right, left)`, gap -1 (one-pixel overlap as before), margin 0 |
| Popups taller than the work area | capped and scrolling (`ScrollableFrame`) |
| Drag ghost (`DragDropController`) | `calculate_clamped_position` at cursor + (12, 8), cursor monitor's work area; colours from the active theme |

Native `tk_popup` menus are positioned by Windows itself and are not affected.
