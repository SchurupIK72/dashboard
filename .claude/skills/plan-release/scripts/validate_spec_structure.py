
"""Validate the basic Markdown structure expected from plan-release."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REQUIRED_SECTIONS = [
    "Workflow выполнения",
    "Видение",
    "Архитектурные решения",
    "Этапы реализации",
]

WORKFLOW_SKILLS = [
    "implement-spec-stage",
    "write-tests",
    "integrate-release",
    "deploy-release",
]

REQUIREMENT_ROW = re.compile(r"^\|\s*(R\d+)\s*\|", re.MULTILINE)

STAGE_HEADING = re.compile(r"^###\s+(.+?)(?:\s+(⬜|🔄|✅))?\s*$", re.MULTILINE)

CHECKLIST_ITEM = re.compile(
    r"^\s*-\s\[[ x]\]\s*(C\d+\.\d+)\s+\[([R\d,\s]+)\]\s+\S", re.MULTILINE
)


def has_section(text: str, section: str) -> bool:
    return re.search(rf"^##\s+{re.escape(section)}\s*$", text, re.MULTILINE) is not None


def extract_section(text: str, title: str) -> str:
    """Return the body of a `##` section up to the next `##` heading."""
    heading = re.search(rf"^##\s+{re.escape(title)}\s*$", text, re.MULTILINE)
    if heading is None:
        return ""
    tail = text[heading.end() :]
    next_heading = re.search(r"^##\s+", tail, re.MULTILINE)
    return tail[: next_heading.start()] if next_heading else tail


def validate_checklist(requirements_section: str, stages_section: str) -> list[str]:
    """Validate C-item IDs and requirement links inside the implementation stages."""
    errors: list[str] = []
    items = CHECKLIST_ITEM.findall(stages_section)


    if not items:
        return errors

    known_requirements = {
        int(row.group(1)[1:]) for row in REQUIREMENT_ROW.finditer(requirements_section)
    }

    seen_items: set[str] = set()
    for item_id, references in items:
        if item_id in seen_items:
            errors.append(f"Duplicate checklist item ID: {item_id}.")
        seen_items.add(item_id)
        for reference in re.findall(r"R\d+", references):
            if int(reference[1:]) not in known_requirements:
                errors.append(f"Unknown requirement reference {reference} in item {item_id}.")

    headings = list(STAGE_HEADING.finditer(stages_section))
    for index, stage in enumerate(headings):
        if index + 1 < len(headings):
            body_end = headings[index + 1].start()
        else:
            body_end = len(stages_section)
        body = stages_section[stage.end() : body_end]
        if not CHECKLIST_ITEM.search(body):
            errors.append(
                f"Stage has no new-format checklist item: {stage.group(0).strip()}."
            )

    return errors


def validate(text: str) -> list[str]:
    errors: list[str] = []

    if not re.search(r"^# .+Specification \(v[^)]+\)", text, re.MULTILINE):
        errors.append("Missing H1 title with `Specification (v...)`.")

    for label in ["Дата создания", "Ветка", "Статус", "Standard"]:
        if f"**{label}:**" not in text:
            errors.append(f"Missing metadata field: {label}.")

    for section in REQUIRED_SECTIONS:
        if not has_section(text, section):
            errors.append(f"Missing required section: {section}.")

    if has_section(text, "Workflow выполнения"):
        for skill in WORKFLOW_SKILLS:
            if f"`{skill}`" not in text:
                errors.append(f"Workflow table missing skill: {skill}.")

    if not re.search(r"^###\s+(?:\S+\s+)?Этап\s+\d+:", text, re.MULTILINE):
        errors.append("Missing implementation stage heading: `### [⬜] Этап N:`.")

    for marker in ["**Файлы:**", "**Что делаем:**", "**Определение готовности:**"]:
        if marker not in text:
            errors.append(f"Missing stage marker: {marker}.")

    if "Score:" not in text:
        errors.append("Missing standard score in metadata.")

    if re.search(r"\b(и т\.д\.|etc\.)\b", text, re.IGNORECASE) or re.search(
        r"\bпрочее\b", text
    ):



        errors.append("Vague placeholder detected: avoid `и т.д.`, `etc.`, or `прочее`.")

    errors.extend(
        validate_checklist(
            extract_section(text, "Требования"),
            extract_section(text, "Этапы реализации"),
        )
    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a dot_ai spec Markdown file.")
    parser.add_argument("spec_path", type=Path)
    args = parser.parse_args()

    if not args.spec_path.exists():
        print(f"ERROR: file not found: {args.spec_path}", file=sys.stderr)
        return 2

    text = args.spec_path.read_text(encoding="utf-8")
    errors = validate(text)

    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
