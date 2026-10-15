# Widget Events Contract

Consumer code never binds Tk lifecycle or virtual events (`<Configure>`, `<FocusIn>`/`<FocusOut>`, `<Map>`/`<Unmap>`, `<Destroy>`, `<<Modified>>`, `<<NotebookTabChanged>>`, `<<ListboxSelect>>`, `<<TreeviewSelect>>`, `<<ComboboxSelected>>`) and never mutates a selection directly. It uses the hooks below. Every hook returns a `Subscription`: `remove()` is idempotent, and the subscription is invalidated when the widget is destroyed. Handlers get values from `bw_gui.contracts.widget_events`, never Tk event objects.

| Module | Content |
|---|---|
| `bw_gui.contracts.widget_events` | pure event values (`ResizeEvent`, `FocusChange`, `SelectionCause`, `ListboxSelectionChange`, `TreeviewSelectionChange`, `ComboboxSelectionChange`, `TabChange`, `ActivateEvent`, `HoverEvent`) |
| `bw_gui.runtime.widget_events` | lifecycle hooks |
| `bw_gui.runtime.selection` | selection hooks, selection mutations, `on_activate` |
| `bw_gui.runtime.pointer_hover` | `bind_hover`, `bind_canvas_item` (see `POINTER_CONTRACT.md`) |

## Scope of a hook

Hooks bind on the widget's own bw-gui tag (`bwkeys:<path>`) and see the widget's **own** events. `within=True` (`on_resize`, `on_focus_change`; toplevels only, otherwise `ValueError`) also reports the events of every descendant: these are the semantics of a former binding on a toplevel's path tag, which Tk puts into the bindtags of all descendants. A handler's return value is ignored; lifecycle events are never consumed.

## Lifecycle hooks

| Hook | Reports | Notes |
|---|---|---|
| `on_resize(w, handler, *, within=False)` | `ResizeEvent(width, height, x, y, widget)` after each geometry change | For a toplevel, a move also reports (screen `x`/`y`). |
| `on_focus_change(w, *, on_gained=None, on_lost=None, within=False)` | `FocusChange(gained, widget)` | Every Tk focus event, whatever its notify detail (1:1 to a former raw binding). At least one callback is required. |
| `on_visibility(w, *, on_shown=None, on_hidden=None)` | transitions of `winfo_viewable()` | See below. |
| `on_destroy(w, handler)` | `handler(w)` once | Only for the widget itself, not its descendants. |
| `on_text_modified(text, handler)` | `handler(text)` after every content change | See below. |
| `on_tab_changed(notebook, handler)` | `TabChange(index, tab_id, widget)` | Reports both user changes and `select()`. |

**`on_visibility`:** reports only real transitions of `winfo_viewable()`, not each raw `<Map>`/`<Unmap>`. bw-gui watches `<Map>`/`<Unmap>` of the widget and of all ancestors up to its toplevel (iconify/deiconify included), re-evaluates the state, and calls `on_shown(widget)`/`on_hidden(widget)` only when it changed. Registration stores the current state without reporting it. Focus or activation changes of the application never report.

**`on_text_modified`:** uses Tk's modified flag. On `<<Modified>>` with the flag set, bw-gui resets the flag (`edit_modified(False)`) and reports. The event caused by that reset is not reported. Typing, paste, undo and programmatic `insert`/`delete` all report. Consumers never read or reset the flag themselves (this replaces the reset each consumer used to do by hand).

## Selection: hooks and mutations

The API is widget-specific on purpose, with one hook, one event type and one mutation object per widget type:

| Widget | Hook | Event | Mutations |
|---|---|---|---|
| `Listbox` | `on_listbox_select` | `ListboxSelectionChange(indices, previous, cause)` | `listbox_selection.set(lb, indices)`, `.clear(lb)` |
| `ttk.Treeview` | `on_treeview_select` | `TreeviewSelectionChange(item_ids, previous, cause)` | `treeview_selection.set(tv, item_ids)`, `.remove(tv, item_ids)`, `.clear(tv)` |
| `ttk.Combobox` | `on_combobox_select` | `ComboboxSelectionChange(index, value, cause)` | `combobox_selection.set_index(cb, i)`, `.set_value(cb, v)` |

Every mutation takes `notify=False` (default: never reports) or `notify=True` (reports with `cause=PROGRAMMATIC`). The operations are exactly the ones the consumer inventory needs (2026-10-15).

**What is shared:** only the meaning of `cause` and the de-duplication. A hook reports only when the selection differs from the last one it reported. For a combobox, picking the same value again does not report.

| `cause` | Meaning |
|---|---|
| `USER` | The change follows mouse or keyboard input on the widget itself. bw-gui sets an input marker on press, drag, release and key (cleared after idle). |
| `PROGRAMMATIC` | A mutation through this module with `notify=True`. |
| `EXPORT_LOST` | Listbox only: another widget took the X selection (`exportselection`). |
| `CONTENT_CHANGED` | Treeview only: items changed and Tk adjusted the selection (1:1 to Tk). |

**Tk differences the module hides:**

- **Listbox and Combobox:** Tk emits no event for programmatic changes. A mutation with `notify=True` reports synchronously.
- **Treeview:** Tk queues `<<TreeviewSelect>>` for programmatic changes. A mutation therefore records the expected selection (a generation mark), and the queued event is then suppressed (`notify=False`) or reported as `PROGRAMMATIC` (`notify=True`), with the same timing as Tk's own event.
- **Migration rule:** a consumer whose treeview handler used to run after a programmatic `selection_set` passes `notify=True`, so that behaviour stays the same.

**Deliberately allowed:**

- content mutations (`insert`/`delete`, reported 1:1 by Tk as far as the selection changes)
- `Combobox.set(value)` (no event, not detectable by a guard)
- `Entry.selection_clear()` (text selection, not a list selection)

`Listbox.exportselection` stays unchanged.

## Activation

`on_activate(w, handler)` handles a Listbox or Treeview. It reports Enter (Shift tolerated) or a double click on an element as `ActivateEvent(source, element, widget)`:

- `element` is the listbox index or treeview item id. For Enter it is the active index or focus item, or `None` if there is none.
- `on_activate` runs on the bw tag, before the native class bindings. `HANDLED` suppresses the native action (e.g. a Treeview opening or closing a node on double click). `None`/`NOT_HANDLED` lets the native action run.
- A double click on empty space is not an activation.
- Double-click recognition is Tk's own multi-click detection, as in `bind_click(count=2)`.

## Guard

A guard forbids, in apps:
- lifecycle and virtual-event bindings
- raw selection mutations (`selection_set`, `select_set`, `selection_add`/`remove`/`toggle`, `selection_clear`/`select_clear` with a range argument, `Combobox.current(<index>)`)

The three levels of the guard (semantic rule, detected AST patterns, known false negatives and positives) are documented with the guard itself.
