
"""Validate changed-file scope for an apply-small-fix branch.

Migration/schema-like and spec files fail. The changed-file count above the
warning threshold (policies.small_fix.file_warning_threshold from the
effective workflow configuration, default flag --max-files overrides it) is a
warning that requires an explanation of the task coherence, not a failure.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


FORBIDDEN_PARTS = ("migrations", "migration")
FORBIDDEN_SUFFIXES = (".sql",)

CONFIG_RELATIVE = Path(".ai") / "workflow.yaml"


def git_lines(args: list[str], cwd: Path) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def changed_files(base: str, cwd: Path) -> list[str]:
    files = git_lines(["diff", "--name-only", f"{base}...HEAD"], cwd)
    if not files:
        files = git_lines(["diff", "--name-only", base], cwd)
    if not files:
        files = git_lines(["diff", "--name-only"], cwd)
    return files


def locate_config(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit if explicit.is_file() else None
    script = Path(__file__).resolve()
    for base in (Path.cwd().resolve(), *Path.cwd().resolve().parents, script, *script.parents):
        candidate = base / CONFIG_RELATIVE
        if candidate.is_file():
            return candidate
    return None


def load_threshold(explicit: Path | None) -> int:
    config_path = locate_config(explicit)
    if config_path is None:
        raise ValueError(f"workflow config not found: {CONFIG_RELATIVE.as_posix()}")
    scripts_dir = config_path.resolve().parent.parent / "scripts"
    if not (scripts_dir / "workflow_config.py").is_file():
        raise ValueError(f"workflow_config not found next to config: {scripts_dir / 'workflow_config.py'}")
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from workflow_config import resolve

    resolved = resolve(str(config_path))
    return int(resolved["effective"]["policies"]["small_fix"]["file_warning_threshold"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--base", default="main")
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument("--explanation", default=None, help="Why the over-threshold change is one coherent small fix.")
    parser.add_argument("--allow-mechanical-overage", action="store_true")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    try:
        threshold = args.max_files if args.max_files is not None else load_threshold(args.config)
    except (ValueError, KeyError, OSError, ImportError) as error:
        print("FAIL")
        print(f"- workflow config error: {error}")
        return 2

    cwd = args.cwd.resolve()
    files = changed_files(args.base, cwd)
    errors: list[str] = []

    spec_files = [path for path in files if path.replace("\\", "/").startswith(".ai/specs/")]
    if spec_files:
        errors.append("apply-small-fix must not create or edit spec files: " + ", ".join(spec_files))

    forbidden = [
        path
        for path in files
        if any(part in path.lower() for part in FORBIDDEN_PARTS)
        or path.lower().endswith(FORBIDDEN_SUFFIXES)
    ]
    if forbidden:
        errors.append("Migration/schema-like files require plan-release: " + ", ".join(forbidden))

    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PASS")
    print(f"changed_files={len(files)}")
    for path in files:
        print(f"- {path}")
    if len(files) > threshold:
        print(f"WARNING=file_warning_threshold:{len(files)}>{threshold}")
        if args.allow_mechanical_overage:
            print("WARNING_NATURE=mechanical_overage")
        elif args.explanation and args.explanation.strip():
            print(f"OVERAGE_EXPLANATION={args.explanation.strip()}")
        else:
            print("WARNING_ACTION=single coherent fix explanation required")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"FAIL\n- git command failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
