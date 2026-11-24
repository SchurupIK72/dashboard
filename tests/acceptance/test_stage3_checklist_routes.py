import html
import json
import re
import sqlite3
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from dashboard.main import create_app
from dashboard.session_cookie import SESSION_COOKIE_NAME
from dashboard.settings import Settings, load_settings

SECRET_KEY = "k9Zq-guard-secret-0123456789-abcdefXYZ"
PASSWORDS = {"anna": "pw-anna-7731", "boris": "pw-boris-4482", "vera": "pw-vera-9915"}
USERS = [
    {"login": "anna", "password": PASSWORDS["anna"], "company": "Alpha"},
    {"login": "boris", "password": PASSWORDS["boris"], "company": "Alpha"},
    {"login": "vera", "password": PASSWORDS["vera"], "company": "Beta"},
]
INVALID_TITLE_MESSAGE = "Название должно быть от 1 до 200 символов"
NOT_FOUND_MESSAGE = "Позиция не найдена"
LISTS = [("/shopping", "shopping", "Покупки"), ("/todos", "todos", "Дела")]
SHOPPING_TITLES = ["Молоко", "Хлеб", "Яйца", "Сыр"]
TODO_TITLES = ["Оплатить интернет", "Позвонить маме", "Забрать посылку", "Купить билеты"]
MUTATIONS = [("toggle", {}), ("rename", {"title": "Новое имя"}), ("delete", {})]
LIST_IDS = [path.strip("/") for path, _, _ in LISTS]


def build_settings(database_path: Path) -> Settings:
    environ = {
        "SECRET_KEY": SECRET_KEY,
        "DASHBOARD_USERS": json.dumps(USERS),
        "DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
    }
    return load_settings(environ=environ, env_file=None)


@dataclass
class Harness:
    client: TestClient
    database_path: Path
    tokens: dict[str, str]

    def request(
        self,
        method: str,
        path: str,
        user: str | None = "anna",
        htmx: bool = False,
        data: dict[str, str] | None = None,
    ) -> Response:
        headers: dict[str, str] = {}
        if user is not None:
            headers["Cookie"] = f"{SESSION_COOKIE_NAME}={self.tokens[user]}"
        if htmx:
            headers["HX-Request"] = "true"
        return self.client.request(method, path, headers=headers, data=data)

    def rows(self, sql: str, params: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
        connection = sqlite3.connect(self.database_path)
        try:
            return [tuple(row) for row in connection.execute(sql, params).fetchall()]
        finally:
            connection.close()

    def dump(self) -> dict[str, list[tuple[object, ...]]]:
        names = [
            str(row[0])
            for row in self.rows("SELECT name FROM sqlite_master WHERE type = 'table'")
            if not str(row[0]).startswith("sqlite_")
        ]
        return {name: self.rows(f"SELECT * FROM {name} ORDER BY 1") for name in sorted(names)}

    def count(self, kind: str) -> int:
        return int(self.rows("SELECT COUNT(*) FROM checklist_items WHERE kind = ?", (kind,))[0][0])

    def item_id(self, kind: str, title: str) -> int:
        found = self.rows(
            "SELECT id FROM checklist_items WHERE kind = ? AND title = ?", (kind, title)
        )
        assert len(found) == 1, (kind, title, found)
        return int(found[0][0])

    def state(self, item_id: int) -> tuple[object, ...]:
        found = self.rows(
            "SELECT kind, title, is_done, created_at, done_at FROM checklist_items WHERE id = ?",
            (item_id,),
        )
        assert len(found) == 1
        return found[0]

    def seed(self, path: str, titles: list[str], user: str = "anna") -> None:
        for title in titles:
            response = self.request("POST", f"{path}/add", user=user, data={"title": title})
            assert response.status_code == 303

    def toggle(self, path: str, kind: str, title: str, user: str = "anna") -> None:
        item_id = self.item_id(kind, title)
        assert self.request("POST", f"{path}/{item_id}/toggle", user=user).status_code == 303

    def seed_both_lists(self) -> None:
        self.seed("/shopping", SHOPPING_TITLES)
        self.seed("/todos", TODO_TITLES)
        self.toggle("/shopping", "shopping", "Хлеб")
        self.toggle("/todos", "todos", "Позвонить маме")


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    database_path = tmp_path / "dashboard.db"
    application = create_app(build_settings(database_path))
    with TestClient(application, follow_redirects=False) as client:
        tokens: dict[str, str] = {}
        for user, password in PASSWORDS.items():
            response = client.post("/login", data={"login": user, "password": password})
            assert response.status_code == 303
            token = client.cookies.get(SESSION_COOKIE_NAME)
            assert token
            tokens[user] = token
            client.cookies.clear()
        yield Harness(client, database_path, tokens)


def page_items(page: str) -> list[tuple[str, bool]]:
    items: list[tuple[str, bool]] = []
    for block in re.findall(r"<li\b[^>]*>.*?</li>", page, re.DOTALL):
        title = re.search(r'<(?:span|s class="is-done")>(.*?)</(?:span|s)>', block, re.DOTALL)
        assert title is not None
        items.append((html.unescape(title.group(1)), 'class="is-done"' in block))
    return items


def page_titles(page: str) -> list[str]:
    return [title for title, _ in page_items(page)]


def assert_fragment(response_text: str) -> None:
    assert "<html" not in response_text.lower()
    assert "<!doctype" not in response_text.lower()
    assert response_text.lstrip().startswith('<div id="checklist-items"')


def assert_full_page(response_text: str) -> None:
    assert "<html" in response_text
    assert 'id="checklist-items"' in response_text


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
def test_page_shows_seeded_items_of_its_own_list_only(
    harness: Harness, path: str, kind: str, title: str
) -> None:
    harness.seed_both_lists()
    response = harness.request("GET", path)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert_full_page(response.text)
    assert f"<h1>{title}</h1>" in response.text
    own = SHOPPING_TITLES if kind == "shopping" else TODO_TITLES
    other = TODO_TITLES if kind == "shopping" else SHOPPING_TITLES
    shown = page_titles(response.text)
    assert sorted(shown) == sorted(own)
    assert not set(shown) & set(other)


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
def test_htmx_get_returns_fragment_without_html_document(
    harness: Harness, path: str, kind: str, title: str
) -> None:
    harness.seed_both_lists()
    response = harness.request("GET", path, htmx=True)
    assert response.status_code == 200
    assert_fragment(response.text)
    assert len(page_titles(response.text)) == 4


@pytest.mark.acceptance
def test_item_added_to_shopping_is_not_on_todos(harness: Harness) -> None:
    harness.seed_both_lists()
    harness.seed("/shopping", ["Только в покупках"])
    assert "Только в покупках" in page_titles(harness.request("GET", "/shopping").text)
    assert "Только в покупках" not in page_titles(harness.request("GET", "/todos").text)
    assert harness.count("shopping") == 5
    assert harness.count("todos") == 4


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
def test_add_valid_title_redirects_and_item_appears(
    harness: Harness, path: str, kind: str, title: str
) -> None:
    harness.seed_both_lists()
    before = harness.count(kind)
    response = harness.request("POST", f"{path}/add", data={"title": "Молоко 3.2%"})
    assert response.status_code == 303
    assert response.headers["location"] == path
    assert harness.count(kind) == before + 1
    assert "Молоко 3.2%" in page_titles(harness.request("GET", path).text)


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
@pytest.mark.parametrize("bad_title", ["   ", "", "x" * 201, " " + "y" * 201 + " "])
def test_add_invalid_title_plain_request_gets_422_page_and_list_is_unchanged(
    harness: Harness, path: str, kind: str, title: str, bad_title: str
) -> None:
    harness.seed_both_lists()
    before = harness.dump()
    response = harness.request("POST", f"{path}/add", data={"title": bad_title})
    assert response.status_code == 422
    assert_full_page(response.text)
    assert INVALID_TITLE_MESSAGE in response.text
    assert "location" not in response.headers
    assert len(page_titles(response.text)) == 4
    assert harness.dump() == before


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
@pytest.mark.parametrize("bad_title", ["   ", "z" * 201])
def test_add_invalid_title_htmx_request_gets_fragment_with_error(
    harness: Harness, path: str, kind: str, title: str, bad_title: str
) -> None:
    harness.seed_both_lists()
    before = harness.dump()
    response = harness.request("POST", f"{path}/add", htmx=True, data={"title": bad_title})
    assert response.status_code == 200
    assert_fragment(response.text)
    assert INVALID_TITLE_MESSAGE in response.text
    assert len(page_titles(response.text)) == 4
    assert harness.dump() == before


@pytest.mark.acceptance
def test_add_title_of_exactly_200_chars_is_accepted_and_padded_title_is_trimmed(
    harness: Harness,
) -> None:
    harness.seed_both_lists()
    boundary = "ж" * 200
    assert harness.request("POST", "/shopping/add", data={"title": boundary}).status_code == 303
    padded = "  Кефир  "
    assert harness.request("POST", "/shopping/add", data={"title": padded}).status_code == 303
    assert harness.request("POST", "/todos/add", data={"title": f" {boundary} "}).status_code == 303
    shown = page_titles(harness.request("GET", "/shopping").text)
    assert boundary in shown
    assert "Кефир" in shown
    assert harness.count("shopping") == 6
    assert harness.count("todos") == 5


@pytest.mark.acceptance
def test_add_valid_title_htmx_request_gets_fragment_with_new_item(harness: Harness) -> None:
    harness.seed_both_lists()
    response = harness.request(
        "POST", "/todos/add", htmx=True, data={"title": "Записаться к врачу"}
    )
    assert response.status_code == 200
    assert_fragment(response.text)
    assert "location" not in response.headers
    assert "Записаться к врачу" in page_titles(response.text)
    assert len(page_titles(response.text)) == 5
    assert "error" not in response.text.split("<ul")[0]


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
def test_toggle_twice_returns_original_state_and_persists_on_reload(
    harness: Harness, path: str, kind: str, title: str
) -> None:
    harness.seed_both_lists()
    target = "Яйца" if kind == "shopping" else "Забрать посылку"
    item_id = harness.item_id(kind, target)
    original = harness.state(item_id)
    assert original[2] == 0
    first = harness.request("POST", f"{path}/{item_id}/toggle")
    assert first.status_code == 303
    assert first.headers["location"] == path
    assert harness.state(item_id)[2] == 1
    assert (target, True) in page_items(harness.request("GET", path).text)
    assert (target, True) in page_items(harness.request("GET", path).text)
    second = harness.request("POST", f"{path}/{item_id}/toggle")
    assert second.status_code == 303
    assert harness.state(item_id) == original
    assert (target, False) in page_items(harness.request("GET", path).text)


@pytest.mark.acceptance
def test_toggle_htmx_request_gets_fragment_and_reflects_new_state(harness: Harness) -> None:
    harness.seed_both_lists()
    item_id = harness.item_id("shopping", "Молоко")
    response = harness.request("POST", f"/shopping/{item_id}/toggle", htmx=True)
    assert response.status_code == 200
    assert_fragment(response.text)
    assert ("Молоко", True) in page_items(response.text)
    back = harness.request("POST", f"/shopping/{item_id}/toggle", htmx=True)
    assert ("Молоко", False) in page_items(back.text)


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
def test_toggle_reopening_a_done_item_restores_it_among_open_items(
    harness: Harness, path: str, kind: str, title: str
) -> None:
    harness.seed_both_lists()
    done_title = "Хлеб" if kind == "shopping" else "Позвонить маме"
    assert (done_title, True) in page_items(harness.request("GET", path).text)
    item_id = harness.item_id(kind, done_title)
    assert harness.request("POST", f"{path}/{item_id}/toggle").status_code == 303
    assert (done_title, False) in page_items(harness.request("GET", path).text)
    assert harness.state(item_id)[4] is None


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
def test_rename_to_valid_title_is_saved(harness: Harness, path: str, kind: str, title: str) -> None:
    harness.seed_both_lists()
    target = "Сыр" if kind == "shopping" else "Купить билеты"
    item_id = harness.item_id(kind, target)
    response = harness.request("POST", f"{path}/{item_id}/rename", data={"title": "  Новое  "})
    assert response.status_code == 303
    assert response.headers["location"] == path
    shown = page_titles(harness.request("GET", path).text)
    assert "Новое" in shown
    assert target not in shown
    assert len(shown) == 4
    assert harness.state(item_id)[1] == "Новое"


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
@pytest.mark.parametrize("bad_title", ["", "   ", "q" * 201])
def test_rename_to_invalid_title_is_rejected_and_previous_title_stays(
    harness: Harness, path: str, kind: str, title: str, bad_title: str
) -> None:
    harness.seed_both_lists()
    target = "Сыр" if kind == "shopping" else "Купить билеты"
    item_id = harness.item_id(kind, target)
    before = harness.dump()
    response = harness.request("POST", f"{path}/{item_id}/rename", data={"title": bad_title})
    assert response.status_code == 422
    assert_full_page(response.text)
    assert INVALID_TITLE_MESSAGE in response.text
    assert target in page_titles(response.text)
    assert harness.dump() == before
    assert target in page_titles(harness.request("GET", path).text)


@pytest.mark.acceptance
def test_rename_invalid_title_htmx_request_gets_fragment_with_error(harness: Harness) -> None:
    harness.seed_both_lists()
    item_id = harness.item_id("todos", "Забрать посылку")
    before = harness.dump()
    response = harness.request("POST", f"/todos/{item_id}/rename", htmx=True, data={"title": " "})
    assert response.status_code == 200
    assert_fragment(response.text)
    assert INVALID_TITLE_MESSAGE in response.text
    assert "Забрать посылку" in page_titles(response.text)
    assert harness.dump() == before


@pytest.mark.acceptance
def test_rename_valid_title_htmx_request_gets_fragment_with_new_title(harness: Harness) -> None:
    harness.seed_both_lists()
    item_id = harness.item_id("shopping", "Яйца")
    response = harness.request(
        "POST", f"/shopping/{item_id}/rename", htmx=True, data={"title": "Яйца С1"}
    )
    assert response.status_code == 200
    assert_fragment(response.text)
    assert "Яйца С1" in page_titles(response.text)
    assert "Яйца" not in page_titles(response.text)


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
def test_delete_removes_item_from_page_and_database_only_for_that_item(
    harness: Harness, path: str, kind: str, title: str
) -> None:
    harness.seed_both_lists()
    target = "Хлеб" if kind == "shopping" else "Позвонить маме"
    item_id = harness.item_id(kind, target)
    other_kind = "todos" if kind == "shopping" else "shopping"
    other_before = harness.rows(
        "SELECT * FROM checklist_items WHERE kind = ? ORDER BY id", (other_kind,)
    )
    response = harness.request("POST", f"{path}/{item_id}/delete")
    assert response.status_code == 303
    assert response.headers["location"] == path
    shown = page_titles(harness.request("GET", path).text)
    assert target not in shown
    assert len(shown) == 3
    assert harness.rows("SELECT id FROM checklist_items WHERE id = ?", (item_id,)) == []
    assert (
        harness.rows("SELECT * FROM checklist_items WHERE kind = ? ORDER BY id", (other_kind,))
        == other_before
    )


@pytest.mark.acceptance
def test_delete_htmx_request_gets_fragment_without_item(harness: Harness) -> None:
    harness.seed_both_lists()
    item_id = harness.item_id("shopping", "Сыр")
    response = harness.request("POST", f"/shopping/{item_id}/delete", htmx=True)
    assert response.status_code == 200
    assert_fragment(response.text)
    assert "Сыр" not in page_titles(response.text)
    assert len(page_titles(response.text)) == 3


@pytest.mark.acceptance
def test_deleting_every_item_shows_empty_list_message(harness: Harness) -> None:
    harness.seed("/shopping", ["Один", "Два"])
    for title in ["Один", "Два"]:
        item_id = harness.item_id("shopping", title)
        assert harness.request("POST", f"/shopping/{item_id}/delete").status_code == 303
    page = harness.request("GET", "/shopping").text
    assert page_titles(page) == []
    assert "Список пуст" in page


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
def test_page_order_open_by_add_time_then_done_by_latest_done_first(
    harness: Harness, path: str, kind: str, title: str
) -> None:
    harness.seed(path, ["A-первый", "B-второй", "C-третий", "D-четвёртый"])
    assert page_titles(harness.request("GET", path).text) == [
        "A-первый",
        "B-второй",
        "C-третий",
        "D-четвёртый",
    ]
    harness.toggle(path, kind, "C-третий")
    time.sleep(0.05)
    harness.toggle(path, kind, "B-второй")
    page = harness.request("GET", path).text
    assert page_items(page) == [
        ("A-первый", False),
        ("D-четвёртый", False),
        ("B-второй", True),
        ("C-третий", True),
    ]
    fragment = harness.request("GET", path, htmx=True).text
    assert page_items(fragment) == page_items(page)


@pytest.mark.acceptance
def test_item_added_by_first_user_is_changed_by_third_user_in_both_lists(
    harness: Harness,
) -> None:
    harness.seed("/shopping", ["Анин пакет"], user="anna")
    harness.seed("/todos", ["Анино дело", "Анино второе"], user="anna")
    for path, kind, title in [
        ("/shopping", "shopping", "Анин пакет"),
        ("/todos", "todos", "Анино дело"),
    ]:
        item_id = harness.item_id(kind, title)
        toggled = harness.request("POST", f"{path}/{item_id}/toggle", user="vera")
        assert toggled.status_code == 303
        assert harness.state(item_id)[2] == 1
        renamed = harness.request(
            "POST", f"{path}/{item_id}/rename", user="vera", data={"title": f"Вера: {title}"}
        )
        assert renamed.status_code == 303
        page = harness.request("GET", path, user="vera").text
        assert (f"Вера: {title}", True) in page_items(page)
        assert "anna" not in page.lower()
        assert "alpha" not in page.lower()
        deleted = harness.request("POST", f"{path}/{item_id}/delete", user="vera")
        assert deleted.status_code == 303
        assert harness.rows("SELECT id FROM checklist_items WHERE id = ?", (item_id,)) == []
    assert page_titles(harness.request("GET", "/todos", user="boris").text) == ["Анино второе"]


@pytest.mark.acceptance
def test_items_carry_no_owner_marker_in_storage_or_pages(harness: Harness) -> None:
    harness.seed_both_lists()
    columns = [row[1] for row in harness.rows("PRAGMA table_info(checklist_items)")]
    assert sorted(columns) == ["created_at", "done_at", "id", "is_done", "kind", "title"]
    for user in ["anna", "boris", "vera"]:
        for path in ["/shopping", "/todos"]:
            page = harness.request("GET", path, user=user).text.lower()
            assert "anna" not in page
            assert "boris" not in page
            assert "vera" not in page


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
@pytest.mark.parametrize(("operation", "data"), MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_missing_item_plain_request_gets_404_page_and_nothing_changes(
    harness: Harness,
    path: str,
    kind: str,
    title: str,
    operation: str,
    data: dict[str, str],
) -> None:
    harness.seed_both_lists()
    before = harness.dump()
    response = harness.request("POST", f"{path}/99999/{operation}", data=data)
    assert response.status_code == 404
    assert_full_page(response.text)
    assert NOT_FOUND_MESSAGE in response.text
    assert harness.dump() == before


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
@pytest.mark.parametrize(("operation", "data"), MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_missing_item_htmx_request_gets_fragment_with_error(
    harness: Harness,
    path: str,
    kind: str,
    title: str,
    operation: str,
    data: dict[str, str],
) -> None:
    harness.seed_both_lists()
    before = harness.dump()
    response = harness.request("POST", f"{path}/99999/{operation}", htmx=True, data=data)
    assert response.status_code == 200
    assert_fragment(response.text)
    assert NOT_FOUND_MESSAGE in response.text
    assert len(page_titles(response.text)) == 4
    assert harness.dump() == before


@pytest.mark.acceptance
@pytest.mark.parametrize(("operation", "data"), MUTATIONS, ids=[m[0] for m in MUTATIONS])
@pytest.mark.parametrize("htmx", [False, True], ids=["plain", "htmx"])
@pytest.mark.parametrize(
    ("path", "foreign_kind", "foreign_title"),
    [("/shopping", "todos", "Забрать посылку"), ("/todos", "shopping", "Яйца")],
    ids=["todo-id-on-shopping", "shopping-id-on-todos"],
)
def test_item_id_of_the_other_list_is_not_found_and_other_list_is_untouched(
    harness: Harness,
    path: str,
    foreign_kind: str,
    foreign_title: str,
    htmx: bool,
    operation: str,
    data: dict[str, str],
) -> None:
    harness.seed_both_lists()
    foreign_id = harness.item_id(foreign_kind, foreign_title)
    before = harness.dump()
    response = harness.request("POST", f"{path}/{foreign_id}/{operation}", htmx=htmx, data=data)
    assert response.status_code == (200 if htmx else 404)
    assert NOT_FOUND_MESSAGE in response.text
    assert harness.dump() == before


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
@pytest.mark.parametrize(("operation", "data"), MUTATIONS, ids=[m[0] for m in MUTATIONS])
@pytest.mark.parametrize("item_id", ["abc", "1.5", "-x"])
def test_non_integer_item_id_gets_422_and_nothing_changes(
    harness: Harness,
    path: str,
    kind: str,
    title: str,
    operation: str,
    data: dict[str, str],
    item_id: str,
) -> None:
    harness.seed_both_lists()
    before = harness.dump()
    response = harness.request("POST", f"{path}/{item_id}/{operation}", data=data)
    assert response.status_code == 422
    assert harness.dump() == before


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
@pytest.mark.parametrize("operation", ["add", "toggle", "rename", "delete"])
@pytest.mark.parametrize("htmx", [False, True], ids=["plain", "htmx"])
def test_get_on_mutating_routes_returns_405_and_does_not_change_database(
    harness: Harness, path: str, kind: str, title: str, operation: str, htmx: bool
) -> None:
    harness.seed_both_lists()
    item_id = harness.item_id(kind, "Яйца" if kind == "shopping" else "Забрать посылку")
    before = harness.dump()
    url = f"{path}/add" if operation == "add" else f"{path}/{item_id}/{operation}"
    response = harness.request("GET", url, htmx=htmx)
    assert response.status_code == 405
    assert harness.dump() == before


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_other_verbs_on_mutating_routes_are_not_allowed(
    harness: Harness, path: str, kind: str, title: str, method: str
) -> None:
    harness.seed_both_lists()
    item_id = harness.item_id(kind, "Яйца" if kind == "shopping" else "Забрать посылку")
    before = harness.dump()
    for url in [f"{path}/add", f"{path}/{item_id}/toggle", f"{path}/{item_id}/rename"]:
        assert harness.request(method, url).status_code == 405
    assert harness.request(method, f"{path}/{item_id}/delete").status_code == 405
    assert harness.dump() == before


@pytest.mark.acceptance
def test_repeated_get_of_pages_never_changes_database_state(harness: Harness) -> None:
    harness.seed_both_lists()
    before = harness.dump()
    for _ in range(3):
        for path in ["/shopping", "/todos"]:
            for htmx in [False, True]:
                assert harness.request("GET", path, htmx=htmx).status_code == 200
            assert harness.request("GET", path, user="vera").status_code == 200
    assert harness.dump() == before


@pytest.mark.acceptance
@pytest.mark.parametrize("path", ["/shopping", "/todos"])
def test_unauthenticated_get_redirects_to_login(harness: Harness, path: str) -> None:
    harness.seed_both_lists()
    response = harness.request("GET", path, user=None)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert "Молоко" not in response.text


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
@pytest.mark.parametrize("operation", ["add", "toggle", "rename", "delete"])
def test_unauthenticated_post_redirects_to_login_and_changes_nothing(
    harness: Harness, path: str, kind: str, title: str, operation: str
) -> None:
    harness.seed_both_lists()
    item_id = harness.item_id(kind, "Яйца" if kind == "shopping" else "Забрать посылку")
    before = harness.dump()
    url = f"{path}/add" if operation == "add" else f"{path}/{item_id}/{operation}"
    response = harness.request("POST", url, user=None, data={"title": "Чужое"})
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert harness.dump() == before


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
@pytest.mark.parametrize("operation", ["page", "add", "toggle", "rename", "delete"])
def test_unauthenticated_htmx_request_gets_hx_redirect_and_changes_nothing(
    harness: Harness, path: str, kind: str, title: str, operation: str
) -> None:
    harness.seed_both_lists()
    item_id = harness.item_id(kind, "Яйца" if kind == "shopping" else "Забрать посылку")
    before = harness.dump()
    if operation == "page":
        response = harness.request("GET", path, user=None, htmx=True)
    else:
        url = f"{path}/add" if operation == "add" else f"{path}/{item_id}/{operation}"
        response = harness.request("POST", url, user=None, htmx=True, data={"title": "Чужое"})
    assert response.status_code == 200
    assert response.headers["HX-Redirect"] == "/login"
    assert response.content == b""
    assert harness.dump() == before


@pytest.mark.acceptance
@pytest.mark.parametrize(("path", "kind", "title"), LISTS, ids=LIST_IDS)
def test_script_title_is_shown_escaped_on_page_fragment_and_rename_input(
    harness: Harness, path: str, kind: str, title: str
) -> None:
    harness.seed_both_lists()
    payload = "<script>alert(1)</script>"
    response = harness.request("POST", f"{path}/add", data={"title": payload})
    assert response.status_code == 303
    page = harness.request("GET", path).text
    assert payload not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert payload in page_titles(page)
    fragment = harness.request("GET", path, htmx=True).text
    assert payload not in fragment
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in fragment
    item_id = harness.item_id(kind, payload)
    renamed = harness.request(
        "POST", f"{path}/{item_id}/rename", htmx=True, data={"title": "<b>жирный</b>"}
    )
    assert "<b>жирный</b>" not in renamed.text
    assert "&lt;b&gt;жирный&lt;/b&gt;" in renamed.text
