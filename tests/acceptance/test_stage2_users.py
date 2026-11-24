import dataclasses
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from dashboard.database import connect, initialize_schema
from dashboard.passwords import DUMMY_PASSWORD_HASH, verify_password
from dashboard.settings import UserSeed
from dashboard.users import (
    Company,
    User,
    UserSeedError,
    authenticate,
    get_user,
    list_companies,
    list_users,
    seed_users,
)

SEEDS = (
    UserSeed(login="anna", password="pw-anna-first", company="Beta"),
    UserSeed(login="boris", password="pw-boris-second", company="Alpha"),
    UserSeed(login="clara", password="pw-clara-third", company="Beta"),
)


def _open_database(path: Path) -> sqlite3.Connection:
    connection = connect(path)
    initialize_schema(connection)
    return connection


def _stored_hashes(connection: sqlite3.Connection) -> dict[str, str]:
    rows = connection.execute("SELECT login, password_hash FROM users").fetchall()
    return {row["login"]: row["password_hash"] for row in rows}


def _user_ids(connection: sqlite3.Connection) -> dict[str, int]:
    rows = connection.execute("SELECT login, id FROM users").fetchall()
    return {row["login"]: row["id"] for row in rows}


def _count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


@pytest.fixture(scope="module")
def seeded_connection(tmp_path_factory: pytest.TempPathFactory) -> Iterator[sqlite3.Connection]:
    connection = _open_database(tmp_path_factory.mktemp("users") / "app.db")
    seed_users(connection, SEEDS)
    yield connection
    connection.close()


@pytest.fixture
def empty_connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = _open_database(tmp_path / "app.db")
    yield connection
    connection.close()


@pytest.mark.acceptance
def test_seed_creates_three_users_and_two_companies(seeded_connection: sqlite3.Connection) -> None:
    assert _count(seeded_connection, "users") == 3
    assert _count(seeded_connection, "companies") == 2


@pytest.mark.acceptance
def test_seed_assigns_company_ids_by_first_appearance(
    seeded_connection: sqlite3.Connection,
) -> None:
    assert list_companies(seeded_connection) == [
        Company(id=1, name="Beta"),
        Company(id=2, name="Alpha"),
    ]


@pytest.mark.acceptance
def test_seed_links_each_user_to_its_company(seeded_connection: sqlite3.Connection) -> None:
    pairs = [
        (user.login, user.company_id, user.company_name) for user in list_users(seeded_connection)
    ]
    assert sorted(pairs) == [
        ("anna", 1, "Beta"),
        ("boris", 2, "Alpha"),
        ("clara", 1, "Beta"),
    ]


@pytest.mark.acceptance
def test_seed_stores_scrypt_hashes_that_verify(seeded_connection: sqlite3.Connection) -> None:
    hashes = _stored_hashes(seeded_connection)
    assert set(hashes) == {"anna", "boris", "clara"}
    for seed in SEEDS:
        assert hashes[seed.login].startswith("scrypt$16384$8$1$")
        assert verify_password(seed.password, hashes[seed.login]) is True


@pytest.mark.acceptance
def test_seed_stores_no_plain_password_in_users_table(
    seeded_connection: sqlite3.Connection,
) -> None:
    rows = seeded_connection.execute("SELECT * FROM users").fetchall()
    cells = [str(cell) for row in rows for cell in tuple(row)]
    for seed in SEEDS:
        assert all(seed.password not in cell for cell in cells)


@pytest.mark.acceptance
def test_seed_again_with_identical_seeds_changes_nothing(
    seeded_connection: sqlite3.Connection,
) -> None:
    hashes_before = _stored_hashes(seeded_connection)
    ids_before = _user_ids(seeded_connection)
    seed_users(seeded_connection, SEEDS)
    assert _stored_hashes(seeded_connection) == hashes_before
    assert _user_ids(seeded_connection) == ids_before
    assert _count(seeded_connection, "companies") == 2


@pytest.mark.acceptance
def test_seed_again_with_new_password_keeps_stored_hash(
    seeded_connection: sqlite3.Connection,
) -> None:
    hashes_before = _stored_hashes(seeded_connection)
    changed = (
        UserSeed(login="anna", password="completely-new-secret", company="Beta"),
        SEEDS[1],
        SEEDS[2],
    )
    seed_users(seeded_connection, changed)
    assert _stored_hashes(seeded_connection) == hashes_before


@pytest.mark.acceptance
def test_seed_with_other_company_for_existing_login_raises_naming_login(
    seeded_connection: sqlite3.Connection,
) -> None:
    diverging = (
        SEEDS[0],
        UserSeed(login="boris", password="pw-boris-second", company="Beta"),
        UserSeed(login="clara", password="pw-clara-third", company="Alpha"),
    )
    with pytest.raises(UserSeedError) as caught:
        seed_users(seeded_connection, diverging)
    assert "boris" in str(caught.value)


@pytest.mark.acceptance
def test_seed_with_single_changed_company_names_that_login(
    seeded_connection: sqlite3.Connection,
) -> None:
    diverging = (
        SEEDS[0],
        SEEDS[1],
        UserSeed(login="clara", password="pw-clara-third", company="Alpha"),
    )
    with pytest.raises(UserSeedError) as caught:
        seed_users(seeded_connection, diverging)
    assert "clara" in str(caught.value)


@pytest.mark.acceptance
def test_seed_with_replaced_login_raises_naming_diverging_login(
    seeded_connection: sqlite3.Connection,
) -> None:
    replaced = (SEEDS[0], SEEDS[1], UserSeed(login="dora", password="pw-dora", company="Beta"))
    with pytest.raises(UserSeedError) as caught:
        seed_users(seeded_connection, replaced)
    message = str(caught.value)
    assert "dora" in message or "clara" in message


@pytest.mark.acceptance
def test_seed_divergence_message_never_contains_passwords_or_hashes(
    seeded_connection: sqlite3.Connection,
) -> None:
    hashes = _stored_hashes(seeded_connection)
    replaced = (
        UserSeed(login="anna", password="pw-anna-first", company="Alpha"),
        UserSeed(login="boris", password="pw-boris-second", company="Alpha"),
        UserSeed(login="dora", password="pw-dora-fourth", company="Beta"),
    )
    with pytest.raises(UserSeedError) as caught:
        seed_users(seeded_connection, replaced)
    message = str(caught.value)
    for secret in ("pw-anna-first", "pw-boris-second", "pw-dora-fourth", *hashes.values()):
        assert secret not in message


@pytest.mark.acceptance
def test_seed_divergence_leaves_database_unchanged(seeded_connection: sqlite3.Connection) -> None:
    hashes_before = _stored_hashes(seeded_connection)
    replaced = (SEEDS[0], SEEDS[1], UserSeed(login="dora", password="pw-dora", company="Beta"))
    with pytest.raises(UserSeedError):
        seed_users(seeded_connection, replaced)
    assert _stored_hashes(seeded_connection) == hashes_before
    assert _count(seeded_connection, "companies") == 2


def _assert_tables_empty(connection: sqlite3.Connection) -> None:
    assert _count(connection, "users") == 0
    assert _count(connection, "companies") == 0


@pytest.mark.acceptance
def test_seed_four_users_raises_and_leaves_tables_empty(
    empty_connection: sqlite3.Connection,
) -> None:
    seeds = (
        UserSeed(login="a", password="p1", company="X"),
        UserSeed(login="b", password="p2", company="Y"),
        UserSeed(login="c", password="p3", company="X"),
        UserSeed(login="d", password="p4", company="Y"),
    )
    with pytest.raises(UserSeedError):
        seed_users(empty_connection, seeds)
    _assert_tables_empty(empty_connection)


@pytest.mark.acceptance
def test_seed_two_users_raises_and_leaves_tables_empty(
    empty_connection: sqlite3.Connection,
) -> None:
    seeds = (
        UserSeed(login="a", password="p1", company="X"),
        UserSeed(login="b", password="p2", company="Y"),
    )
    with pytest.raises(UserSeedError):
        seed_users(empty_connection, seeds)
    _assert_tables_empty(empty_connection)


@pytest.mark.acceptance
def test_seed_three_distinct_companies_raises_and_leaves_tables_empty(
    empty_connection: sqlite3.Connection,
) -> None:
    seeds = (
        UserSeed(login="a", password="p1", company="X"),
        UserSeed(login="b", password="p2", company="Y"),
        UserSeed(login="c", password="p3", company="Z"),
    )
    with pytest.raises(UserSeedError):
        seed_users(empty_connection, seeds)
    _assert_tables_empty(empty_connection)


@pytest.mark.acceptance
def test_seed_single_company_raises_and_leaves_tables_empty(
    empty_connection: sqlite3.Connection,
) -> None:
    seeds = (
        UserSeed(login="a", password="p1", company="X"),
        UserSeed(login="b", password="p2", company="X"),
        UserSeed(login="c", password="p3", company="X"),
    )
    with pytest.raises(UserSeedError):
        seed_users(empty_connection, seeds)
    _assert_tables_empty(empty_connection)


@pytest.mark.acceptance
def test_seed_duplicate_logins_raises_naming_login_and_leaves_tables_empty(
    empty_connection: sqlite3.Connection,
) -> None:
    seeds = (
        UserSeed(login="dupelogin", password="p1", company="X"),
        UserSeed(login="dupelogin", password="p2", company="Y"),
        UserSeed(login="c", password="p3", company="Y"),
    )
    with pytest.raises(UserSeedError) as caught:
        seed_users(empty_connection, seeds)
    assert "dupelogin" in str(caught.value)
    _assert_tables_empty(empty_connection)


@pytest.mark.acceptance
def test_authenticate_with_right_password_returns_user(
    seeded_connection: sqlite3.Connection,
) -> None:
    user = authenticate(seeded_connection, "boris", "pw-boris-second")
    assert user == User(
        id=_user_ids(seeded_connection)["boris"],
        login="boris",
        company_id=2,
        company_name="Alpha",
    )


@pytest.mark.acceptance
def test_authenticate_with_wrong_password_returns_none(
    seeded_connection: sqlite3.Connection,
) -> None:
    assert authenticate(seeded_connection, "boris", "pw-boris-wrong") is None


@pytest.mark.acceptance
def test_authenticate_with_unknown_login_returns_none(
    seeded_connection: sqlite3.Connection,
) -> None:
    assert authenticate(seeded_connection, "nobody", "pw-boris-second") is None


@pytest.mark.acceptance
def test_authenticate_unknown_login_still_verifies_against_dummy_hash(
    seeded_connection: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, str]] = []

    def recording_verify(password: str, stored_hash: str) -> bool:
        calls.append((password, stored_hash))
        return verify_password(password, stored_hash)

    monkeypatch.setattr("dashboard.users.verify_password", recording_verify)
    assert authenticate(seeded_connection, "nobody", "guess") is None
    assert calls == [("guess", DUMMY_PASSWORD_HASH)]


@pytest.mark.acceptance
def test_authenticate_known_login_verifies_against_stored_hash(
    seeded_connection: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, str]] = []

    def recording_verify(password: str, stored_hash: str) -> bool:
        calls.append((password, stored_hash))
        return verify_password(password, stored_hash)

    monkeypatch.setattr("dashboard.users.verify_password", recording_verify)
    assert authenticate(seeded_connection, "anna", "guess") is None
    assert calls == [("guess", _stored_hashes(seeded_connection)["anna"])]


@pytest.mark.acceptance
def test_get_user_returns_user_for_existing_id(seeded_connection: sqlite3.Connection) -> None:
    anna_id = _user_ids(seeded_connection)["anna"]
    assert get_user(seeded_connection, anna_id) == User(
        id=anna_id, login="anna", company_id=1, company_name="Beta"
    )


@pytest.mark.acceptance
def test_get_user_returns_none_for_unknown_id(seeded_connection: sqlite3.Connection) -> None:
    assert get_user(seeded_connection, 9999) is None


@pytest.mark.acceptance
def test_list_users_is_ordered_by_id(seeded_connection: sqlite3.Connection) -> None:
    ids = [user.id for user in list_users(seeded_connection)]
    assert ids == sorted(ids)
    assert [user.login for user in list_users(seeded_connection)] == ["anna", "boris", "clara"]


@pytest.mark.acceptance
def test_list_companies_is_ordered_by_id(seeded_connection: sqlite3.Connection) -> None:
    companies = list_companies(seeded_connection)
    assert [company.id for company in companies] == [1, 2]
    assert [company.name for company in companies] == ["Beta", "Alpha"]


def _assign(target: object, attribute: str, value: object) -> None:
    setattr(target, attribute, value)


@pytest.mark.acceptance
def test_user_is_immutable() -> None:
    user = User(id=1, login="anna", company_id=1, company_name="Beta")
    with pytest.raises(dataclasses.FrozenInstanceError):
        _assign(user, "login", "other")
    assert user.login == "anna"


@pytest.mark.acceptance
def test_company_is_immutable() -> None:
    company = Company(id=1, name="Beta")
    with pytest.raises(dataclasses.FrozenInstanceError):
        _assign(company, "name", "other")
    assert company.name == "Beta"


@pytest.mark.acceptance
def test_users_table_rejects_unknown_company_id(empty_connection: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        empty_connection.execute(
            "INSERT INTO users (login, password_hash, company_id) VALUES (?, ?, ?)",
            ("ghost", "scrypt$x", 999),
        )
