from bw_gui.widgets.doc_text_events import (
    CodeBlockEvent,
    HeadingEvent,
    ListItemEvent,
    ParagraphEvent,
    TextRun,
    html_to_events,
)


def test_heading_becomes_heading_event_with_level():
    events = html_to_events("<h1>Titel</h1>")
    assert events == [HeadingEvent(level=1, runs=(TextRun(text="Titel"),))]


def test_paragraph_with_bold_and_italic_runs():
    html = "<p>Normal <strong>fett</strong> und <em>kursiv</em>.</p>"
    events = html_to_events(html)
    assert events == [
        ParagraphEvent(
            runs=(
                TextRun(text="Normal "),
                TextRun(text="fett", bold=True),
                TextRun(text=" und "),
                TextRun(text="kursiv", italic=True),
                TextRun(text="."),
            )
        )
    ]


def test_fenced_code_block_produces_exactly_one_code_block_event():
    html = (
        "<p>Text davor.</p>\n"
        '<pre><code class="language-python">print(\'hi\')\n</code></pre>\n'
        "<p>Text danach.</p>"
    )
    events = html_to_events(html)

    code_events = [event for event in events if isinstance(event, CodeBlockEvent)]
    assert len(code_events) == 1
    assert code_events[0].text == "print('hi')"
    assert len(events) == 3


def test_list_items_are_flattened_to_list_item_events():
    events = html_to_events("<ul>\n<li>Eins</li>\n<li>Zwei</li>\n</ul>")
    assert events == [
        ListItemEvent(ordered=False, runs=(TextRun(text="Eins"),)),
        ListItemEvent(ordered=False, runs=(TextRun(text="Zwei"),)),
    ]


def test_ordered_list_items_are_marked_ordered():
    events = html_to_events("<ol>\n<li>Eins</li>\n<li>Zwei</li>\n</ol>")
    assert all(isinstance(event, ListItemEvent) and event.ordered for event in events)


def test_inline_code_span_is_marked_code_without_becoming_a_code_block():
    events = html_to_events("<p>Nutze <code>--check</code> beim Aufruf.</p>")
    assert events == [
        ParagraphEvent(
            runs=(
                TextRun(text="Nutze "),
                TextRun(text="--check", code=True),
                TextRun(text=" beim Aufruf."),
            )
        )
    ]


def test_table_row_is_flattened_to_tab_separated_paragraph():
    html = (
        "<table>\n<thead>\n<tr>\n<th>A</th>\n<th>B</th>\n</tr>\n</thead>\n"
        "<tbody>\n<tr>\n<td>1</td>\n<td>2</td>\n</tr>\n</tbody>\n</table>"
    )
    events = html_to_events(html)

    assert events == [
        ParagraphEvent(runs=(TextRun(text="A"), TextRun(text="\t"), TextRun(text="B"))),
        ParagraphEvent(runs=(TextRun(text="1"), TextRun(text="\t"), TextRun(text="2"))),
    ]


def test_empty_document_yields_no_events():
    assert html_to_events("") == []
