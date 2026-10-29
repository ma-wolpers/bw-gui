# DataGrid contract

`bw_gui.widgets.data_grid.DataGrid` is a virtualised, canvas-based table for
"many columns × tens of rows" views (e.g. a class × lesson-dates matrix). It
replaces keeping several `ttk.Treeview`s in sync: a Treeview re-lays out the
*whole* table on every visible change (a single heading update costs hundreds
of milliseconds at ~40 columns), a canvas only repaints the damaged area.

## Layout

- Three regions, left to right: `Region.LEFT` | `Region.SCROLL` | `Region.RIGHT`,
  separated by two splitter sashes (user-resizable). Initially LEFT and RIGHT get
  their natural width (RIGHT at most 45 %), SCROLL the rest.
- Every region has a header and a body; a horizontal scrollbar appears only
  while its content is wider than its pane. One vertical scrollbar for all.
- A row counts as visible only if it is fully visible in **every** region, so the
  vertical extent is the shortest body (a region with a horizontal scrollbar is
  shorter). Scrolling to the end, `see()` and the vertical scrollbar therefore
  never leave the last row under a scrollbar; when a body shrinks (the scrollbar
  appears, window/splitter resize), the top row is re-clamped.
- Wheel direction follows `WheelEvent.whole_steps` (positive = towards the
  content end); Shift/horizontal swipe scrolls the region under the pointer.
- Rows are one model for all regions (`top_row` is a single value), so the
  regions cannot drift apart vertically.

## Data and state (consumer → grid)

| Call | Effect | Render kind |
|---|---|---|
| `set_columns([GridColumn(key, title, width, region, anchor)])` | column set | content |
| `set_rows([GridRow(row_id, {key: text})])` | rows in display order (consumer sorts) | content |
| `set_cursor(row_id, column_key)` | selection band on the row, cell cursor and header marker on the column | markers |
| `set_sort_indicator(column_key, ascending)` | ▲/▼ in that header | content |
| `set_width_scale(f)` | global column-width zoom (all widths × f); unchanged value = no-op, so callers may pass it on every state update | content |
| `see(row_id, column_key=None)` | scroll so the row/column is visible; before the grid has its real size the target is kept and applied on the first real-size render | content only if something scrolled |
| `cell_bbox(row_id, column_key)` | `(body_widget, x, y, w, h)` after `see` + `flush_now` (inline editors) | — |

All calls only *mark* a render (`IdleRenderScheduler`): one render per idle
cycle, however many calls. **content** is a full pass over the visible cells
through `CanvasItemPool`s (unchanged cells cost no Tk calls); **markers** moves
only band, cursor and marker (a few `coords`). Text colours never depend on the
selection, so moving the cursor never touches cell texts. Budget: a cursor
move costs a small constant number of Tcl calls, independent of the column
count (`tests/test_data_grid_tk.py`).

## Events (grid → consumer)

- `on_cell_click(row_id, column_key | None, region)`, `on_cell_double_click(...)`,
  `on_header_click(column_key)`; clicks focus the clicked region's body.
- Wheel scrolls rows; Shift+wheel scrolls the region horizontally.
- The grid binds **no keys** (principle E). Consumers bind shortcuts on
  `grid.key_widgets` (the focusable bodies) via the keybinding contract and
  call `set_cursor`/`see` themselves; `grid.focus(column_key)` moves the focus
  to the region of a column.

## Theme

Colours come only from the ambient theme (principle A): band and header marker
`accent_soft`, cursor `accent`, text `fg_primary`, header `bg_panel`, lines
`border`. A theme switch re-renders; the grid's theme listener ends with its frame.

## Building blocks (reusable)

- `bw_gui.runtime.idle_render.IdleRenderScheduler(owner)`: `mark(key, render)`,
  `flush_now()`; cancelled when *owner* is destroyed.
- `bw_gui.widgets.canvas_item_pool.CanvasItemPool(canvas, kind)`: `begin()`,
  `place(coords, **options)`, `end()`; sends only differences, hides unused items.
- `bw_gui.testing.tcl_calls.count_tcl_calls(action)`: deterministic call budgets.
