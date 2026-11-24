
"""Validate basic stage status consistency in a dot_ai implementation spec."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


STAGE_HEADING = re.compile(r"^###\s+(.+?)(?:\s+(⬜|🔄|✅))?\s*$", re.MULTILINE)
STATUS_MARKS = ("⬜", "🔄", "✅")
OPEN_CHECKLIST_ITEM = re.compile(r"^\s*-\s\[\s\]\s*C\d+\.\d+", re.MULTILINE)


def _stages_body(text: str) -> str:
    """Return the body of `## Этапы реализации` up to the next `##` heading.

    Specs may use `###` subsections elsewhere (requirement groups `### A.`,
    scope notes) — those are not stages and must not be scanned.
    """
    marker = "## Этапы реализации"
    start = text.find(marker)
    if start == -1:
        return ""
    rest = text[start + len(marker) :]
    next_section = rest.find("\n## ")
    return rest if next_section == -1 else rest[:next_section]


def validate(text: str) -> list[str]:
    errors: list[str] = []

    if "## Этапы реализации" not in text:
        errors.append("Missing `## Этапы реализации` section.")

    stages = list(STAGE_HEADING.finditer(_stages_body(text)))
    if not stages:
        errors.append("No implementation stages found (`### ...`).")
        return errors

    in_progress = 0
    complete = 0
    not_started = 0
    stages_body = _stages_body(text)

    for index, stage in enumerate(stages):
        line = stage.group(0)
        status = next((mark for mark in STATUS_MARKS if mark in line), None)
        if status is None:
            errors.append(f"Stage has no status mark: {line}")
            continue
        if status == "🔄":
            in_progress += 1
        elif status == "✅":
            complete += 1
            if index + 1 < len(stages):
                body_end = stages[index + 1].start()
            else:
                body_end = len(stages_body)
            body = stages_body[stage.end() : body_end]
            if OPEN_CHECKLIST_ITEM.search(body):
                errors.append(
                    f"Stage is `✅` but has open checklist items: {line.strip()}."
                )
        elif status == "⬜":
            not_started += 1

    if in_progress > 1:
        errors.append("More than one stage is marked in progress (`🔄`).")

    if complete == len(stages) and "write-tests" not in text:
        errors.append("All stages are complete but `write-tests` is not referenced.")

    if complete == 0 and not_started == len(stages):
        errors.append("No stage appears completed; do not commit an implementation stage yet.")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dot_ai spec stage completion.")
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
