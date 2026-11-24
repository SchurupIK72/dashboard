import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import pytest

from dashboard.main import templates

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "src" / "dashboard" / "templates"
SCRIPT_TITLE = "<script>alert(1)</script>"
ESCAPED_SCRIPT_TITLE = "&lt;script&gt;alert(1)&lt;/script&gt;"
PATHS = ["/shopping", "/todos"]


def make_item(item_id: int, title: str, is_done: bool = False) -> SimpleNamespace:
    return SimpleNamespace(id=item_id, title=title, is_done=is_done)


def render_fragment(
    items: list[SimpleNamespace], path: str = "/shopping", error: str | None = None
) -> str:
    return templates.get_template("_checklist_items.html").render(
        checklist_path=path, items=items, error=error
    )


def render_page(
    items: list[SimpleNamespace],
    path: str = "/shopping",
    title: str = "Покупки",
    error: str | None = None,
) -> str:
    return templates.get_template("checklist.html").render(
        checklist_title=title, checklist_path=path, items=items, error=error
    )


Attributes = dict[str, str | None]


@dataclass
class FormMarkup:
    attrs: Attributes
    inputs: list[Attributes] = field(default_factory=list)


class MarkupCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[tuple[str, Attributes]] = []
        self.forms: list[FormMarkup] = []
        self.item_texts: list[tuple[str, str]] = []
        self._form: FormMarkup | None = None
        self._stack: list[str] = []
        self._li_buffer: list[tuple[str, str]] | None = None
        self._text_target: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.elements.append((tag, attributes))
        if tag == "form":
            self._form = FormMarkup(attrs=attributes)
            self.forms.append(self._form)
        elif tag == "input" and self._form is not None:
            self._form.inputs.append(attributes)
        elif tag == "li":
            self._li_buffer = []
        elif tag in ("s", "span") and self._li_buffer is not None:
            self._text_target = tag
            self._li_buffer.append((tag, ""))
        if tag not in ("input", "br", "meta", "link"):
            self._stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._form = None
        elif tag in ("s", "span"):
            self._text_target = None
        elif tag == "li" and self._li_buffer is not None:
            self.item_texts.extend(self._li_buffer)
            self._li_buffer = None
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._text_target is not None and self._li_buffer:
            tag, text = self._li_buffer[-1]
            self._li_buffer[-1] = (tag, text + data)


def collect(markup: str) -> MarkupCollector:
    collector = MarkupCollector()
    collector.feed(markup)
    collector.close()
    return collector


def forms_with_action(collector: MarkupCollector, action: str) -> list[FormMarkup]:
    return [form for form in collector.forms if form.attrs.get("action") == action]


def attrs_of(form: FormMarkup) -> Attributes:
    return form.attrs


@pytest.mark.acceptance
@pytest.mark.parametrize("path", PATHS)
def test_fragment_has_no_html_document_and_has_root_container(path: str) -> None:
    markup = render_fragment([make_item(1, "Молоко")], path)
    lowered = markup.lower()
    assert "<html" not in lowered
    assert "<body" not in lowered
    assert "<head" not in lowered
    assert "<!doctype" not in lowered
    divs = [attrs for tag, attrs in collect(markup).elements if tag == "div"]
    assert divs[0].get("id") == "checklist-items"
    assert markup.strip().startswith('<div id="checklist-items"')
    assert markup.strip().endswith("</div>")


@pytest.mark.acceptance
def test_fragment_keeps_given_order_and_does_not_resort() -> None:
    items = [
        make_item(9, "Девятый", is_done=True),
        make_item(2, "Второй"),
        make_item(7, "Седьмой", is_done=True),
        make_item(1, "Первый"),
    ]
    collector = collect(render_fragment(items))
    assert [text.strip() for _, text in collector.item_texts] == [
        "Девятый",
        "Второй",
        "Седьмой",
        "Первый",
    ]


@pytest.mark.acceptance
def test_fragment_order_follows_input_for_reversed_input() -> None:
    items = [make_item(3, "Ц"), make_item(2, "Б"), make_item(1, "А")]
    collector = collect(render_fragment(items))
    assert [text.strip() for _, text in collector.item_texts] == ["Ц", "Б", "А"]


@pytest.mark.acceptance
def test_done_items_are_struck_through_and_open_items_are_not() -> None:
    items = [
        make_item(1, "Открытая"),
        make_item(2, "Готовая", is_done=True),
        make_item(3, "Вторая открытая"),
        make_item(4, "Вторая готовая", is_done=True),
    ]
    collector = collect(render_fragment(items))
    by_tag = [(tag, text.strip()) for tag, text in collector.item_texts]
    assert by_tag == [
        ("span", "Открытая"),
        ("s", "Готовая"),
        ("span", "Вторая открытая"),
        ("s", "Вторая готовая"),
    ]
    struck = [attrs for tag, attrs in collector.elements if tag == "s"]
    assert len(struck) == 2
    assert all(attrs.get("class") == "is-done" for attrs in struck)


@pytest.mark.acceptance
def test_all_open_items_have_no_strikethrough_element() -> None:
    markup = render_fragment([make_item(1, "А"), make_item(2, "Б")])
    assert "<s " not in markup
    assert "<s>" not in markup
    assert "is-done" not in markup


@pytest.mark.acceptance
def test_done_toggle_button_reflects_state() -> None:
    markup = render_fragment([make_item(1, "Открытая"), make_item(2, "Готовая", is_done=True)])
    collector = collect(markup)
    buttons = [
        attrs
        for tag, attrs in collector.elements
        if tag == "button" and attrs.get("aria-pressed") is not None
    ]
    assert [button["aria-pressed"] for button in buttons] == ["false", "true"]


@pytest.mark.acceptance
@pytest.mark.parametrize("path", PATHS)
def test_every_form_has_post_action_and_htmx_attributes(path: str) -> None:
    items = [make_item(5, "Хлеб"), make_item(8, "Сыр", is_done=True)]
    collector = collect(render_fragment(items, path))
    expected_actions = [f"{path}/add"]
    for item in items:
        expected_actions += [
            f"{path}/{item.id}/toggle",
            f"{path}/{item.id}/rename",
            f"{path}/{item.id}/delete",
        ]
    assert [attrs_of(form).get("action") for form in collector.forms] == expected_actions
    for form in collector.forms:
        attributes = attrs_of(form)
        action = attributes["action"]
        assert str(attributes.get("method")).lower() == "post"
        assert attributes.get("hx-post") == action
        assert attributes.get("hx-target") == "#checklist-items"
        assert attributes.get("hx-swap") == "outerHTML"


@pytest.mark.acceptance
def test_no_get_based_htmx_or_links_to_mutating_routes() -> None:
    markup = render_fragment([make_item(1, "Хлеб"), make_item(2, "Сыр", is_done=True)])
    for forbidden in ("hx-get", "hx-put", "hx-delete", "hx-patch", "<a ", 'method="get"'):
        assert forbidden not in markup.lower()


@pytest.mark.acceptance
@pytest.mark.parametrize("path", PATHS)
def test_delete_form_requires_confirmation(path: str) -> None:
    items = [make_item(4, "Хлеб"), make_item(6, "Сыр", is_done=True)]
    collector = collect(render_fragment(items, path))
    for item in items:
        delete_forms = forms_with_action(collector, f"{path}/{item.id}/delete")
        assert len(delete_forms) == 1
        assert attrs_of(delete_forms[0]).get("hx-confirm") == "Удалить позицию?"
    confirmations = [attrs for _, attrs in collector.elements if "hx-confirm" in attrs]
    assert len(confirmations) == 2


@pytest.mark.acceptance
def test_confirmation_is_only_on_delete_forms() -> None:
    collector = collect(render_fragment([make_item(1, "Хлеб")]))
    for form in collector.forms:
        action = str(attrs_of(form)["action"])
        has_confirm = "hx-confirm" in attrs_of(form)
        assert has_confirm == action.endswith("/delete")


@pytest.mark.acceptance
def test_title_is_escaped_in_text_and_rename_value_for_open_item() -> None:
    markup = render_fragment([make_item(1, SCRIPT_TITLE)])
    assert "<script" not in markup.lower()
    assert "alert(1)</script>" not in markup
    assert ESCAPED_SCRIPT_TITLE in markup
    collector = collect(markup)
    assert [text for _, text in collector.item_texts if text.strip()] == [SCRIPT_TITLE]
    rename = forms_with_action(collector, "/shopping/1/rename")[0]
    rename_input = rename.inputs[0]
    assert rename_input["value"] == SCRIPT_TITLE
    assert f'value="{ESCAPED_SCRIPT_TITLE}"' in markup


@pytest.mark.acceptance
def test_title_is_escaped_for_done_item() -> None:
    markup = render_fragment([make_item(1, SCRIPT_TITLE, is_done=True)])
    assert "<script" not in markup.lower()
    collector = collect(markup)
    assert [(tag, text.strip()) for tag, text in collector.item_texts] == [("s", SCRIPT_TITLE)]
    assert f'value="{ESCAPED_SCRIPT_TITLE}"' in markup


@pytest.mark.acceptance
def test_title_with_quote_cannot_break_out_of_rename_value() -> None:
    hostile = '"><img src=x onerror=alert(1)>'
    markup = render_fragment([make_item(1, hostile)])
    assert "<img" not in markup.lower()
    collector = collect(markup)
    rename = forms_with_action(collector, "/shopping/1/rename")[0]
    assert len(rename.inputs) == 1
    assert rename.inputs[0]["value"] == hostile
    assert "onerror" not in {key for _, attrs in collector.elements for key in attrs}


@pytest.mark.acceptance
def test_ampersand_and_unicode_titles_round_trip() -> None:
    title = "Чай & кофе «2 в 1» ✓"
    collector = collect(render_fragment([make_item(1, title)]))
    assert [text.strip() for _, text in collector.item_texts] == [title]
    rename = forms_with_action(collector, "/shopping/1/rename")[0]
    assert rename.inputs[0]["value"] == title


@pytest.mark.acceptance
def test_empty_list_shows_empty_message_without_list() -> None:
    collector = collect(render_fragment([]))
    markup = render_fragment([])
    assert "Список пуст" in markup
    assert not [tag for tag, _ in collector.elements if tag in ("ul", "li")]
    assert [attrs_of(form)["action"] for form in collector.forms] == ["/shopping/add"]


@pytest.mark.acceptance
def test_non_empty_list_hides_empty_message() -> None:
    markup = render_fragment([make_item(1, "Хлеб")])
    assert "Список пуст" not in markup
    assert markup.count("<li") == 1


@pytest.mark.acceptance
@pytest.mark.parametrize("error", [None, ""])
def test_no_error_element_without_error(error: str | None) -> None:
    markup = render_fragment([make_item(1, "Хлеб")], error=error)
    classes = [attrs.get("class") for _, attrs in collect(markup).elements]
    assert "error" not in classes


@pytest.mark.acceptance
def test_no_error_element_when_error_is_not_passed() -> None:
    markup = templates.get_template("_checklist_items.html").render(
        checklist_path="/todos", items=[]
    )
    classes = [attrs.get("class") for _, attrs in collect(markup).elements]
    assert "error" not in classes


@pytest.mark.acceptance
def test_error_is_shown_in_error_paragraph_inside_root() -> None:
    message = "Название должно быть от 1 до 200 символов"
    markup = render_fragment([make_item(1, "Хлеб")], error=message)
    collector = collect(markup)
    errors = [(tag, attrs) for tag, attrs in collector.elements if attrs.get("class") == "error"]
    assert len(errors) == 1
    assert errors[0][0] == "p"
    assert message in markup
    assert markup.index(message) > markup.index('id="checklist-items"')
    assert markup.index(message) < markup.index("<form")


@pytest.mark.acceptance
def test_error_text_is_escaped() -> None:
    markup = render_fragment([], error=SCRIPT_TITLE)
    assert "<script" not in markup.lower()
    assert ESCAPED_SCRIPT_TITLE in markup


@pytest.mark.acceptance
@pytest.mark.parametrize("path", PATHS)
def test_title_inputs_are_limited_required_and_named_title(path: str) -> None:
    collector = collect(render_fragment([make_item(3, "Хлеб")], path))
    add_form = forms_with_action(collector, f"{path}/add")[0]
    rename_form = forms_with_action(collector, f"{path}/3/rename")[0]
    for form in (add_form, rename_form):
        assert len(form.inputs) == 1
        title_input = form.inputs[0]
        assert title_input["name"] == "title"
        assert title_input["maxlength"] == "200"
        assert "required" in title_input
    assert not add_form.inputs[0].get("value")


@pytest.mark.acceptance
def test_button_labels_are_russian() -> None:
    markup = render_fragment([make_item(1, "Хлеб")])
    for label in ("Добавить", "Сохранить", "Удалить"):
        assert f">{label}</button>" in markup


@pytest.mark.acceptance
def test_fragment_contains_no_script_comment_or_external_url() -> None:
    markup = render_fragment([make_item(1, "Хлеб"), make_item(2, "Сыр", is_done=True)])
    lowered = markup.lower()
    assert "<script" not in lowered
    assert "<!--" not in markup
    assert "http://" not in lowered
    assert "https://" not in lowered


@pytest.mark.acceptance
@pytest.mark.parametrize("name", ["checklist.html", "_checklist_items.html"])
def test_template_sources_have_no_script_comments_or_urls(name: str) -> None:
    source = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
    lowered = source.lower()
    assert "<script" not in lowered
    assert "<!--" not in source
    assert "{#" not in source
    assert "http://" not in lowered
    assert "https://" not in lowered
    assert "|safe" not in lowered.replace(" ", "")
    assert "autoescape false" not in lowered


@pytest.mark.acceptance
@pytest.mark.parametrize(
    ("path", "title"),
    [("/shopping", "Покупки"), ("/todos", "Дела")],
)
def test_page_extends_base_with_title_heading_and_fragment(path: str, title: str) -> None:
    items = [make_item(1, "Хлеб"), make_item(2, "Сыр", is_done=True)]
    page = render_page(items, path, title)
    assert page.lstrip().lower().startswith("<!doctype html>")
    assert f"<title>{title}</title>" in page
    assert f"<h1>{title}</h1>" in page
    assert page.count("<html") == 1
    assert page.count('id="checklist-items"') == 1
    assert render_fragment(items, path).strip() in page
    main_start = page.index("<main")
    assert main_start < page.index('id="checklist-items"') < page.index("</main>")
    assert page.index("<h1>") < page.index('id="checklist-items"')


@pytest.mark.acceptance
def test_page_escapes_hostile_title_and_adds_no_inline_script() -> None:
    page = render_page([make_item(1, SCRIPT_TITLE)])
    assert ESCAPED_SCRIPT_TITLE in page
    script_tags = re.findall(r"<script\b[^>]*>", page)
    assert script_tags
    assert all("src=" in tag for tag in script_tags)
    assert "alert(1)" not in re.sub(re.escape(ESCAPED_SCRIPT_TITLE), "", page).replace(
        SCRIPT_TITLE, ""
    )


@pytest.mark.acceptance
def test_page_title_and_heading_come_from_context() -> None:
    page = render_page([], "/todos", "Дела")
    assert "<title>Дела</title>" in page
    assert "Покупки" not in page


@pytest.mark.acceptance
def test_page_shows_error_through_fragment() -> None:
    page = render_page([], error="Позиция не найдена")
    assert '<p class="error"' in page
    assert "Позиция не найдена" in page
    ok_page = render_page([])
    assert "Позиция не найдена" not in ok_page
    assert 'class="error"' not in ok_page
