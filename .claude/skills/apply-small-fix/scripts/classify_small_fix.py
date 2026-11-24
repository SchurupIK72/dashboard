
"""Classify whether a task looks suitable for apply-small-fix.

Escalation to plan-release happens by task content only. The changed-file
count above the warning threshold keeps ROUTE=apply-small-fix and demands an
explanation. Both values come from the effective workflow configuration:
policies.small_fix.file_warning_threshold and require_plan_mode.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ESCALATION_PATTERNS = {
    "migration": re.compile(
        r"\b(migration|migrations|migrate|schema|database)\b|миграц|схем[аыу]?\s+(данных|базы)",
        re.I,
    ),
    "public_contract": re.compile(
        r"\b(api|public contract|protocol|endpoint|breaking)\b|публичн",
        re.I,
    ),
    "architecture": re.compile(
        r"\b(architecture|redesign|new module)\b|архитектур",
        re.I,
    ),
    "feature": re.compile(
        r"\b(new feature|add feature|support new|implement new)\b|нов(ая|ую|ой)\s+(фича|функциональность|возможность)",
        re.I,
    ),
    "multi_stage": re.compile(
        r"\b(stage|phase|multi-step)\b|несколько этапов|многоэтап",
        re.I,
    ),
}

MIGRATION_FILE_PARTS = ("migration",)
MIGRATION_FILE_SUFFIXES = (".sql",)

CONFIG_RELATIVE = Path(".ai") / "workflow.yaml"


def read_description(args: argparse.Namespace) -> str:
    if args.description:
        return args.description
    if args.file:
        return args.file.read_text(encoding="utf-8")
    return sys.stdin.read()


def locate_config(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit if explicit.is_file() else None
    script = Path(__file__).resolve()
    for base in (Path.cwd().resolve(), *Path.cwd().resolve().parents, script, *script.parents):
        candidate = base / CONFIG_RELATIVE
        if candidate.is_file():
            return candidate
    return None


def load_policies(config_path: Path) -> dict:
    scripts_dir = config_path.resolve().parent.parent / "scripts"
    if not (scripts_dir / "workflow_config.py").is_file():
        raise ValueError(f"workflow_config not found next to config: {scripts_dir / 'workflow_config.py'}")
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from workflow_config import resolve

    resolved = resolve(str(config_path))
    return resolved["effective"]["policies"]["small_fix"]


def is_migration_file(files: list[str]) -> bool:
    for path in files:
        normalized = path.replace("\\", "/").lower()
        if any(part in normalized for part in MIGRATION_FILE_PARTS):
            return True
        if normalized.endswith(MIGRATION_FILE_SUFFIXES):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("description", nargs="?")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--changed-files", nargs="*", default=[])
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    config_path = locate_config(args.config)
    if config_path is None:
        print("FAIL")
        print(f"- workflow config not found: {CONFIG_RELATIVE.as_posix()} (policies.small_fix is required)")
        return 2
    try:
        policies = load_policies(config_path)
        threshold = int(policies["file_warning_threshold"])
        require_plan_mode = bool(policies["require_plan_mode"])
    except (ValueError, KeyError, OSError, ImportError) as error:
        print("FAIL")
        print(f"- workflow config error: {error}")
        return 2

    text = read_description(args)
    reasons: list[str] = []
    for name, pattern in ESCALATION_PATTERNS.items():
        if pattern.search(text):
            reasons.append(name)

    files = [path for path in args.changed_files if path]
    if any(path.replace("\\", "/").startswith(".ai/specs/") for path in files):
        reasons.append("spec_artifact")
    if is_migration_file(files):
        reasons.append("migration_file")

    if reasons:
        print("ROUTE=plan-release")
        print("REASONS=" + ",".join(sorted(set(reasons))))
        return 1

    print("ROUTE=apply-small-fix")
    print("REASONS=local,limited,checkable")
    print("PLAN_MODE=" + ("required" if require_plan_mode else "not_required"))
    if len(files) > threshold:
        print(
            f"WARNING=file_warning_threshold:{len(files)}>{threshold}:"
            "single coherent fix explanation required"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
