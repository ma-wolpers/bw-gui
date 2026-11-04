# CardBoard Contract

`bw_gui.widgets.card_board.CardBoard`: a board of **rows × lanes**. A `CARDS` lane holds an
ordered stack of cards per row, a `TEXT` lane one free text per row. Cards are dragged
between cells with a coloured **insertion line** that shows where the card would land.

## Division of labour

| The board does | The consumer does |
|---|---|
| layout, word wrap, rendering in theme colours (tokens, row tints via `tinted_color`) | owns all data and rebuilds `BoardRow`s after every change |
| reports gestures: cursor change, double click, "+" click, drop, text commit | applies rules (where a card may go, uniqueness, naming, undo) |
| keeps its own keyboard **cursor** (card key or cell) | binds every key on `key_widget` (principle E: the board binds none) |
| offers `move_cursor(direction)` (pure navigation) and `see(cursor)` | decides what Ctrl+arrows, Delete, F2 … mean |

## Model (`_model.py`, no Tk)

- `BoardLane(key, title, kind=CARDS|TEXT, weight=1.0, placeholder="")`
- `BoardRow(key, label, cards={lane: (BoardCard, …)}, texts={lane: str}, tint=RowTint | None, locked=False)` –
  rows in **display order** (top first). `label` may contain `\n` (first line primary, others muted).
  A **locked** row takes nothing new: no "+" boxes, no drop slots, its `TEXT` cells show no
  placeholder and open no editor; its cells stay selectable with the cursor.
- `BoardCard(key, text, badge=None, tone=CardTone.NORMAL)` – `key` unique across the board; `badge`
  is a short code in a bubble at the card's right side. `tone` marks a card without colours in
  the consumer: `EMPHASIS` (soft accent fill, e.g. the leading card of a cell), `WARNING`
  (warning outline, e.g. a rule the consumer reports as violated). The one tone → token table
  lives in `_render.py` and follows theme switches.
- `BoardSlot(row_key, lane_key, index)` – insert before the card at `index` (`index == len` → end).
- `Cursor = str | BoardCell | None` – a card key, or a cell (empty `CARDS` cell or `TEXT` cell).

## Geometry (`_layout.py`, `_navigation.py`, no Tk)

- `compute_layout(rows, lanes, width, line_height, wrapper, badge_width)` – every cell spans its
  row's height; empty `CARDS` cells get a full-width dashed "+" box, filled ones a small "+" below
  the last card.
- `hit_test` → `CARD` / `ADD` / `CELL` / `NONE`; `slot_at` → slot before the first card whose middle
  lies below the pointer (points beyond the first/last row snap to it); `insertion_line(slot)` → the
  line in the gap.
- Navigation: per lane the entries run top to bottom (cards, or the cell when it has none).
  Up/Down step through a lane across rows; Left/Right switch lane in the same row to the entry
  closest in height.

## Gestures

- Click on a card or an empty/text cell: cursor moves, `on_cursor_change(cursor)`; a `TEXT` cell
  also opens the inline editor (not in a locked row). Click on "+": `on_add(cell)`.
- Double click on a card: `on_card_activate(key)`.
- Drag (threshold 4 px, Escape cancels): the line appears only over slots where
  `can_drop(key, slot)` is true; release there → `on_drop(key, slot)`. The board never moves the
  card itself – the consumer updates its data and calls `set_rows`. Dragging near the top/bottom
  edge scrolls.
- Inline text editor: Ctrl+Enter or focus loss commits, Escape cancels; `on_text_commit(cell, text)`
  fires only when the text changed (one consumer write per real change).

## Cost

Content renders go through `CanvasItemPool`s (unchanged passes cost no Tk calls); cursor and drop
line have their own cheap pass (a cursor step stays below 25 Tcl calls, pinned by
`tests/test_card_board_tk.py`). Renders are idle-scheduled (`IdleRenderScheduler`); `flush_now()`
for tests.
