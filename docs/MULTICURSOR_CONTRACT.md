# Multi-cursor Contract

`attach_multicursor(text) -> MultiCursorController` gives a Tk `Text` several cursors and selections. Consumers see regions and edits, never marks, tags, or Tk index arithmetic.

| Module | Responsibility |
|---|---|
| `contracts/multicursor.py` | `Region`, `Edit`, `normalize`, planning functions (pure, no Tk) |
| `contracts/multicursor_history.py` | `CursorHistory`: cursor records matched by text content |
| `runtime/multicursor_text.py` | `TextSurface`: offsets, motion, transaction |
| `runtime/multicursor_view.py` | selection tag, caret bars, scroll hook |
| `runtime/multicursor.py` | `MultiCursorController`: gestures, keys, mode, undo/redo |

## Gestures

- **Ctrl+click:** adds a cursor. On an existing cursor or inside a selection it removes that region. The last region is never removed.
- **Ctrl+drag:** adds a selection, also while one exists. A native selection becomes the first region.
- **Plain click:** ends the mode, then behaves natively.

## Keys while active

| Key | Effect |
|---|---|
| Characters, Space, Enter, Tab | written at every region, replacing its selection |
| Backspace, Delete | a selection goes away; a caret removes its neighbouring character |
| ←/→ | every cursor moves from its head; selections are dropped |
| ↑/↓ | one display line, keeping a goal column across short lines |
| Home/End | start or end of the display line |
| Shift + motion | extends every region from its anchor |
| Ctrl+C / Ctrl+X | selections joined by newlines |
| Ctrl+V | one line per region when the counts match, else the whole text everywhere |
| Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z | undo/redo with cursors |
| Ctrl+A, PageUp/Down, Ctrl+arrows | end the mode, then behave natively |

The consumer binds what belongs to its own key registry: `add_cursor(±1)` (e.g. Ctrl+Alt+↑/↓) and `handle_escape()`, which returns `True` when the mode consumed the key. Escape order: multi-cursor first, then the consumer's own uses.

## Normalisation

- Identical carets collapse.
- Overlapping or touching selections merge, keeping the direction of the earlier one.
- A caret strictly inside a selection is swallowed.
- A caret exactly on a selection's edge stays independent. Writing puts its text before the selection's replacement (start edge) or after it (end edge).

## Transactions and undo

- **One step:** a key press is one transaction and one undo step, with `autoseparators` off and restored in every case.
- **Failure:** if an edit fails midway, the applied part is undone, the regions stay as they were, no record is written, and the exception propagates. A failure on the first edit undoes nothing.
- **Cursors:** undo and redo always run through the controller, also while inactive. A record holds digests of the whole text before and after a transaction, so it applies only when the text is exactly the state its offsets belong to.
- **Reactivation:** undoing into a multi-cursor edit restores its cursors and reactivates the mode. A plain undo stays native.
- **New document:** call `reset_history()`. It ends the mode, drops the records and clears the widget's undo stack.

## Changes from outside

Regions are offsets for one text state. A change the controller did not make ends the mode, checked on every controller action. Consumers call `sync()` from their `on_text_modified` handler so it also ends immediately. `on_text_modified` allows one subscriber per widget in practice (the first resets Tk's flag), which is why the controller does not subscribe itself.

Tk delivers `<<Modified>>` after the running code. A transaction therefore reports exactly one change, seen with the final text, and no batching interface is needed (`test_transaction_reports_one_modified_event_with_the_final_text`).

## Consumer edits

- `apply_per_region(plan, caret_text=None)`: `plan(region)` returns the `Edit` of a selection, or `None` to abort the whole action unchanged. Carets write `caret_text`.
- `run_on_regions(plan)`: one edit per region, carets included.
- `Edit.select` sets the selection afterwards, relative to the start of the new text.

## Offsets and emoji

Offsets count characters like Python. Measured on Tk 8.6: a column index and `count -chars` count an emoji twice, while `+ N chars` steps over it as one. `TextSurface` therefore uses `len(get(...))` and `+ N chars`, the pair that agrees, so an offset cannot point into an emoji.

## Drawing

- The primary region (the youngest) owns Tk's native cursor; every other head gets a bar placed at its `bbox`, hidden when scrolled out of view.
- Selections use the tag `mc_sel` with the colours of `sel`, read fresh on every draw.
- While active, `yscrollcommand` is wrapped: first the original command with the same arguments, then the bars. Leaving the mode restores the original and deletes the wrapper.

## Attach order

Attach after the consumer's click handlers. A consumer handler returning `HANDLED` (e.g. "no document loaded") must run first so it also stops the Ctrl gestures.
