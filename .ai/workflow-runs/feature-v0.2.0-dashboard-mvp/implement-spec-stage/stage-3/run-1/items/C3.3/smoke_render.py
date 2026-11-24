from types import SimpleNamespace as NS
from dashboard.main import templates

env = templates.env
items = [NS(id=1, title="<script>alert(1)</script>", is_done=False), NS(id=2, title="Молоко", is_done=True)]
ctx = {"checklist_title": "Покупки", "checklist_path": "/shopping", "items": items, "error": None}
frag = env.get_template("_checklist_items.html").render(**ctx)
full = env.get_template("checklist.html").render(**ctx)
empty = env.get_template("_checklist_items.html").render(**{**ctx, "items": []})
err = env.get_template("_checklist_items.html").render(**{**ctx, "error": "Позиция <b>"})
checks = {
 "escaped": "&lt;script&gt;alert(1)&lt;/script&gt;" in frag and "<script>alert(1)" not in frag,
 "s_done_once": frag.count('<s class="is-done">') == 1 and '<s class="is-done">Молоко</s>' in frag,
 "confirm": 'hx-confirm="Удалить позицию?"' in frag,
 "frag_no_html": not any(t in frag.lower() for t in ("<html", "<!doctype", "<body")),
 "empty": "Список пуст" in empty and "<ul" not in empty and "Список пуст" not in frag,
 "full_has_html": "<html" in full.lower() and "checklist-items" in full and "<h1>Покупки</h1>" in full,
 "no_http": "http://" not in frag and "https://" not in frag,
 "no_script_tag": "<script" not in frag,
 "error_shown": 'class="error"' in err and "&lt;b&gt;" in err and 'class="error"' not in frag,
 "order": frag.index("alert(1)") < frag.index("Молоко"),
}
for k, v in checks.items():
    print(k, v)
print("ALL", all(checks.values()))
