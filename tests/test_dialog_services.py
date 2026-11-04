from __future__ import annotations

from bw_gui.dialogs import FileDialogService, MessageDialogService, TextPromptDialogService
from bw_gui.dialogs import service as dialog_service
from bw_gui.dialogs.service import _EscapeSafeQueryString


class _FakeModalParent:
    def __init__(self):
        self.titles: list[str] = []

    def _run_modal_dialog_call(self, title, callback):
        self.titles.append(title)
        return callback()


def test_message_dialog_uses_modal_runner_with_parent(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_showerror(title, message, **kwargs):
        calls.append((title, message))
        return "ok"

    monkeypatch.setattr(dialog_service.messagebox, "showerror", fake_showerror)
    parent = _FakeModalParent()

    service = MessageDialogService()
    result = service.showerror("Fehler", "Kaputt", parent=parent)

    assert result == "ok"
    assert calls == [("Fehler", "Kaputt")]
    assert parent.titles == ["Fehler"]


def test_text_prompt_uses_default_root_when_parent_missing(monkeypatch):
    parent = _FakeModalParent()

    class _FakeQueryString:
        def __init__(self, title, prompt, **kwargs):
            self.result = f"{title}:{prompt}"

    monkeypatch.setattr(dialog_service, "_EscapeSafeQueryString", _FakeQueryString)
    monkeypatch.setattr(dialog_service.tk, "_default_root", parent)

    service = TextPromptDialogService()
    result = service.askstring("Titel", "Frage?")

    assert result == "Titel:Frage?"
    assert parent.titles == ["Titel"]


def test_file_dialog_openfilenames_normalizes_iterable(monkeypatch):
    parent = _FakeModalParent()

    def fake_openfilenames(**kwargs):
        return ["a.txt", "b.txt"]

    monkeypatch.setattr(dialog_service.filedialog, "askopenfilenames", fake_openfilenames)

    service = FileDialogService()
    result = service.askopenfilenames(parent=parent, title="Dateien")

    assert result == ("a.txt", "b.txt")
    assert parent.titles == ["Dateien"]


def test_message_dialog_askyesno_normalizes_bool(monkeypatch):
    def fake_askyesno(title, message, **kwargs):
        return 1

    monkeypatch.setattr(dialog_service.messagebox, "askyesno", fake_askyesno)

    service = MessageDialogService()
    result = service.askyesno("Frage", "Weiter?")

    assert result is True


def test_message_dialog_askretrycancel_normalizes_bool(monkeypatch):
    def fake_askretrycancel(title, message, **kwargs):
        return 0

    monkeypatch.setattr(dialog_service.messagebox, "askretrycancel", fake_askretrycancel)

    service = MessageDialogService()
    result = service.askretrycancel("Pfadpruefung", "Nochmal?")

    assert result is False


def test_escape_safe_query_string_keys_go_through_the_window_binder(_shared_tk_root, monkeypatch):
    """Enter/Escape of the text prompt are window-binder shortcuts that consume the key, so
    Escape never leaks to shortcuts behind the dialog; the stdlib's raw bindings are gone."""
    from bw_gui.testing.keys import press_key

    monkeypatch.setattr(_EscapeSafeQueryString, "wait_window", lambda self, window=None: None)
    monkeypatch.setattr(_EscapeSafeQueryString, "grab_set", lambda self: None)
    dialog = _EscapeSafeQueryString("Titel", "Frage", parent=_shared_tk_root)
    try:
        assert str(dialog.tk.call("bind", str(dialog), "<Key-Escape>")) == ""
        assert press_key(dialog.entry, "Escape") is True
        assert not dialog.winfo_exists()
    finally:
        if dialog.winfo_exists():
            dialog.destroy()


def _headless_prompt(monkeypatch, root, **kwargs):
    """Build a real query dialog without its modal wait/grab; warnings are recorded."""
    warnings: list[str] = []
    monkeypatch.setattr(_EscapeSafeQueryString, "wait_window", lambda self, window=None: None)
    monkeypatch.setattr(_EscapeSafeQueryString, "grab_set", lambda self: None)
    monkeypatch.setattr(
        dialog_service.MessageDialogService, "showwarning", lambda self, title, message, **kw: warnings.append(message)
    )
    return _EscapeSafeQueryString("Titel", "Name?", parent=root, **kwargs), warnings


def test_validator_error_keeps_the_prompt_open_with_its_text(_shared_tk_root, monkeypatch):
    dialog, warnings = _headless_prompt(
        monkeypatch, _shared_tk_root, validate=lambda text: "gibt es schon" if text == "A" else None, initialvalue="A"
    )
    try:
        dialog.ok()
        assert warnings == ["gibt es schon"]
        assert dialog.winfo_exists()
        assert dialog.entry.get() == "A"
        dialog.entry.delete(0, "end")
        dialog.entry.insert(0, "B")
        dialog.ok()
        assert dialog.result == "B"
        assert not dialog.winfo_exists()
    finally:
        if dialog.winfo_exists():
            dialog.destroy()


def test_initial_value_is_inserted_and_selected(_shared_tk_root, monkeypatch):
    dialog, _warnings = _headless_prompt(monkeypatch, _shared_tk_root, initialvalue="Kopie")
    try:
        assert dialog.entry.get() == "Kopie"
        assert dialog.entry.selection_present()
    finally:
        dialog.destroy()


def test_askstring_forwards_the_validator(monkeypatch):
    seen = {}

    class _FakeQueryString:
        def __init__(self, title, prompt, **kwargs):
            seen.update(kwargs)
            self.result = "x"

    monkeypatch.setattr(dialog_service, "_EscapeSafeQueryString", _FakeQueryString)
    monkeypatch.setattr(dialog_service.tk, "_default_root", _FakeModalParent())
    def check(text):
        return None

    assert TextPromptDialogService().askstring("T", "P", validate=check) == "x"
    assert seen["validate"] is check
