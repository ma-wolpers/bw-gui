# Overlay Stack Contract

One stack per Tk interpreter (stored on the root, `bw_gui.runtime.overlay_stack`) is the
single source for "which overlays are open". It replaces `ScrollablePopupWindow._open_popups`
and the toplevel scans consumer apps used to do.

## Entries and categories

`OverlayEntry(overlay_id, category, toplevel, policy)`

| Category | Who registers | Gating |
|---|---|---|
| `MODAL_DIALOG` | `ScrollablePopupWindow` (default `overlay_category`), `TabbedSettingsDialog`, native message/file/choice dialogs via `_run_modal` | yes |
| `NON_MODAL_POPUP` | `ScrollablePopupWindow(overlay_category=NON_MODAL_POPUP)` and consumer tool windows via `register_overlay` | only with the `include_non_modal` preset |
| `MENU` | `CustomMenuBar` popups and description flyouts | only with the `include_menus` preset |
| `TRANSIENT` | `HoverTooltip`, drag ghost | never |

- **Native dialogs:** a native dialog has no Tk toplevel. It is a *modal invocation* with `toplevel=None`, which is allowed only for `MODAL_DIALOG` (otherwise `ValueError`). It is registered for exactly the duration of the blocking call (`try`/`finally`).
- **What reads the entries:** gating and presets read only categories, never toplevels. Code that needs a toplevel skips `None` entries.
- **Lifecycle:** `register_overlay(anchor, category, *, toplevel=None, policy=None) -> Subscription` ends automatically on the toplevel's `<Destroy>`.

## Presets for a binder's `dialog_open`

There is no global "anything open" default. Every app picks a preset explicitly:

| Preset | Semantics | Used by |
|---|---|---|
| `blocking(w)` | a modal dialog is open | Kartograph (its former scan classified menu popups as non-blocking) |
| `blocking(w, include_menus=True)` | modal dialog or menu popup | Blattwerk, aiza, Kursplaner, Korrektor |
| `blocking(w, include_non_modal=True)` | modal dialog or any non-modal popup | – (no consumer) |
| `modal_affecting_mode(w)` | modal with `PopupPolicy.affects_mode` | – (no consumer) |

Kursplaner: its former scan counted every visible direct child toplevel of the main window as blocking unless it was explicitly tracked as non-blocking. Menu popups are direct children of the root, so they counted; the non-blocking tool windows (Kompetenznetz, loading hint, shortcut debug window) register as `NON_MODAL_POPUP`. Hence `blocking(include_menus=True)`, not `modal_affecting_mode` (every Kursplaner modal popup affected the mode anyway).

Korrektor: same shape. Its former `PopupPolicyRegistry` plus scan counted every visible direct child toplevel (menu popups included) except the shortcut debug window. Blocking popups register as `MODAL_DIALOG` (raw toplevels through `_register_popup_window`), the debug window as `NON_MODAL_POPUP`, so the preset is `blocking(include_menus=True)`; `include_non_modal` would have made the debug window block. Escape from the main window closes the most recent non-`TRANSIENT` entry with a toplevel (former `active_popup()`).

`modal_affecting_mode(w)` and `blocking(w, include_non_modal=True)` have no consumer since the 2026-10 characterizations; they stay part of the contract on purpose (decision 2026-10-18: document, do not remove).

`topmost_window(w)` returns the toplevel Escape may close from the main window: the most recent entry with a toplevel that is not `TRANSIENT` and whose policy allows `close_on_escape` (no policy = allowed); native invocations are skipped. It replaces the consumer registries' `active_popup()` (Korrektor, Blattwerk).

`overlay_state(w)` returns `OverlayState(modal_dialog, menu_open, non_modal_popups, modal_affecting_mode, entries)`.

## Completeness against the former scans

Before an app migrates, every toplevel its old scan counted as blocking is inventoried and registered with the matching category. A characterization test compares the old scan with `overlay_state()` plus the app's preset for every popup kind and for combinations.

`unregistered_visible_toplevels(w)` is a test diagnostic: it reports visible toplevels that were added later without being registered.

`PopupPolicyRegistry` (`contracts/popup.py`) stays the pure, Tk-free policy declaration used by LaufKern manifests. Its stack methods are not a runtime source of truth.
