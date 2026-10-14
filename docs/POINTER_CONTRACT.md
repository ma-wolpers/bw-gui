# Pointer Contract

bw-gui is the only place that interprets Tk's wheel `delta`, X11 wheel buttons and
pointer `state` bits. Consumers bind semantic hooks and never see `event.delta`,
`event.num`, `event.state` or Tk sequence strings.

| Module | Responsibility |
|---|---|
| `bw_gui.contracts.pointer` | pure: `wheel_steps`, `StepAccumulator`, `WheelEvent`, `ClickEvent`, `DragEvent`, `Axis`, `Button`, `CancelReason`, `wheel_axis` |
| `bw_gui.runtime.pointer` | Tk side: `bind_wheel`, `bind_click`, `bind_drag` |
| `bw_gui.runtime.scroll_resolver` | the single wheel handler for `ScrollableFrame` on the router-owned `all` tag |

Every hook binds on the widget's `bwkeys:<path>` tag (before its class bindings) and returns a `Subscription`.

- **Lifecycle:** `remove()` is idempotent, and the subscription is invalidated when the widget is destroyed.
- **Handler return:** handlers return `EventResult`. `HANDLED` stops the Tk event, which also keeps an enclosing `ScrollableFrame` from scrolling.

## Wheel

- **`steps`:** continuous, unit "notch" (1.0 = one detent of a standard wheel), positive towards the content end (down/right).
  - win32: `-delta / 120`
  - x11: button 4 → `-1`, button 5 → `+1`
  - aqua: `-delta` (not verified live)
- **`whole_steps`:** discrete. Per subscription and axis: `acc += steps; whole = trunc(acc); acc -= whole`.
  - There is no time limit and no reset on a direction change; a counter-movement reduces the remainder.
  - The accumulator is dropped only with the subscription.
  - The former 400 ms idea was an unfounded number. Mouse wheels report whole notches, so the remainder is always 0; only touchpads leave remainders, and for them net accumulation matches the physical movement.
- **`axis`:** always `VERTICAL`. Tk 8.6 on Windows does not distinguish horizontal tilt from Shift+wheel. `wheel_axis(event, shift_means_horizontal=True)` makes the Shift interpretation explicit at the consumer.

## Click

`bind_click(widget, handler, *, button=PRIMARY, count=1|2)` uses Tk's own multi-click recognition (system double-click time and radius) via an internal raw sequence. This is gesture recognition, not a shortcut decision.

- On a double click, `count=1` fires for the first press and `count=2` for the second.
- Without a `count=2` subscription, the second press is a normal `count=1` press.

## Drag

`bind_drag(widget, *, on_start, on_move, on_end, on_cancel, button, threshold=0, cancel_on_escape=False)`:

- **Press:** creates a candidate. `on_start` fires at press (threshold 0) or when the threshold is first exceeded.
- **Grab:** Tk's implicit grab delivers motion and release across widget and window borders. bw-gui never calls `grab_set`.
- **Release:** also outside the widget, gives `on_end` with valid root coordinates.
- **Modifiers:** `start_modifiers` is frozen at press; `modifiers` is the current state.
- **Cancel:**
  - Focus loss of the toplevel gives `on_cancel(FOCUS_LOST)`.
  - With `cancel_on_escape`, a temporary gesture subscription exists while the drag is active. Every bw-gui key dispatcher (`bwkeys:*`, toplevel, `all`) checks it before all roles, so an exact Escape cancels regardless of focus within the toplevel. The subscription is removed on end, cancel, exception and destroy, and it never appears in shortcut conflict analysis.
  - Limit: a native class binding that consumes Escape earlier would win.
- **Destroy:** the widget being destroyed silently discards the state.
- **Exceptions:** an exception in a callback resets the drag (reported by Tk); no further callback of that drag runs.
- **Re-entrancy:** callbacks may destroy the widget but must not start a new drag.

## Scroll resolver (`ScrollableFrame`)

The candidate is the **nearest registered `ScrollableFrame` along the widget hierarchy**. Registration order plays no role.

1. **Search boundary:** from `event.widget` upwards to and including its toplevel, never beyond (bugfix 10).
2. **Native widgets first:**
   - `Text`, `Listbox` and `ttk.Treeview` that can scroll in the wheel direction are responsible.
   - Scrollbars and comboboxes always consume the wheel.
   - So does any widget with its own `bind_wheel`.

   Tk's class bindings of these widgets do not `break`, so before this rule a surrounding frame scrolled as well (bugfix 8, measured).
3. **Nearest overflowing frame:** the nearest frame that overflows on its axis scrolls by the accumulated whole notches. A frame that does not overflow passes the wheel outward (deliberate change). There is no chaining at the content end.
4. **Own frame parts:** wheel events on a frame's outer frame or own scrollbar resolve to that frame (bugfix 9).
5. **No candidate:** nothing happens.
