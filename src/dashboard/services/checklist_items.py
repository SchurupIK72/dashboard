import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

MAX_TITLE_LENGTH = 200

SELECT_ITEMS_SQL = "SELECT id, kind, title, is_done, created_at, done_at FROM checklist_items"


class ChecklistKind(StrEnum):
    """The checklist an item belongs to."""

    SHOPPING = "shopping"
    TODOS = "todos"


@dataclass(frozen=True)
class ChecklistItem:
    """A shopping or to-do list entry with its completion state."""

    id: int
    kind: ChecklistKind
    title: str
    is_done: bool
    created_at: str
    done_at: str | None


class InvalidTitleError(Exception):
    """Raised when a title is empty after trimming or longer than the allowed length."""


class ChecklistItemNotFoundError(Exception):
    """Raised when the checklist has no item with the given id."""


def _validate_title(title: str) -> str:
    trimmed = title.strip()
    if not 1 <= len(trimmed) <= MAX_TITLE_LENGTH:
        raise InvalidTitleError(f"Название должно быть от 1 до {MAX_TITLE_LENGTH} символов")
    return trimmed


def _timestamp(now: datetime | None) -> str:
    if now is None:
        moment = datetime.now(UTC)
    elif now.tzinfo is None:
        moment = now.replace(tzinfo=UTC)
    else:
        moment = now.astimezone(UTC)
    return moment.isoformat(timespec="microseconds")


def _to_item(row: sqlite3.Row) -> ChecklistItem:
    done_at = row["done_at"]
    return ChecklistItem(
        id=int(row["id"]),
        kind=ChecklistKind(str(row["kind"])),
        title=str(row["title"]),
        is_done=bool(row["is_done"]),
        created_at=str(row["created_at"]),
        done_at=None if done_at is None else str(done_at),
    )


def _find_item(connection: sqlite3.Connection, kind: ChecklistKind, item_id: int) -> ChecklistItem:
    row = connection.execute(
        f"{SELECT_ITEMS_SQL} WHERE id = ? AND kind = ?", (item_id, kind.value)
    ).fetchone()
    if row is None:
        raise ChecklistItemNotFoundError(f"Позиция {item_id} не найдена")
    return _to_item(row)


def add_item(
    connection: sqlite3.Connection,
    kind: ChecklistKind,
    title: str,
    now: datetime | None = None,
) -> ChecklistItem:
    """Add an open item with the trimmed title to the checklist and return it."""
    trimmed = _validate_title(title)
    cursor = connection.execute(
        "INSERT INTO checklist_items (kind, title, is_done, created_at, done_at) "
        "VALUES (?, ?, 0, ?, NULL)",
        (kind.value, trimmed, _timestamp(now)),
    )
    connection.commit()
    if cursor.lastrowid is None:
        raise ChecklistItemNotFoundError("Не удалось добавить позицию")
    return _find_item(connection, kind, cursor.lastrowid)


def list_items(connection: sqlite3.Connection, kind: ChecklistKind) -> list[ChecklistItem]:
    """Return open items oldest first followed by done items most recently done first."""
    open_rows = connection.execute(
        f"{SELECT_ITEMS_SQL} WHERE kind = ? AND is_done = 0 ORDER BY created_at ASC, id ASC",
        (kind.value,),
    ).fetchall()
    done_rows = connection.execute(
        f"{SELECT_ITEMS_SQL} WHERE kind = ? AND is_done = 1 ORDER BY done_at DESC, id DESC",
        (kind.value,),
    ).fetchall()
    return [_to_item(row) for row in open_rows + done_rows]


def toggle_item(
    connection: sqlite3.Connection,
    kind: ChecklistKind,
    item_id: int,
    now: datetime | None = None,
) -> ChecklistItem:
    """Mark an open item as done or reopen a done item and return the updated item."""
    item = _find_item(connection, kind, item_id)
    if item.is_done:
        connection.execute(
            "UPDATE checklist_items SET is_done = 0, done_at = NULL WHERE id = ? AND kind = ?",
            (item_id, kind.value),
        )
    else:
        connection.execute(
            "UPDATE checklist_items SET is_done = 1, done_at = ? WHERE id = ? AND kind = ?",
            (_timestamp(now), item_id, kind.value),
        )
    connection.commit()
    return _find_item(connection, kind, item_id)


def rename_item(
    connection: sqlite3.Connection, kind: ChecklistKind, item_id: int, title: str
) -> ChecklistItem:
    """Replace the item title with the trimmed new title and return the updated item."""
    trimmed = _validate_title(title)
    _find_item(connection, kind, item_id)
    connection.execute(
        "UPDATE checklist_items SET title = ? WHERE id = ? AND kind = ?",
        (trimmed, item_id, kind.value),
    )
    connection.commit()
    return _find_item(connection, kind, item_id)


def delete_item(connection: sqlite3.Connection, kind: ChecklistKind, item_id: int) -> None:
    """Delete the item from the checklist."""
    _find_item(connection, kind, item_id)
    connection.execute(
        "DELETE FROM checklist_items WHERE id = ? AND kind = ?", (item_id, kind.value)
    )
    connection.commit()
