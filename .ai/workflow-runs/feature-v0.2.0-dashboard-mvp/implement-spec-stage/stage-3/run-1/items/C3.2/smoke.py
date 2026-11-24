import json
import re
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from dashboard.main import create_app
from dashboard.settings import load_settings

USERS = [
    {"login": "anna", "password": "pw-anna-7731", "company": "Alpha"},
    {"login": "boris", "password": "pw-boris-4482", "company": "Alpha"},
    {"login": "vera", "password": "pw-vera-9915", "company": "Beta"},
]
HX = {"HX-Request": "true"}
failures: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(("OK   " if condition else "FAIL ") + label, "" if condition else detail)
    if not condition:
        failures.append(label)


def item_ids(path: str, text: str) -> list[int]:
    return sorted(int(found) for found in re.findall(rf"{path}/(\d+)/toggle", text))


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "dashboard.db"
        settings = load_settings(
            environ={
                "SECRET_KEY": "k9Zq-guard-secret-0123456789-abcdefXYZ",
                "DASHBOARD_USERS": json.dumps(USERS),
                "DATABASE_URL": f"sqlite:///{database.as_posix()}",
            },
            env_file=None,
        )
        with TestClient(create_app(settings), follow_redirects=False) as client:
            anon = client.post("/shopping/add", data={"title": "x"})
            check("anon POST 303", anon.status_code == 303 and anon.headers["location"] == "/login")
            check("anon GET 303", client.get("/todos").status_code == 303)
            login = client.post("/login", data={"login": "anna", "password": "pw-anna-7731"})
            check("login 303", login.status_code == 303)
            for path in ("/shopping", "/todos"):
                page = client.get(path)
                check(f"GET {path} 200", page.status_code == 200 and "<html" in page.text)
                add = client.post(f"{path}/add", data={"title": "  Молоко  "})
                check(
                    f"{path} add plain 303",
                    add.status_code == 303 and add.headers["location"] == path,
                )
                page = client.get(path)
                check(f"{path} item shown", "Молоко" in page.text)
                first = item_ids(path, page.text)[0]
                add_hx = client.post(f"{path}/add", data={"title": "Хлеб"}, headers=HX)
                check(
                    f"{path} add htmx 200 fragment",
                    add_hx.status_code == 200
                    and "<html" not in add_hx.text
                    and "Хлеб" in add_hx.text,
                )
                second = item_ids(path, add_hx.text)[-1]
                toggle = client.post(f"{path}/{first}/toggle")
                check(f"{path} toggle plain 303", toggle.status_code == 303)
                toggle_hx = client.post(f"{path}/{first}/toggle", headers=HX)
                check(
                    f"{path} toggle htmx 200",
                    toggle_hx.status_code == 200 and "<html" not in toggle_hx.text,
                )
                rename = client.post(f"{path}/{first}/rename", data={"title": "Кефир"})
                check(f"{path} rename plain 303", rename.status_code == 303)
                rename_hx = client.post(
                    f"{path}/{first}/rename", data={"title": "Кефир2"}, headers=HX
                )
                check(
                    f"{path} rename htmx 200",
                    rename_hx.status_code == 200 and "Кефир2" in rename_hx.text,
                )
                bad = client.post(f"{path}/add", data={"title": "   "})
                check(
                    f"{path} invalid plain 422",
                    bad.status_code == 422 and "<html" in bad.text and "от 1 до 200" in bad.text,
                )
                bad_hx = client.post(f"{path}/add", data={"title": "x" * 201}, headers=HX)
                check(
                    f"{path} invalid htmx 200 error",
                    bad_hx.status_code == 200
                    and "от 1 до 200" in bad_hx.text
                    and "<html" not in bad_hx.text,
                )
                missing_field = client.post(f"{path}/add", data={})
                check(
                    f"{path} missing field 422 message",
                    missing_field.status_code == 422 and "от 1 до 200" in missing_field.text,
                )
                bad_rename = client.post(f"{path}/{first}/rename", data={"title": ""})
                check(f"{path} rename invalid 422", bad_rename.status_code == 422)
                nf = client.post(f"{path}/999/toggle")
                check(
                    f"{path} missing plain 404",
                    nf.status_code == 404 and "Позиция не найдена" in nf.text,
                )
                nf_hx = client.post(f"{path}/999/delete", headers=HX)
                check(
                    f"{path} missing htmx 200",
                    nf_hx.status_code == 200 and "Позиция не найдена" in nf_hx.text,
                )
                nf_rename = client.post(f"{path}/999/rename", data={"title": "a"})
                check(f"{path} missing rename 404", nf_rename.status_code == 404)
                check(
                    f"{path} non-int id 422",
                    client.post(f"{path}/abc/toggle").status_code == 422,
                )
                for suffix in (f"/{first}/toggle", f"/{first}/rename", f"/{first}/delete", "/add"):
                    got = client.get(f"{path}{suffix}")
                    check(f"GET {path}{suffix} 405", got.status_code == 405, got.status_code)
                delete = client.post(f"{path}/{first}/delete")
                check(f"{path} delete plain 303", delete.status_code == 303)
                delete_hx = client.post(f"{path}/{second}/delete", headers=HX)
                check(
                    f"{path} delete htmx 200 empty",
                    delete_hx.status_code == 200 and "Список пуст" in delete_hx.text,
                )
            client.post("/shopping/add", data={"title": "Только покупки"})
            check("kinds separate", "Только покупки" not in client.get("/todos").text)
            shop_id = item_ids("/shopping", client.get("/shopping").text)[0]
            other_kind = client.post(f"/todos/{shop_id}/toggle")
            check("cross-kind id 404", other_kind.status_code == 404, other_kind.status_code)
            client.cookies.clear()
            client.post("/login", data={"login": "vera", "password": "pw-vera-9915"})
            toggled = client.post(f"/shopping/{shop_id}/toggle")
            check("other user toggles any item 303", toggled.status_code == 303, toggled.status_code)
            check("toggled by other user shown done", "is-done" in client.get("/shopping").text)
    print("FAILURES:", failures)
    sys.exit(1 if failures else 0)


main()
