# CardBoard Contract

`bw_gui.widgets.card_board.CardBoard`: a board of **rows × lanes**. A `CARDS` lane holds an
ordered stack of cards per row, a `TEXT` lane one free text per row, a `CARDS_TEXT` lane both
(the cards always above the text). Cards are dragged between cells with a coloured
**insertion line** that shows where the card would land. Cards are renamed and typed **in place**
(inline editor over the card or a draft slot) -- no popup.

## Division of labour

| The board does | The consumer does |
|---|---|
| layout, word wrap, rendering in theme colours (tokens, row tints via `tinted_color`) | owns all data and rebuilds `BoardRow`s after every change |
| reports gestures: cursor change, double click, "+" click, drop, text commit | applies rules (where a card may go, uniqueness, naming, undo) |
| keeps its own keyboard **cursor** (card key or cell) | binds every key on `key_widget` (principle E: the board binds none) |
| offers `move_cursor(direction)` (pure navigation) and `see(cursor)` | decides what Ctrl+arrows, Delete, F2 … mean |

## Model (`_model.py`, no Tk)

- `BoardLane(key, title, kind=CARDS|TEXT|CARDS_TEXT, weight=1.0, placeholder="")` – whether a lane
  holds cards and/or a text is answered only by `lane_holds_cards(kind)` / `lane_holds_text(kind)`.
- `BoardRow(key, label, cards={lane: (BoardCard, …)}, texts={lane: str}, tint=RowTint | None, locked=False, action=None)` –
  rows in **display order** (top first). `label` may contain `\n` (first line primary, others muted).
  A **locked** row takes nothing new: no "+" boxes, no drop slots, its `TEXT` cells show no
  placeholder and open no editor; its cells stay selectable with the cursor.
  `action` (text) shows a small button in the row-label column below the label; the row grows to
  fit it. Its look (fill, outline, text tokens) is the one `_ROW_ACTION_LOOK` entry in `_render.py`.
- `BoardCard(key, text, badge=None, tone=CardTone.NORMAL)` – `key` unique across the board; `badge`
  is a short code in a bubble at the card's right side. `tone` marks a card without colours in
  the consumer: `EMPHASIS` (soft accent fill, e.g. the leading card of a cell), `WARNING`
  (warning outline, e.g. a rule the consumer reports as violated). The one tone → token table
  lives in `_render.py` and follows theme switches.
- `BoardSlot(row_key, lane_key, index)` – insert before the card at `index` (`index == len` → end).
- `Cursor = str | BoardCell | None` – a card key, or a cell (empty `CARDS` cell, or the text of a
  `TEXT`/`CARDS_TEXT` cell).
- `EditTarget = str | BoardCell | BoardSlot` – what the inline editor edits: a card, a text cell,
  or a new card at a slot.

## Geometry (`_layout.py`, `_navigation.py`, no Tk)

- `compute_layout(rows, lanes, width, line_height, wrapper, badge_width, draft=None)` – every cell
  spans its row's height and stacks its cards, its "+" box (not in locked rows) and its text
  (`CellBox.text_box`). An empty `CARDS` cell gets a full-width dashed "+" box, every other card
  stack a small "+" below the last card. `draft` (a slot) reserves one card-high space there
  (`BoardLayout.draft_box`); the following cards move down.
- `hit_test` → `ROW_ACTION` (with `row_key`; checked first) / `CARD` / `ADD` / `TEXT` (the text area
  of a cell) / `CELL` / `NONE`; `slot_at` → slot before the first card whose middle lies below the
  pointer (points beyond the first/last row snap to it; over the text of a `CARDS_TEXT` cell → the
  end of its cards, i.e. directly above the text); `insertion_line(slot)` → the line in the gap.
- Navigation: per lane the entries run top to bottom – a cell's cards, then the cell itself when it
  holds a text or no card. Up/Down step through a lane across rows; Left/Right switch lane in the
  same row to the entry closest in height. A cell cursor frames the text area (`cursor_box`).

## Gestures

- Click on a card or an empty/text cell: cursor moves, `on_cursor_change(cursor)`; a click on a
  cell's text area also opens the inline editor (not in a locked row). Click on "+": `on_add(cell)`.
- Click on a row-action button: `on_row_action(row_key)`; the cursor does not move. What the
  action does is the consumer's business (the board has no rule about it).
- Double click on a card: `on_card_activate(key)`.
- Drag (threshold 4 px, Escape cancels): the line appears only over slots where
  `can_drop(key, slot)` is true; release there → `on_drop(key, slot)`. The board never moves the
  card itself – the consumer updates its data and calls `set_rows`. Dragging near the top/bottom
  edge scrolls.
- Inline editor (`_text_editor.py`, one editor for all targets, at most one open; `editing` names
  the target):
  - **Text** (`edit_text(cell)`): Ctrl+Enter or focus loss commits, Escape cancels;
    `on_text_commit(cell, text)` fires only when the text changed (one consumer write per real change).
  - **Card** (`edit_card(key, on_done=, initial=, validate=)` over the card,
    `draft_card(slot, on_done=, initial=, validate=)` in a reserved draft space): one line, Enter
    (or Ctrl+Enter) commits, Escape cancels. `validate(text)` returns an error message, which is
    shown below the field (`FieldErrorLabel`, the same look as `askstring`) while the editor stays
    open. Focus loss commits a valid text and discards an invalid one. An unchanged rename reports
    nothing; a draft always reports its text. The board never adds or renames the card itself –
    `on_done(text)` goes to the consumer, which updates its rows.
  - After every re-layout (`set_rows`, resize) the open editor follows its target, or closes
    without reporting when the target is gone.

## Cost

Content renders go through `CanvasItemPool`s (unchanged passes cost no Tk calls); cursor and drop
line have their own cheap pass (a cursor step stays below 25 Tcl calls, pinned by
`tests/test_card_board_tk.py`). Renders are idle-scheduled (`IdleRenderScheduler`); `flush_now()`
for tests.
