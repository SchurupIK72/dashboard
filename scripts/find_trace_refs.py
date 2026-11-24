"""Check durable decision references (D##) against the project decision registry.

Scans the release diff versus a base ref (default main; working tree and
untracked files included, so uncommitted release artifacts are covered) or
explicit files, extracts D## decision references from added lines and fails
with file:line for every reference missing from the registry (default
.ai/DECISIONS.md). Local spec numbers (R##, C##.##, A##, X##) are not global
decisions and never match. Installed projects keep their accepted registry and
root via --registry/--root; no portal registry is imposed.

A registered decision is a registry line whose first token is the `D##`
identifier: a bullet item, a heading, a table row or a plain `D##: text` row.

Exit codes:
    0 - every D## reference found is registered (or no references at all)
    1 - at least one dead D## reference
    2 - usage or execution error (git failure, missing registry, unreadable file)
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REF_RE = re.compile(r"\bD(\d+)\b")
REGISTRY_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s+|#{1,6}\s+|\|\s*)?(D\d+)\b")
DIFF_HEADER_PREFIXES = ("diff --git", "index ", "old mode", "new mode",
                        "deleted file mode", "new file mode",
                        "similarity index", "dissimilarity index", "rename ")
DEFAULT_BASE = "main"
DEFAULT_REGISTRY = ".ai/DECISIONS.md"
DEFAULT_EXCLUDES = (".ai/specs/", ".ai/workflow-runs/", ".ai/reports/")


class ExecutionError(Exception):
    """Real execution error (git, filesystem) that must fail the run."""


def registered_ids(registry_text: str) -> set[str]:
    ids = set()
    for line in registry_text.splitlines():
        match = REGISTRY_ITEM_RE.match(line)
        if match:
            ids.add(match.group(1))
    return ids


def git_output(root: Path, args_list: list[str]) -> str:
    result = subprocess.run(["git", "-C", str(root), *args_list],
                            capture_output=True, timeout=60)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ExecutionError(f"git {' '.join(args_list)} failed: {detail}")
    return result.stdout.decode("utf-8", errors="replace")


def strip_diff_path(raw: str) -> str:
    value = raw
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    return value


def added_lines_from_diff(diff_text: str):
    lines = diff_text.splitlines()
    index = 0
    current_path = None
    while index < len(lines):
        raw = lines[index]
        index += 1
        if raw.startswith("+++ b/"):
            current_path = strip_diff_path(raw[6:])
            continue
        if raw.startswith("--- ") or raw.startswith(DIFF_HEADER_PREFIXES):
            continue
        if not raw.startswith("@@"):
            continue
        old_part = re.search(r"-(\d+)(?:,(\d+))?", raw)
        new_part = re.search(r"\+(\d+)(?:,(\d+))?", raw)
        if not old_part or not new_part:
            continue
        old_left = int(old_part.group(2)) if old_part.group(2) is not None else 1
        new_left = int(new_part.group(2)) if new_part.group(2) is not None else 1
        line_no = int(new_part.group(1))
        while index < len(lines) and (old_left > 0 or new_left > 0):
            body = lines[index]
            index += 1
            if body.startswith("+"):
                if current_path and current_path != "/dev/null":
                    yield current_path, line_no, body[1:]
                line_no += 1
                new_left -= 1
            elif body.startswith("-"):
                old_left -= 1
            elif body.startswith("\\"):
                continue
            else:
                line_no += 1
                new_left -= 1
                old_left -= 1


def untracked_files(root: Path) -> list[str]:
    raw = git_output(root, ["ls-files", "--others", "--exclude-standard", "-z"])
    return [name for name in raw.split("\0") if name]


def is_excluded(rel_path: str, registry_rel: str, excludes: tuple[str, ...]) -> bool:
    posix = rel_path.replace("\\", "/")
    if posix == registry_rel:
        return True
    return any(posix.startswith(prefix) for prefix in excludes)


def relative_to_root(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def refs_in_line(path: str, line_no: int, content: str) -> list[dict]:
    return [{"file": path, "line": line_no, "id": f"D{match.group(1)}"}
            for match in REF_RE.finditer(content)]


def collect_file_refs(root: Path, path: Path, registry_rel: str,
                      excludes: tuple[str, ...]) -> list[dict]:
    if not path.is_file():
        raise ExecutionError(f"file not found: {path}")
    rel = relative_to_root(root, path)
    if is_excluded(rel, registry_rel, excludes):
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    refs = []
    for number, line in enumerate(text.splitlines(), start=1):
        refs.extend(refs_in_line(rel, number, line))
    return refs


def collect_diff_refs(root: Path, base: str, registry_rel: str,
                      excludes: tuple[str, ...]) -> list[dict]:
    diff_text = git_output(root, ["diff", "--no-color", "--unified=0",
                                  "--no-renames", base, "--"])
    refs = []
    for path, line_no, content in added_lines_from_diff(diff_text):
        if is_excluded(path, registry_rel, excludes):
            continue
        refs.extend(refs_in_line(path, line_no, content))
    for name in untracked_files(root):
        refs.extend(collect_file_refs(root, root / name, registry_rel, excludes))
    return refs


def report(refs: list[dict], registered: set[str], registry_label: str,
           as_json: bool) -> int:
    for ref in refs:
        ref["registered"] = ref["id"] in registered
    dead = [ref for ref in refs if not ref["registered"]]
    if as_json:
        payload = {
            "registry": registry_label,
            "registered_ids": sorted(registered, key=lambda item: int(item[1:])),
            "refs": refs,
            "dead_count": len(dead),
            "status": "FAIL" if dead else "PASS",
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for ref in dead:
            print(f"{ref['file']}:{ref['line']}: "
                  f"{ref['id']} not registered in {registry_label}")
        if dead:
            ids = ", ".join(sorted({ref["id"] for ref in dead},
                                   key=lambda item: int(item[1:])))
            print(f"FAIL: {len(dead)} dead decision reference(s): {ids}")
        elif refs:
            print(f"PASS: {len(refs)} decision reference(s), "
                  f"all registered in {registry_label}")
        else:
            print(f"PASS: no decision references found "
                  f"(registry: {registry_label})")
    return 1 if dead else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path,
                        help="explicit files to scan; omit to scan the release diff")
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--registry", default=DEFAULT_REGISTRY,
                        help="decision registry path (absolute or root-relative)")
    parser.add_argument("--base", default=DEFAULT_BASE,
                        help="base ref for the release diff")
    parser.add_argument("--exclude", action="append", default=[], metavar="PREFIX",
                        help="extra excluded path prefix (repeatable)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()
    root = args.root.resolve()
    registry_path = Path(args.registry)
    registry_abs = registry_path if registry_path.is_absolute() else root / registry_path
    if not registry_abs.is_file():
        print(f"FAIL: decision registry not found: {registry_abs}", file=sys.stderr)
        return 2
    try:
        registry_text = registry_abs.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"FAIL: cannot read decision registry {registry_abs}: {exc}",
              file=sys.stderr)
        return 2
    registered = registered_ids(registry_text)
    registry_rel = relative_to_root(root, registry_abs)
    excludes = DEFAULT_EXCLUDES + tuple(
        item.replace("\\", "/").rstrip("/") + "/" for item in args.exclude)
    try:
        if args.files:
            refs = []
            for item in args.files:
                full = item if item.is_absolute() else root / item
                refs.extend(collect_file_refs(root, full, registry_rel, excludes))
        else:
            refs = collect_diff_refs(root, args.base, registry_rel, excludes)
    except ExecutionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    return report(refs, registered, registry_rel, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
