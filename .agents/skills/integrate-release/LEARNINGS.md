# Learnings — integrate-release

Уроков пока нет. Новый урок — коротким напоминанием без таблиц и обязательных секций; если урок вскрывает failure mode, сначала фиксируется eval, затем правится поведение.

- Иллюстративные примеры D-ссылок в шаблонах и документации пишутся нечисловым плейсхолдером (`D##`), а не конкретным номером: буквальный номер в release diff становится мёртвой ссылкой для `scripts/find_trace_refs.py`.
- `find_trace_refs.py` on the dot_ai release diff needs `--exclude tests/`: the checker's own self-test fixtures carry deliberately dead D-IDs (48 false positives at the v0.14.0 merge).
- Spec archiving moves a file that tests may pin by active path: tests reading `.ai/specs/{slug}.md` need an archive fallback (three matrix-contract failures at the v0.14.0 merge).
- Runtime dirs `.ai/ownership/` and `.ai/workflow-runs/` must be gitignored, otherwise every workflow-state gate reports DIRTY_TREE on a clean checkout (fixed at the v0.14.0 merge).
