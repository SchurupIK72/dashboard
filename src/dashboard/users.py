import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from dashboard.passwords import DUMMY_PASSWORD_HASH, hash_password, verify_password
from dashboard.settings import UserSeed

REQUIRED_USER_COUNT = 3
REQUIRED_COMPANY_COUNT = 2

SELECT_USERS_SQL = (
    "SELECT users.id, users.login, users.company_id, companies.name AS company_name "
    "FROM users JOIN companies ON companies.id = users.company_id"
)


@dataclass(frozen=True)
class Company:
    """A company that shares expenses with the other one."""

    id: int
    name: str


@dataclass(frozen=True)
class User:
    """A dashboard user together with the company they belong to."""

    id: int
    login: str
    company_id: int
    company_name: str


class UserSeedError(Exception):
    """Raised when DASHBOARD_USERS is invalid or diverges from the database."""


def _validate_seeds(seeds: Sequence[UserSeed]) -> None:
    if len(seeds) != REQUIRED_USER_COUNT:
        raise UserSeedError(
            f"DASHBOARD_USERS должна содержать ровно {REQUIRED_USER_COUNT} пользователей"
        )
    logins: set[str] = set()
    for seed in seeds:
        if seed.login in logins:
            raise UserSeedError(f"DASHBOARD_USERS: логин {seed.login} указан более одного раза")
        logins.add(seed.login)
    if len({seed.company for seed in seeds}) != REQUIRED_COMPANY_COUNT:
        raise UserSeedError(
            f"DASHBOARD_USERS должна содержать ровно {REQUIRED_COMPANY_COUNT} различных компании"
        )


def _verify_seeds_match_database(connection: sqlite3.Connection, seeds: Sequence[UserSeed]) -> None:
    rows = connection.execute(SELECT_USERS_SQL).fetchall()
    company_by_stored_login = {str(row["login"]): str(row["company_name"]) for row in rows}
    company_by_seed_login = {seed.login: seed.company for seed in seeds}
    for login in sorted(company_by_seed_login.keys() - company_by_stored_login.keys()):
        raise UserSeedError(f"Логин {login} из DASHBOARD_USERS отсутствует в базе данных")
    for login in sorted(company_by_stored_login.keys() - company_by_seed_login.keys()):
        raise UserSeedError(f"Логин {login} из базы данных отсутствует в DASHBOARD_USERS")
    for seed in seeds:
        if company_by_stored_login[seed.login] != seed.company:
            raise UserSeedError(
                f"Логин {seed.login}: компания в DASHBOARD_USERS не совпадает с базой данных"
            )


def _find_or_create_company_id(connection: sqlite3.Connection, name: str) -> int:
    row = connection.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()
    if row is not None:
        return int(row["id"])
    cursor = connection.execute("INSERT INTO companies (name) VALUES (?)", (name,))
    if cursor.lastrowid is None:
        raise UserSeedError(f"Не удалось создать компанию {name}")
    return cursor.lastrowid


def _insert_seeds(connection: sqlite3.Connection, seeds: Sequence[UserSeed]) -> None:
    company_ids: dict[str, int] = {}
    for seed in seeds:
        if seed.company not in company_ids:
            company_ids[seed.company] = _find_or_create_company_id(connection, seed.company)
    for seed in seeds:
        connection.execute(
            "INSERT INTO users (login, password_hash, company_id) VALUES (?, ?, ?)",
            (seed.login, hash_password(seed.password), company_ids[seed.company]),
        )


def seed_users(connection: sqlite3.Connection, seeds: Sequence[UserSeed]) -> None:
    """Create the companies and users from the seeds or verify them against the database."""
    _validate_seeds(seeds)
    if not connection.in_transaction:
        connection.execute("BEGIN IMMEDIATE")
    try:
        user_count = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
        if user_count == 0:
            _insert_seeds(connection, seeds)
        else:
            _verify_seeds_match_database(connection, seeds)
    except BaseException:
        connection.rollback()
        raise
    connection.commit()


def _to_user(row: sqlite3.Row) -> User:
    return User(
        id=int(row["id"]),
        login=str(row["login"]),
        company_id=int(row["company_id"]),
        company_name=str(row["company_name"]),
    )


def authenticate(connection: sqlite3.Connection, login: str, password: str) -> User | None:
    """Return the user for a correct login and password, otherwise None."""
    row = connection.execute(
        "SELECT users.id, users.login, users.company_id, companies.name AS company_name, "
        "users.password_hash "
        "FROM users JOIN companies ON companies.id = users.company_id "
        "WHERE users.login = ?",
        (login,),
    ).fetchone()
    if row is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None
    if not verify_password(password, str(row["password_hash"])):
        return None
    return _to_user(row)


def get_user(connection: sqlite3.Connection, user_id: int) -> User | None:
    """Return the user with the given id or None."""
    row = connection.execute(f"{SELECT_USERS_SQL} WHERE users.id = ?", (user_id,)).fetchone()
    return None if row is None else _to_user(row)


def list_users(connection: sqlite3.Connection) -> list[User]:
    """Return all users ordered by id."""
    rows = connection.execute(f"{SELECT_USERS_SQL} ORDER BY users.id").fetchall()
    return [_to_user(row) for row in rows]


def list_companies(connection: sqlite3.Connection) -> list[Company]:
    """Return all companies ordered by id."""
    rows = connection.execute("SELECT id, name FROM companies ORDER BY id").fetchall()
    return [Company(id=int(row["id"]), name=str(row["name"])) for row in rows]
