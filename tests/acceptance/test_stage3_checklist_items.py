import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from dashboard.database import connect, initialize_schema
from dashboard.services.checklist_items import (
    ChecklistItem,
    ChecklistItemNotFoundError,
    ChecklistKind,
    InvalidTitleError,
    add_item,
    delete_item,
    list_items,
    rename_item,
    toggle_item,
)

BASE = datetime(2026, 3, 1, 10, 0, 0)


def minutes(count: int) -> datetime:
    return BASE + timedelta(minutes=count)


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    opened = connect(tmp_path / "x.db")
    initialize_schema(opened)
    yield opened
    opened.close()


def titles(connection: sqlite3.Connection, kind: ChecklistKind) -> list[str]:
    return [item.title for item in list_items(connection, kind)]


def seed(connection: sqlite3.Connection) -> dict[str, ChecklistItem]:
    return {
        "milk": add_item(connection, ChecklistKind.SHOPPING, "Молоко", minutes(1)),
        "bread": add_item(connection, ChecklistKind.SHOPPING, "Хлеб", minutes(2)),
        "rice": add_item(connection, ChecklistKind.SHOPPING, "Рис", minutes(3)),
        "visa": add_item(connection, ChecklistKind.TODOS, "Продлить визу", minutes(4)),
        "sim": add_item(connection, ChecklistKind.TODOS, "Купить SIM", minutes(5)),
    }


@pytest.mark.acceptance
def test_add_item_returns_open_item_with_trimmed_title(connection: sqlite3.Connection) -> None:
    item = add_item(connection, ChecklistKind.SHOPPING, "  Молоко \t", minutes(0))
    assert item.title == "Молоко"
    assert item.kind is ChecklistKind.SHOPPING
    assert item.is_done is False
    assert item.done_at is None
    assert item.id >= 1
    assert titles(connection, ChecklistKind.SHOPPING) == ["Молоко"]


@pytest.mark.acceptance
def test_add_item_stores_trimmed_title_in_database(connection: sqlite3.Connection) -> None:
    add_item(connection, ChecklistKind.TODOS, "   Забрать посылку  ", minutes(0))
    row = connection.execute("SELECT title, kind, is_done, done_at FROM checklist_items").fetchone()
    assert row["title"] == "Забрать посылку"
    assert row["kind"] == "todos"
    assert row["is_done"] == 0
    assert row["done_at"] is None


@pytest.mark.acceptance
@pytest.mark.parametrize("length", [1, 200])
def test_add_item_accepts_boundary_lengths(connection: sqlite3.Connection, length: int) -> None:
    title = "я" * length
    item = add_item(connection, ChecklistKind.SHOPPING, title, minutes(0))
    assert item.title == title
    assert len(titles(connection, ChecklistKind.SHOPPING)[0]) == length


@pytest.mark.acceptance
def test_add_item_accepts_200_chars_with_surrounding_spaces(
    connection: sqlite3.Connection,
) -> None:
    item = add_item(connection, ChecklistKind.TODOS, "  " + "б" * 200 + "  ", minutes(0))
    assert item.title == "б" * 200


@pytest.mark.acceptance
@pytest.mark.parametrize("bad_title", ["", "   ", "\t\n ", "x" * 201, " " + "x" * 201 + " "])
def test_add_item_rejects_invalid_title_and_keeps_list(
    connection: sqlite3.Connection, bad_title: str
) -> None:
    seed(connection)
    before = list_items(connection, ChecklistKind.SHOPPING)
    before_todos = list_items(connection, ChecklistKind.TODOS)
    with pytest.raises(InvalidTitleError):
        add_item(connection, ChecklistKind.SHOPPING, bad_title, minutes(10))
    assert list_items(connection, ChecklistKind.SHOPPING) == before
    assert list_items(connection, ChecklistKind.TODOS) == before_todos
    assert connection.execute("SELECT COUNT(*) FROM checklist_items").fetchone()[0] == 5


@pytest.mark.acceptance
def test_kinds_are_stored_separately(connection: sqlite3.Connection) -> None:
    seed(connection)
    assert titles(connection, ChecklistKind.SHOPPING) == ["Молоко", "Хлеб", "Рис"]
    assert titles(connection, ChecklistKind.TODOS) == ["Продлить визу", "Купить SIM"]
    kinds = {item.kind for item in list_items(connection, ChecklistKind.SHOPPING)} | {
        item.kind for item in list_items(connection, ChecklistKind.TODOS)
    }
    assert kinds == {ChecklistKind.SHOPPING, ChecklistKind.TODOS}


@pytest.mark.acceptance
def test_same_title_in_both_kinds_is_independent(connection: sqlite3.Connection) -> None:
    shopping = add_item(connection, ChecklistKind.SHOPPING, "Вода", minutes(1))
    todos = add_item(connection, ChecklistKind.TODOS, "Вода", minutes(2))
    toggle_item(connection, ChecklistKind.SHOPPING, shopping.id, minutes(3))
    assert list_items(connection, ChecklistKind.SHOPPING)[0].is_done is True
    assert list_items(connection, ChecklistKind.TODOS)[0].id == todos.id
    assert list_items(connection, ChecklistKind.TODOS)[0].is_done is False


@pytest.mark.acceptance
def test_timestamps_naive_is_utc_with_microseconds(connection: sqlite3.Connection) -> None:
    item = add_item(connection, ChecklistKind.SHOPPING, "Яйца", datetime(2026, 3, 1, 10, 0, 0))
    assert item.created_at == "2026-03-01T10:00:00.000000+00:00"
    done = toggle_item(
        connection, ChecklistKind.SHOPPING, item.id, datetime(2026, 3, 1, 11, 30, 5, 123456)
    )
    assert done.done_at == "2026-03-01T11:30:05.123456+00:00"


@pytest.mark.acceptance
def test_timestamps_aware_is_converted_to_utc(connection: sqlite3.Connection) -> None:
    zone = timezone(timedelta(hours=7))
    item = add_item(
        connection, ChecklistKind.SHOPPING, "Фрукты", datetime(2026, 3, 1, 17, 0, 0, tzinfo=zone)
    )
    assert item.created_at == "2026-03-01T10:00:00.000000+00:00"
    done = toggle_item(
        connection,
        ChecklistKind.SHOPPING,
        item.id,
        datetime(2026, 3, 1, 20, 0, 0, tzinfo=zone),
    )
    assert done.done_at == "2026-03-01T13:00:00.000000+00:00"


@pytest.mark.acceptance
def test_default_now_is_current_utc(connection: sqlite3.Connection) -> None:
    before = datetime.now(UTC)
    item = add_item(connection, ChecklistKind.TODOS, "Сейчас")
    toggled = toggle_item(connection, ChecklistKind.TODOS, item.id)
    after = datetime.now(UTC)
    assert before <= datetime.fromisoformat(item.created_at) <= after
    assert toggled.done_at is not None
    assert before <= datetime.fromisoformat(toggled.done_at) <= after


@pytest.mark.acceptance
def test_toggle_marks_done_and_sets_done_at(connection: sqlite3.Connection) -> None:
    items = seed(connection)
    done = toggle_item(connection, ChecklistKind.SHOPPING, items["bread"].id, minutes(20))
    assert done.is_done is True
    assert done.done_at == "2026-03-01T10:20:00.000000+00:00"
    assert done.title == "Хлеб"
    untouched = {item.title: item for item in list_items(connection, ChecklistKind.SHOPPING)}
    assert untouched["Молоко"].is_done is False
    assert untouched["Рис"].is_done is False
    assert all(not item.is_done for item in list_items(connection, ChecklistKind.TODOS))


@pytest.mark.acceptance
def test_double_toggle_restores_original_state(connection: sqlite3.Connection) -> None:
    items = seed(connection)
    original = list_items(connection, ChecklistKind.SHOPPING)
    toggle_item(connection, ChecklistKind.SHOPPING, items["milk"].id, minutes(20))
    reopened = toggle_item(connection, ChecklistKind.SHOPPING, items["milk"].id, minutes(21))
    assert reopened.is_done is False
    assert reopened.done_at is None
    assert list_items(connection, ChecklistKind.SHOPPING) == original


@pytest.mark.acceptance
def test_toggle_state_persists_across_connections(tmp_path: Path) -> None:
    path = tmp_path / "persist.db"
    first = connect(path)
    initialize_schema(first)
    items = seed(first)
    toggle_item(first, ChecklistKind.TODOS, items["visa"].id, minutes(30))
    rename_item(first, ChecklistKind.SHOPPING, items["rice"].id, "Рис басмати")
    delete_item(first, ChecklistKind.SHOPPING, items["bread"].id)
    first.close()
    second = connect(path)
    try:
        todos = list_items(second, ChecklistKind.TODOS)
        assert [(item.title, item.is_done) for item in todos] == [
            ("Купить SIM", False),
            ("Продлить визу", True),
        ]
        assert titles(second, ChecklistKind.SHOPPING) == ["Молоко", "Рис басмати"]
    finally:
        second.close()


@pytest.mark.acceptance
def test_toggle_missing_id_raises(connection: sqlite3.Connection) -> None:
    seed(connection)
    with pytest.raises(ChecklistItemNotFoundError):
        toggle_item(connection, ChecklistKind.SHOPPING, 9999, minutes(1))


@pytest.mark.acceptance
def test_operations_with_id_of_other_kind_raise_and_change_nothing(
    connection: sqlite3.Connection,
) -> None:
    items = seed(connection)
    shopping_before = list_items(connection, ChecklistKind.SHOPPING)
    todos_before = list_items(connection, ChecklistKind.TODOS)
    foreign_todo = items["visa"].id
    foreign_shopping = items["milk"].id
    with pytest.raises(ChecklistItemNotFoundError):
        toggle_item(connection, ChecklistKind.SHOPPING, foreign_todo, minutes(40))
    with pytest.raises(ChecklistItemNotFoundError):
        rename_item(connection, ChecklistKind.SHOPPING, foreign_todo, "Взлом")
    with pytest.raises(ChecklistItemNotFoundError):
        delete_item(connection, ChecklistKind.SHOPPING, foreign_todo)
    with pytest.raises(ChecklistItemNotFoundError):
        toggle_item(connection, ChecklistKind.TODOS, foreign_shopping, minutes(40))
    with pytest.raises(ChecklistItemNotFoundError):
        delete_item(connection, ChecklistKind.TODOS, foreign_shopping)
    assert list_items(connection, ChecklistKind.SHOPPING) == shopping_before
    assert list_items(connection, ChecklistKind.TODOS) == todos_before


@pytest.mark.acceptance
def test_rename_saves_trimmed_title(connection: sqlite3.Connection) -> None:
    items = seed(connection)
    renamed = rename_item(connection, ChecklistKind.SHOPPING, items["bread"].id, "  Багет  ")
    assert renamed.title == "Багет"
    assert renamed.id == items["bread"].id
    assert renamed.created_at == items["bread"].created_at
    assert titles(connection, ChecklistKind.SHOPPING) == ["Молоко", "Багет", "Рис"]


@pytest.mark.acceptance
@pytest.mark.parametrize("length", [1, 200])
def test_rename_accepts_boundary_lengths(connection: sqlite3.Connection, length: int) -> None:
    items = seed(connection)
    renamed = rename_item(connection, ChecklistKind.TODOS, items["sim"].id, "ж" * length)
    assert renamed.title == "ж" * length


@pytest.mark.acceptance
@pytest.mark.parametrize("bad_title", ["", "    ", "x" * 201])
def test_rename_rejects_invalid_title_and_keeps_old(
    connection: sqlite3.Connection, bad_title: str
) -> None:
    items = seed(connection)
    before = list_items(connection, ChecklistKind.SHOPPING)
    with pytest.raises(InvalidTitleError):
        rename_item(connection, ChecklistKind.SHOPPING, items["milk"].id, bad_title)
    assert list_items(connection, ChecklistKind.SHOPPING) == before
    assert before[0].title == "Молоко"


@pytest.mark.acceptance
def test_rename_validates_title_before_lookup(connection: sqlite3.Connection) -> None:
    seed(connection)
    with pytest.raises(InvalidTitleError):
        rename_item(connection, ChecklistKind.SHOPPING, 9999, "   ")


@pytest.mark.acceptance
def test_rename_missing_id_with_valid_title_raises_not_found(
    connection: sqlite3.Connection,
) -> None:
    seed(connection)
    with pytest.raises(ChecklistItemNotFoundError):
        rename_item(connection, ChecklistKind.SHOPPING, 9999, "Нет такого")


@pytest.mark.acceptance
def test_rename_keeps_done_state(connection: sqlite3.Connection) -> None:
    items = seed(connection)
    toggle_item(connection, ChecklistKind.SHOPPING, items["rice"].id, minutes(15))
    renamed = rename_item(connection, ChecklistKind.SHOPPING, items["rice"].id, "Рис длиннозёрный")
    assert renamed.is_done is True
    assert renamed.done_at == "2026-03-01T10:15:00.000000+00:00"


@pytest.mark.acceptance
def test_delete_removes_item_only_from_its_list(connection: sqlite3.Connection) -> None:
    items = seed(connection)
    assert delete_item(connection, ChecklistKind.SHOPPING, items["bread"].id) is None
    assert titles(connection, ChecklistKind.SHOPPING) == ["Молоко", "Рис"]
    assert titles(connection, ChecklistKind.TODOS) == ["Продлить визу", "Купить SIM"]
    assert (
        connection.execute(
            "SELECT COUNT(*) FROM checklist_items WHERE id = ?", (items["bread"].id,)
        ).fetchone()[0]
        == 0
    )


@pytest.mark.acceptance
def test_delete_done_item_and_repeat_delete_raises(connection: sqlite3.Connection) -> None:
    items = seed(connection)
    toggle_item(connection, ChecklistKind.TODOS, items["visa"].id, minutes(50))
    delete_item(connection, ChecklistKind.TODOS, items["visa"].id)
    assert titles(connection, ChecklistKind.TODOS) == ["Купить SIM"]
    with pytest.raises(ChecklistItemNotFoundError):
        delete_item(connection, ChecklistKind.TODOS, items["visa"].id)


@pytest.mark.acceptance
def test_list_items_empty_kind_is_empty_list(connection: sqlite3.Connection) -> None:
    add_item(connection, ChecklistKind.SHOPPING, "Соль", minutes(1))
    assert list_items(connection, ChecklistKind.TODOS) == []


@pytest.mark.acceptance
def test_order_open_by_created_asc_then_done_by_done_at_desc(
    connection: sqlite3.Connection,
) -> None:
    first = add_item(connection, ChecklistKind.SHOPPING, "A", minutes(1))
    second = add_item(connection, ChecklistKind.SHOPPING, "B", minutes(2))
    third = add_item(connection, ChecklistKind.SHOPPING, "C", minutes(3))
    fourth = add_item(connection, ChecklistKind.SHOPPING, "D", minutes(4))
    toggle_item(connection, ChecklistKind.SHOPPING, second.id, minutes(60))
    toggle_item(connection, ChecklistKind.SHOPPING, fourth.id, minutes(90))
    ordered = list_items(connection, ChecklistKind.SHOPPING)
    assert [item.title for item in ordered] == ["A", "C", "D", "B"]
    assert [item.is_done for item in ordered] == [False, False, True, True]
    assert ordered[0].id == first.id
    assert ordered[1].id == third.id


@pytest.mark.acceptance
def test_order_when_done_in_reverse_of_creation(connection: sqlite3.Connection) -> None:
    items = [
        add_item(connection, ChecklistKind.TODOS, name, minutes(index))
        for index, name in enumerate(["A", "B", "C", "D"], start=1)
    ]
    toggle_item(connection, ChecklistKind.TODOS, items[3].id, minutes(100))
    toggle_item(connection, ChecklistKind.TODOS, items[0].id, minutes(200))
    toggle_item(connection, ChecklistKind.TODOS, items[1].id, minutes(150))
    assert titles(connection, ChecklistKind.TODOS) == ["C", "A", "B", "D"]


@pytest.mark.acceptance
def test_order_reopened_item_returns_to_open_block_by_created_at(
    connection: sqlite3.Connection,
) -> None:
    items = [
        add_item(connection, ChecklistKind.SHOPPING, name, minutes(index))
        for index, name in enumerate(["A", "B", "C", "D"], start=1)
    ]
    toggle_item(connection, ChecklistKind.SHOPPING, items[0].id, minutes(70))
    toggle_item(connection, ChecklistKind.SHOPPING, items[2].id, minutes(80))
    toggle_item(connection, ChecklistKind.SHOPPING, items[0].id, minutes(90))
    assert titles(connection, ChecklistKind.SHOPPING) == ["A", "B", "D", "C"]


@pytest.mark.acceptance
def test_order_ties_broken_by_id(connection: sqlite3.Connection) -> None:
    moment = minutes(5)
    items = [add_item(connection, ChecklistKind.SHOPPING, name, moment) for name in ["A", "B", "C"]]
    assert titles(connection, ChecklistKind.SHOPPING) == ["A", "B", "C"]
    stamp = minutes(500)
    toggle_item(connection, ChecklistKind.SHOPPING, items[0].id, stamp)
    toggle_item(connection, ChecklistKind.SHOPPING, items[1].id, stamp)
    assert titles(connection, ChecklistKind.SHOPPING) == ["C", "B", "A"]


@pytest.mark.acceptance
def test_order_is_independent_of_insertion_order_of_timestamps(
    connection: sqlite3.Connection,
) -> None:
    late = add_item(connection, ChecklistKind.TODOS, "Поздняя", minutes(30))
    early = add_item(connection, ChecklistKind.TODOS, "Ранняя", minutes(10))
    middle = add_item(connection, ChecklistKind.TODOS, "Средняя", minutes(20))
    assert [item.id for item in list_items(connection, ChecklistKind.TODOS)] == [
        early.id,
        middle.id,
        late.id,
    ]


@pytest.mark.acceptance
def test_schema_is_idempotent_and_keeps_rows(tmp_path: Path) -> None:
    opened = connect(tmp_path / "twice.db")
    try:
        initialize_schema(opened)
        seed(opened)
        initialize_schema(opened)
        initialize_schema(opened)
        assert titles(opened, ChecklistKind.SHOPPING) == ["Молоко", "Хлеб", "Рис"]
        assert titles(opened, ChecklistKind.TODOS) == ["Продлить визу", "Купить SIM"]
    finally:
        opened.close()


@pytest.mark.acceptance
def test_table_columns_have_no_owner(connection: sqlite3.Connection) -> None:
    columns = [row["name"] for row in connection.execute("PRAGMA table_info(checklist_items)")]
    assert columns == ["id", "kind", "title", "is_done", "created_at", "done_at"]
    assert not any("user" in name or "owner" in name for name in columns)


@pytest.mark.acceptance
def test_check_rejects_unknown_kind(connection: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO checklist_items (kind, title, is_done, created_at) "
            "VALUES ('chores', 'x', 0, '2026-03-01T10:00:00.000000+00:00')"
        )


@pytest.mark.acceptance
def test_check_rejects_is_done_outside_zero_one(connection: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO checklist_items (kind, title, is_done, created_at) "
            "VALUES ('shopping', 'x', 2, '2026-03-01T10:00:00.000000+00:00')"
        )


@pytest.mark.acceptance
def test_check_accepts_both_valid_kinds_and_states(connection: sqlite3.Connection) -> None:
    for kind in ("shopping", "todos"):
        for state in (0, 1):
            connection.execute(
                "INSERT INTO checklist_items (kind, title, is_done, created_at) "
                "VALUES (?, 'x', ?, '2026-03-01T10:00:00.000000+00:00')",
                (kind, state),
            )
    assert connection.execute("SELECT COUNT(*) FROM checklist_items").fetchone()[0] == 4


@pytest.mark.acceptance
def test_sql_metacharacters_in_title_are_stored_literally(connection: sqlite3.Connection) -> None:
    seed(connection)
    hostile = "x'); DROP TABLE checklist_items; --"
    item = add_item(connection, ChecklistKind.SHOPPING, hostile, minutes(60))
    assert item.title == hostile
    renamed = rename_item(connection, ChecklistKind.SHOPPING, item.id, "' OR '1'='1")
    assert renamed.title == "' OR '1'='1"
    assert len(list_items(connection, ChecklistKind.SHOPPING)) == 4
    assert len(list_items(connection, ChecklistKind.TODOS)) == 2


@pytest.mark.acceptance
def test_schema_defines_kind_state_index(connection: sqlite3.Connection) -> None:
    indexes = {
        row["name"]: row["sql"]
        for row in connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'index' AND tbl_name = 'checklist_items'"
        )
    }
    assert "idx_checklist_items_kind_state" in indexes
    assert "kind" in indexes["idx_checklist_items_kind_state"]
