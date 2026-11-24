import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response

from dashboard.database import get_connection
from dashboard.services.checklist_items import (
    MAX_TITLE_LENGTH,
    ChecklistItemNotFoundError,
    ChecklistKind,
    InvalidTitleError,
    add_item,
    delete_item,
    list_items,
    rename_item,
    toggle_item,
)

PAGE_TEMPLATE = "checklist.html"
FRAGMENT_TEMPLATE = "_checklist_items.html"
INVALID_TITLE_MESSAGE = f"Название должно быть от 1 до {MAX_TITLE_LENGTH} символов"
ITEM_NOT_FOUND_MESSAGE = "Позиция не найдена"


@dataclass(frozen=True)
class Checklist:
    """A checklist kind with its page path and display title."""

    kind: ChecklistKind
    path: str
    title: str


CHECKLISTS = (
    Checklist(ChecklistKind.SHOPPING, "/shopping", "Покупки"),
    Checklist(ChecklistKind.TODOS, "/todos", "Дела"),
)

router = APIRouter()


def _render_checklist(
    request: Request,
    connection: sqlite3.Connection,
    checklist: Checklist,
    status_code: int,
    error: str | None,
) -> Response:
    from dashboard.main import HTMX_REQUEST_HEADER, templates

    is_htmx = request.headers.get(HTMX_REQUEST_HEADER) == "true"
    context = {
        "checklist_title": checklist.title,
        "checklist_path": checklist.path,
        "items": list_items(connection, checklist.kind),
        "error": error,
    }
    template_name = FRAGMENT_TEMPLATE if is_htmx else PAGE_TEMPLATE
    return templates.TemplateResponse(
        request, template_name, context, status_code=200 if is_htmx else status_code
    )


def _respond_after_change(
    request: Request,
    connection: sqlite3.Connection,
    checklist: Checklist,
    change: Callable[[], object],
) -> Response:
    from dashboard.main import HTMX_REQUEST_HEADER

    try:
        change()
    except InvalidTitleError:
        return _render_checklist(request, connection, checklist, 422, INVALID_TITLE_MESSAGE)
    except ChecklistItemNotFoundError:
        return _render_checklist(request, connection, checklist, 404, ITEM_NOT_FOUND_MESSAGE)
    if request.headers.get(HTMX_REQUEST_HEADER) == "true":
        return _render_checklist(request, connection, checklist, 200, None)
    return RedirectResponse(checklist.path, status_code=303)


def _register(checklist: Checklist) -> None:
    kind = checklist.kind
    path = checklist.path
    prefix = kind.value

    @router.get(path, name=f"show_{prefix}")
    def show_checklist(
        request: Request,
        connection: Annotated[sqlite3.Connection, Depends(get_connection)],
    ) -> Response:
        """Render the checklist page."""
        return _render_checklist(request, connection, checklist, 200, None)

    @router.post(f"{path}/add", name=f"add_{prefix}")
    def submit_add(
        request: Request,
        connection: Annotated[sqlite3.Connection, Depends(get_connection)],
        title: Annotated[str, Form()] = "",
    ) -> Response:
        """Add an item to the checklist."""
        return _respond_after_change(
            request, connection, checklist, lambda: add_item(connection, kind, title)
        )

    @router.post(f"{path}/{{item_id}}/toggle", name=f"toggle_{prefix}")
    def submit_toggle(
        request: Request,
        item_id: int,
        connection: Annotated[sqlite3.Connection, Depends(get_connection)],
    ) -> Response:
        """Mark the item as done or reopen it."""
        return _respond_after_change(
            request, connection, checklist, lambda: toggle_item(connection, kind, item_id)
        )

    @router.post(f"{path}/{{item_id}}/rename", name=f"rename_{prefix}")
    def submit_rename(
        request: Request,
        item_id: int,
        connection: Annotated[sqlite3.Connection, Depends(get_connection)],
        title: Annotated[str, Form()] = "",
    ) -> Response:
        """Rename the item."""
        return _respond_after_change(
            request, connection, checklist, lambda: rename_item(connection, kind, item_id, title)
        )

    @router.post(f"{path}/{{item_id}}/delete", name=f"delete_{prefix}")
    def submit_delete(
        request: Request,
        item_id: int,
        connection: Annotated[sqlite3.Connection, Depends(get_connection)],
    ) -> Response:
        """Delete the item."""
        return _respond_after_change(
            request, connection, checklist, lambda: delete_item(connection, kind, item_id)
        )


for _checklist in CHECKLISTS:
    _register(_checklist)
