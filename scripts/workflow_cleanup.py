"""Safe file-only cleanup of identified workflow-run resources.

Deterministic CLI over the run-artifacts tree (.ai/workflow-runs): a dry-run
plan by default, execution only with --apply. Explicit targets are the current
run's own directories (--branch-slug with --run-id); --orphans additionally
enumerates leftover run directories whose branch and spec are absent and which
hold no active ownership/resume claim, counting as candidates only with a
terminal state file or when empty. Before any deletion, evidence referenced by
the final manifests and reports passed via --reference is relocated to the
durable .ai/reports/evidence tree and the references are rewritten in place,
so surviving documents keep resolving; a relocation or rewrite that fails
keeps every affected run directory undeleted so a retry can complete it.
Failed runs (non-terminal state),
active siblings (active ownership claims), unreadable or ambiguous cases,
memory candidates, the backlog, durable reports, the ownership registry and
foreign runs are always preserved, every preservation with its reason. The
separate plan-release layout (.ai/workflow-runs/plan-release/{plan-id}/{run-id})
is recognized through the branch recorded in its state file, verified against
the actual local branch list before it may preserve anything, and worktrees are
independent because only the given repository's run tree is ever read or
written. Cleanup is file-only: no process is stopped or killed. Errors are
visible through a non-zero exit and never undo an already successful merge.
Exit codes: 0 plan or clean apply, 1 failed apply steps, 2 input,
configuration or environment error.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_RELATIVE = '.ai/workflow-runs'
OWNERSHIP_RELATIVE = '.ai/ownership/registry.json'
EVIDENCE_RELATIVE = '.ai/reports/evidence'
DEFAULT_CONFIG_RELATIVE = '.ai/workflow.yaml'
PLAN_RELEASE_SLUG = 'plan-release'
RUN_SKILL_SEGMENTS = ('implement-spec-stage', 'write-tests', 'plan-release')
ACCEPTED_ITEM_STATUS = 'accepted'
DONE_STAGE_STATUS = '✅'
NAME_PATTERN = re.compile(r'[A-Za-z0-9._-]+')
PROTECTED_HINTS = (
    'memory candidates: .ai/memory-candidates/',
    'backlog: .ai/specs/draft/',
    'durable reports: .ai/reports/',
    'ownership registry: .ai/ownership/',
    'foreign runs: other branch trees under .ai/workflow-runs/',
)
EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_ERROR = 2


class CleanupError(ValueError):
    """Raised for input, configuration or environment errors."""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _posix(path):
    return Path(path).as_posix()


def _reference_pattern(text):
    return re.compile(r'(?<![\w./-])' + re.escape(text) + r'(?![\w/-])(?!\.[A-Za-z0-9_])')


def _load_settings(config_path):
    settings = {
        'preserve_referenced_evidence': True,
        'config_path': _posix(config_path),
        'sha256': None,
        'note': 'configuration file absent: built-in defaults apply',
    }
    if not config_path.is_file():
        return settings
    try:
        import workflow_config
        resolved = workflow_config.resolve(str(config_path))
    except Exception as error:
        raise CleanupError(f'configuration error: {config_path}: {error}') from error
    cleanup = resolved['effective']['policies']['cleanup']
    settings.update({
        'preserve_referenced_evidence': bool(cleanup['preserve_referenced_evidence']),
        'sha256': resolved['snapshot']['yaml_sha256'],
        'note': None,
    })
    return settings


def _load_claims(repo):
    registry_path = repo / OWNERSHIP_RELATIVE
    if not registry_path.is_file():
        return []
    try:
        registry = json.loads(registry_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CleanupError(f'ownership registry unreadable: {registry_path}: {error}') from error
    if not isinstance(registry, dict):
        raise CleanupError(f'ownership registry invalid: {registry_path}: an object is required')
    return [
        claim
        for claim in registry.get('claims') or []
        if isinstance(claim, dict) and claim.get('status') == 'active'
    ]


def _local_branches(repo):
    try:
        result = subprocess.run(
            ['git', '-C', str(repo), 'for-each-ref', 'refs/heads', '--format=%(refname:short)'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=30,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _slug(branch):
    return str(branch).replace('/', '-')


def _run_entries(runs_root):
    entries = []
    if not runs_root.is_dir():
        return entries
    for slug_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        if slug_dir.name == PLAN_RELEASE_SLUG:
            for plan_dir in sorted(path for path in slug_dir.iterdir() if path.is_dir()):
                for run_dir in sorted(path for path in plan_dir.iterdir() if path.is_dir()):
                    entries.append({'path': run_dir, 'slug': slug_dir.name, 'run_id': run_dir.name, 'layout': PLAN_RELEASE_SLUG})
        else:
            for skill_dir in sorted(path for path in slug_dir.iterdir() if path.is_dir()):
                if skill_dir.name not in RUN_SKILL_SEGMENTS:
                    continue
                for stage_dir in sorted(path for path in skill_dir.iterdir() if path.is_dir()):
                    for run_dir in sorted(path for path in stage_dir.iterdir() if path.is_dir()):
                        entries.append({'path': run_dir, 'slug': slug_dir.name, 'run_id': run_dir.name, 'layout': 'stage'})
    return entries


def _read_state(run_dir):
    state_path = run_dir / 'state.json'
    if not state_path.is_file():
        return None, 'absent'
    try:
        state = json.loads(state_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return None, f'unreadable: {error}'
    if not isinstance(state, dict):
        return None, 'not an object'
    return state, 'ok'


def _completion(run_dir):
    files = [path for path in run_dir.rglob('*') if path.is_file()]
    if not files:
        return True, 'empty run directory: nothing to resume or lose', None
    state, status = _read_state(run_dir)
    if state is None:
        if status == 'absent':
            return False, 'files present without state.json: doubt', None
        return False, f'state.json {status}: doubt', None
    items = state.get('items') if isinstance(state.get('items'), dict) else {}
    pending = sorted(
        key
        for key, value in items.items()
        if not isinstance(value, dict) or value.get('status') != ACCEPTED_ITEM_STATUS
    )
    if pending:
        return False, 'non-terminal items: ' + ', '.join(pending), state
    if state.get('stage_status') != DONE_STAGE_STATUS:
        return False, f"non-terminal stage status: {state.get('stage_status')!r}", state
    return True, 'terminal state: recorded items accepted and the stage is done', state


def _claim_for(claims, run_id, branches):
    for claim in claims:
        if claim.get('run_id') == run_id:
            return claim
        for branch in branches:
            if branch and claim.get('branch') == branch:
                return claim
    return None


def _spec_path(repo, slug):
    if not slug:
        return None
    for candidate in (repo / '.ai/specs' / f'{slug}.md', repo / '.ai/specs/archive' / f'{slug}.md'):
        if candidate.is_file():
            return _posix(candidate)
    return None


def _entry_branches(entry, local_branches, recorded=None):
    if entry['layout'] == PLAN_RELEASE_SLUG:
        if not recorded:
            return []
        return [recorded] if recorded in (local_branches or []) else []
    return [branch for branch in (local_branches or []) if _slug(branch) == entry['slug']]


def _decide_explicit(entry, claims):
    reasons = []
    claim = _claim_for(claims, entry['run_id'], [])
    if claim is not None:
        reasons.append(f"active ownership/resume claim: {claim.get('claim_id') or claim.get('run_id')}")
    terminal, reason, _ = _completion(entry['path'])
    if not terminal:
        reasons.append(reason)
    return ('preserve' if reasons else 'delete'), reasons


def _decide_orphan(entry, repo, local_branches, claims):
    reasons = []
    recorded = None
    if entry['layout'] == PLAN_RELEASE_SLUG:
        state, _ = _read_state(entry['path'])
        recorded = state.get('branch') if state else None
    if local_branches is None:
        reasons.append('branch presence unverifiable (git unavailable): doubt')
        branches = []
    else:
        branches = _entry_branches(entry, local_branches, recorded)
        if branches:
            reasons.append('branch exists: ' + ', '.join(sorted(branches)))
    slug = _slug(recorded) if recorded else (entry['slug'] if entry['layout'] != PLAN_RELEASE_SLUG else None)
    spec = _spec_path(repo, slug)
    if spec is not None:
        reasons.append('spec exists: ' + spec)
    claim_branches = list(branches)
    if recorded and recorded not in claim_branches:
        claim_branches.append(recorded)
    claim = _claim_for(claims, entry['run_id'], claim_branches)
    if claim is not None:
        reasons.append(f"active ownership/resume claim: {claim.get('claim_id') or claim.get('run_id')}")
    terminal, reason, _ = _completion(entry['path'])
    if not terminal:
        reasons.append(reason)
    return ('preserve' if reasons else 'delete'), reasons


def _explicit_targets(branch_slug, run_ids, runs_root):
    if not NAME_PATTERN.fullmatch(branch_slug):
        raise CleanupError(f'branch-slug must be a single path segment: {branch_slug!r}')
    for run_id in run_ids:
        if not NAME_PATTERN.fullmatch(run_id):
            raise CleanupError(f'run-id must be a single path segment: {run_id!r}')
    resolved_root = runs_root.resolve()
    targets = []
    for entry in _run_entries(runs_root):
        if entry['slug'] != branch_slug or entry['run_id'] not in run_ids:
            continue
        try:
            entry['path'].resolve().relative_to(resolved_root)
        except (OSError, ValueError) as error:
            raise CleanupError(f'target escapes the run tree: {entry["path"]}') from error
        targets.append(entry)
    missing = sorted(set(run_ids) - {target['run_id'] for target in targets})
    if missing:
        raise CleanupError(f'run-id not found under {RUNS_RELATIVE}/{branch_slug}/: ' + ', '.join(missing))
    return targets


def _collect_relocations(documents, delete_paths, repo, runs_root):
    relocations = []
    for document in documents:
        try:
            text = document.read_text(encoding='utf-8')
        except (OSError, UnicodeError) as error:
            raise CleanupError(f'reference document unreadable: {document}: {error}') from error
        for run_dir in delete_paths:
            run_root = run_dir.resolve()
            tree_relative = run_dir.relative_to(runs_root)
            for file_path in sorted(path for path in run_dir.rglob('*') if path.is_file()):
                try:
                    inside = file_path.resolve().relative_to(run_root)
                except (OSError, ValueError):
                    continue
                durable = f'{EVIDENCE_RELATIVE}/{_posix(tree_relative / inside)}'
                referenced = _posix(file_path.relative_to(repo))
                absolute = _posix(file_path.resolve())
                absolute_durable = _posix((repo / durable).resolve())
                for form, replacement in ((referenced, durable), (absolute, absolute_durable)):
                    if _reference_pattern(form).search(text):
                        relocations.append({
                            'document': _posix(document),
                            'referenced': referenced,
                            'durable': durable,
                            'matched_form': form,
                        })
                        break
    return relocations


def _apply_relocations(relocations, repo):
    failures = []
    completed = set()
    rewritten = set()
    by_document = {}
    for relocation in relocations:
        by_document.setdefault(relocation['document'], []).append(relocation)
    for relocation in relocations:
        destination = _posix(repo / relocation['durable'])
        if destination in completed:
            continue
        try:
            target = repo / relocation['durable']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo / relocation['referenced'], target)
            completed.add(destination)
        except OSError as error:
            failures.append({'step': 'relocate-evidence', 'path': relocation['durable'], 'error': str(error)})
    for document, entries in by_document.items():
        ready = [relocation for relocation in entries if _posix(repo / relocation['durable']) in completed]
        if not ready:
            continue
        try:
            path = repo / document
            text = path.read_text(encoding='utf-8')
            replacements = []
            for relocation in ready:
                replacements.append((relocation['referenced'], relocation['durable']))
                replacements.append((_posix((repo / relocation['referenced']).resolve()), _posix((repo / relocation['durable']).resolve())))
            for old, new in sorted(replacements, key=lambda pair: -len(pair[0])):
                text = _reference_pattern(old).sub(new, text)
            temporary = path.with_name(f'{path.name}.{os.getpid()}.tmp')
            temporary.write_text(text, encoding='utf-8')
            os.replace(temporary, path)
            rewritten.add(document)
        except (OSError, UnicodeError) as error:
            failures.append({'step': 'rewrite-references', 'path': document, 'error': str(error)})
    return failures, completed, rewritten


def _prune_empty(runs_root, removed):
    for path in removed:
        current = path.parent
        while current != runs_root and runs_root in current.parents:
            try:
                next(current.iterdir())
            except StopIteration:
                try:
                    current.rmdir()
                except OSError:
                    pass
            except OSError:
                pass
            current = current.parent


def _apply_deletions(targets, referenced, repo, runs_root, settings):
    failures = []
    deleted = []
    kept_in_place = []
    for target in targets:
        run_dir = target['path']
        kept = referenced.get(run_dir.resolve(), set())
        try:
            if settings['preserve_referenced_evidence'] or not kept:
                shutil.rmtree(run_dir)
                deleted.append(_posix(run_dir.relative_to(repo)))
                continue
            for file_path in (path for path in run_dir.rglob('*') if path.is_file()):
                if file_path.resolve() not in kept:
                    file_path.unlink()
            for directory in sorted((path for path in run_dir.rglob('*') if path.is_dir()), key=lambda path: len(path.parts), reverse=True):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            if any(run_dir.rglob('*')):
                kept_in_place.append(_posix(run_dir.relative_to(repo)))
            else:
                shutil.rmtree(run_dir)
                deleted.append(_posix(run_dir.relative_to(repo)))
        except OSError as error:
            failures.append({'step': 'delete-run-dir', 'path': _posix(run_dir), 'error': str(error)})
    _prune_empty(runs_root, [target['path'] for target in targets])
    return deleted, kept_in_place, failures


def evaluate(args):
    repo = Path(args.repo).resolve() if args.repo else REPO_ROOT
    runs_root = repo / RUNS_RELATIVE
    config = Path(args.config) if args.config is not None else repo / DEFAULT_CONFIG_RELATIVE
    settings = _load_settings(config)
    claims = _load_claims(repo)
    if not args.run_id and not args.orphans:
        raise CleanupError('nothing identified: pass --run-id for the current run and/or --orphans for leftover candidates')
    explicit = _explicit_targets(args.branch_slug, args.run_id, runs_root)
    targets = []
    for entry in explicit:
        decision, reasons = _decide_explicit(entry, claims)
        targets.append({**entry, 'kind': 'explicit', 'decision': decision, 'reasons': reasons})
    local_branches = None
    if args.orphans:
        local_branches = _local_branches(repo)
        explicit_paths = {entry['path'].resolve() for entry in explicit}
        for entry in _run_entries(runs_root):
            if entry['path'].resolve() in explicit_paths:
                continue
            decision, reasons = _decide_orphan(entry, repo, local_branches, claims)
            targets.append({**entry, 'kind': 'orphan', 'decision': decision, 'reasons': reasons})
    delete_entries = [target for target in targets if target['decision'] == 'delete']
    delete_paths = [target['path'] for target in delete_entries]
    documents = []
    for reference in args.reference or []:
        path = Path(reference)
        if not path.is_absolute():
            path = repo / path
        if not path.is_file():
            raise CleanupError(f'reference document not found: {reference}')
        resolved = path.resolve()
        for run_dir in delete_paths:
            try:
                resolved.relative_to(run_dir.resolve())
            except (OSError, ValueError):
                continue
            raise CleanupError(f'reference document lies inside a deletion target: {reference}')
        documents.append(path)
    relocations = _collect_relocations(documents, delete_paths, repo, runs_root)
    referenced = {}
    for relocation in relocations:
        for run_dir in delete_paths:
            try:
                (repo / relocation['referenced']).resolve().relative_to(run_dir.resolve())
            except (OSError, ValueError):
                continue
            referenced.setdefault(run_dir.resolve(), set()).add((repo / relocation['referenced']).resolve())
            break
    failures = []
    deleted = []
    kept_in_place = []
    notes = []
    if args.apply:
        completed = set()
        rewritten = set()
        if settings['preserve_referenced_evidence']:
            failures, completed, rewritten = _apply_relocations(relocations, repo)
        elif relocations:
            notes.append('referenced evidence kept in place: policies.cleanup.preserve_referenced_evidence=false')
        blocked = set()
        if settings['preserve_referenced_evidence']:
            for relocation in relocations:
                if _posix(repo / relocation['durable']) in completed and relocation['document'] in rewritten:
                    continue
                for run_dir in delete_paths:
                    try:
                        (repo / relocation['referenced']).resolve().relative_to(run_dir.resolve())
                    except (OSError, ValueError):
                        continue
                    blocked.add(run_dir.resolve())
                    break
        deletable = []
        for target in delete_entries:
            if target['path'].resolve() not in blocked:
                deletable.append(target)
                continue
            target['decision'] = 'preserve'
            target['reasons'].append('relocation of referenced evidence failed: run directory kept undeleted for a retry')
            notes.append(f"run directory kept undeleted after a relocation failure: {_posix(target['path'])}")
        deleted, kept_in_place, deletion_failures = _apply_deletions(deletable, referenced, repo, runs_root, settings)
        failures.extend(deletion_failures)
    result = 'planned' if not args.apply else ('applied-with-failures' if failures else 'applied')
    document = {
        'tool': 'scripts/workflow_cleanup.py',
        'generated_at': _now(),
        'mode': 'apply' if args.apply else 'dry-run',
        'result': result,
        'repo': _posix(repo),
        'branch_slug': args.branch_slug,
        'runs_root': _posix(runs_root),
        'policy': settings,
        'targets': [
            {
                'run_dir': _posix(target['path']),
                'run_id': target['run_id'],
                'slug': target['slug'],
                'layout': target['layout'],
                'kind': target['kind'],
                'decision': target['decision'],
                'reasons': target['reasons'],
            }
            for target in targets
        ],
        'relocations': relocations,
        'protected': list(PROTECTED_HINTS),
        'deleted': deleted,
        'kept_in_place': kept_in_place,
        'notes': notes,
        'failures': failures,
    }
    exit_code = EXIT_FAILURE if args.apply and failures else EXIT_OK
    return document, exit_code


def build_parser():
    parser = argparse.ArgumentParser(
        description='Safe file-only cleanup of identified workflow-run resources: '
        'dry-run plan by default, --apply executes the enumerated plan.',
    )
    parser.add_argument('--repo', type=Path, default=None)
    parser.add_argument('--config', type=Path, default=None)
    parser.add_argument('--branch-slug', required=True)
    parser.add_argument('--run-id', action='append', default=[])
    parser.add_argument('--reference', action='append', default=[])
    parser.add_argument('--orphans', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--json-out', type=Path, default=None)
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    args = build_parser().parse_args(argv)
    try:
        document, exit_code = evaluate(args)
    except CleanupError as error:
        print(f'workflow_cleanup: {error}', file=sys.stderr)
        return EXIT_ERROR
    payload = json.dumps(document, ensure_ascii=False, indent=2)
    print(payload)
    if args.json_out is not None:
        target = Path(args.json_out)
        if target.parent and not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload + '\n', encoding='utf-8')
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
