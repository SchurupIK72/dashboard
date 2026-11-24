"""Inter-session ownership of a workflow stage or fix with write-scope reservations.

Registers one active owner per worktree for a stage-or-fix scope together with
the declared write scopes (sources, tests, reports). A second claim of the same
scope or with intersecting write scopes is refused with the owning run named
and writes nothing. Worktrees are independent because the registry lives inside
each worktree (.ai/ownership/registry.json). Stale ownership is never dropped
by mtime or PID alone: it is released on normal completion, or removed only
with proven completion or an explicit user decision. Resume keeps the owner,
the evidence list and the rework counters; a counter may never decrease. The
policy comes from the shared workflow configuration resolver
(policies.ownership.enabled). Exit codes: 0 ok (also when the policy disables
ownership), 1 conflict or refusal, 2 configuration, registry or lock error.
"""

import argparse
import fnmatch
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import jsonschema
    import workflow_config
except ImportError as import_error:
    print(
        'workflow_ownership: dependencies unavailable: '
        f'{import_error}; run with the project environment',
        file=sys.stderr,
    )
    raise SystemExit(2)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / 'schemas' / 'workflow-run.json'
REGISTRY_RELATIVE = '.ai/ownership/registry.json'
LOCK_SUFFIX = '.lock'
LOCK_WAIT_SECONDS = 5.0
GLOB_CHARS = '*?['
DIMENSIONS = ('sources', 'tests', 'reports')
RELEASE_REASONS = ('completed', 'user_decision')
REFUSED_REASONS = "mtime or PID without identity proves nothing: release requires proven completion or an explicit user decision (--reason completed|user_decision --proof ...)"


class OwnershipError(ValueError):
    """Raised for configuration, registry or input errors."""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _load_policy(config_path):
    try:
        resolved = workflow_config.resolve(str(config_path))
    except (workflow_config.ConfigError, OSError) as error:
        raise OwnershipError(f'config error: {error}') from error
    ownership = resolved['effective']['policies']['ownership']
    return {
        'enabled': bool(ownership['enabled']),
        'path': str(config_path),
        'sha256': resolved['snapshot']['yaml_sha256'],
    }


def _validate_registry(registry):
    schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(registry),
        key=lambda error: str(list(error.absolute_path)),
    )
    if errors:
        error = errors[0]
        location = '.'.join(str(part) for part in error.absolute_path) or '$'
        raise OwnershipError(f'registry invalid at {location}: {error.message}')


def _normalize(path):
    value = str(path).replace('\\', '/').strip()
    while value.startswith('./'):
        value = value[2:]
    return value.rstrip('/')


def _has_glob(value):
    return any(char in value for char in GLOB_CHARS)


def _parts(value):
    return [part for part in value.split('/') if part]


def _prefix_dir(left, right):
    left_parts, right_parts = _parts(left), _parts(right)
    if not left_parts or not right_parts:
        return False
    shorter, longer = (left_parts, right_parts) if len(left_parts) <= len(right_parts) else (right_parts, left_parts)
    return longer[:len(shorter)] == shorter


def _literal_prefix(value):
    kept = []
    for part in _parts(value):
        if _has_glob(part):
            break
        kept.append(part)
    return '/'.join(kept)


def scopes_overlap(first, second):
    """Conservative path overlap: equality, directory prefix or glob match."""
    left, right = _normalize(first), _normalize(second)
    if not left or not right:
        return False
    if left == right:
        return True
    if _has_glob(left) or _has_glob(right):
        if fnmatch.fnmatch(right, left) or fnmatch.fnmatch(left, right):
            return True
        return _prefix_dir(_literal_prefix(left), _literal_prefix(right))
    return _prefix_dir(left, right)


class RegistryLock:
    """Exclusive-create mutex guarding read-modify-write of the registry."""

    def __init__(self, registry_path, wait_seconds=LOCK_WAIT_SECONDS):
        self.path = registry_path.with_name(registry_path.name + LOCK_SUFFIX)
        self.wait_seconds = wait_seconds
        self.handle = None

    def __enter__(self):
        deadline = time.monotonic() + self.wait_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                self.handle = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise OwnershipError(f'registry busy: {self.path} held past {self.wait_seconds}s')
                time.sleep(0.1)
                continue
            os.write(self.handle, json.dumps({'pid': os.getpid(), 'acquired_at': _now()}).encode('utf-8'))
            return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.handle is not None:
            os.close(self.handle)
            self.handle = None
        try:
            self.path.unlink()
        except OSError:
            pass
        return False


def _load_registry(registry_path):
    if not registry_path.is_file():
        return None
    try:
        registry = json.loads(registry_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise OwnershipError(f'registry unreadable: {registry_path}: {error}') from error
    _validate_registry(registry)
    return registry


def _new_registry(repo, policy):
    return {
        'registry_version': 1,
        'worktree': str(repo),
        'updated_at': _now(),
        'config': {'path': policy['path'], 'sha256': policy['sha256']},
        'claims': [],
    }


def _save_registry(registry_path, registry):
    _validate_registry(registry)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = registry_path.with_name(f'{registry_path.name}.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, registry_path)


def _active_claims(registry):
    return [claim for claim in registry['claims'] if claim['status'] == 'active']


def _find_active(claims, kind, scope):
    for claim in claims:
        if claim['status'] == 'active' and claim['kind'] == kind and claim['scope'] == scope:
            return claim
    return None


def _owner_summary(claim):
    return {
        'claim_id': claim['claim_id'],
        'kind': claim['kind'],
        'scope': claim['scope'],
        'branch': claim['branch'],
        'run_id': claim['run_id'],
        'owner_agent': claim['owner_agent'],
        'acquired_at': claim['acquired_at'],
    }


def _scope_conflicts(active, scopes):
    conflicts = []
    for claim in active:
        recorded = claim['write_scopes']
        for wanted_dimension, wanted_paths in scopes.items():
            for wanted_path in wanted_paths:
                hit = None
                for held_dimension in DIMENSIONS:
                    for held_path in recorded[held_dimension]:
                        if scopes_overlap(wanted_path, held_path):
                            hit = {
                                'dimensions': f'{wanted_dimension}:{held_dimension}',
                                'requested': wanted_path,
                                'reserved': held_path,
                            }
                            break
                    if hit:
                        break
                if hit:
                    conflicts.append({'owner': _owner_summary(claim), **hit})
                    break
    return conflicts


def _parse_counters(pairs):
    counters = {}
    for pair in pairs:
        item, separator, value = pair.partition('=')
        if not separator or not item.strip() or not value.strip():
            raise OwnershipError(f'counter: expected ITEM=NON-NEGATIVE-INT, got {pair!r}')
        try:
            number = int(value)
        except ValueError as error:
            raise OwnershipError(f'counter: expected ITEM=NON-NEGATIVE-INT, got {pair!r}') from error
        if number < 0:
            raise OwnershipError(f'counter: negative values are not allowed: {pair!r}')
        counters[item.strip()] = number
    return counters


def _scope_lists(args):
    return {dimension: sorted({_normalize(path) for path in _flatten(getattr(args, dimension))}) for dimension in DIMENSIONS}


def _flatten(groups):
    return [item for group in groups for item in group]


def _emit(result):
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result.get('returncode', 0)


def cmd_reserve(args, policy, registry_path):
    if not policy['enabled']:
        return _emit({'status': 'DISABLED', 'message': 'policies.ownership.enabled=false: no reservation written'})
    with RegistryLock(registry_path, args.lock_wait_seconds):
        registry = _load_registry(registry_path) or _new_registry(args.repo, policy)
        active = _active_claims(registry)
        same = _find_active(active, args.kind, args.scope)
        if same is not None:
            return _emit({
                'status': 'CONFLICT',
                'returncode': 1,
                'reason': 'scope already owned in this worktree',
                'owner': _owner_summary(same),
                'hint': 'use resume when continuing the same run, or release/break first',
            })
        scopes = _scope_lists(args)
        conflicts = _scope_conflicts(active, scopes)
        if conflicts:
            return _emit({
                'status': 'CONFLICT',
                'returncode': 1,
                'reason': 'write scopes intersect an active reservation',
                'conflicts': conflicts,
                'hint': 'no code, tests or statuses are written; the owner above must release first',
            })
        claim = {
            'claim_id': f'{args.kind}:{args.scope}:{args.run_id}',
            'kind': args.kind,
            'scope': args.scope,
            'branch': args.branch,
            'run_id': args.run_id,
            'owner_agent': args.owner,
            'acquired_at': _now(),
            'updated_at': _now(),
            'status': 'active',
            'write_scopes': scopes,
            'evidence': sorted({_normalize(path) for path in _flatten(args.evidence)}),
            'rework_counters': _parse_counters(_flatten(args.counter)),
            'resumes': 0,
            'released_at': None,
            'release_reason': None,
            'release_proof': None,
            'released_by': None,
        }
        registry['claims'].append(claim)
        registry['updated_at'] = _now()
        _save_registry(registry_path, registry)
    return _emit({'status': 'RESERVED', 'claim': claim, 'returncode': 0})


def cmd_resume(args, policy, registry_path):
    if not policy['enabled']:
        return _emit({'status': 'DISABLED', 'message': 'policies.ownership.enabled=false: nothing to resume'})
    with RegistryLock(registry_path, args.lock_wait_seconds):
        registry = _load_registry(registry_path)
        claim = _find_active(registry['claims'], args.kind, args.scope) if registry else None
        if claim is None:
            return _emit({
                'status': 'REFUSED',
                'returncode': 1,
                'reason': f'no active {args.kind}:{args.scope} claim in this worktree',
                'hint': 'reserve first, or the previous owner released the scope',
            })
        if claim['run_id'] != args.run_id:
            return _emit({
                'status': 'CONFLICT',
                'returncode': 1,
                'reason': 'scope owned by another run',
                'owner': _owner_summary(claim),
            })
        wanted = _parse_counters(_flatten(args.counter))
        lowered = {item: claim['rework_counters'][item] for item, value in wanted.items() if item in claim['rework_counters'] and value < claim['rework_counters'][item]}
        if lowered:
            return _emit({
                'status': 'REFUSED',
                'returncode': 1,
                'reason': 'rework counters never decrease on resume',
                'counters': lowered,
            })
        for item, value in wanted.items():
            claim['rework_counters'][item] = max(value, claim['rework_counters'].get(item, 0))
        for path in _flatten(args.evidence):
            normalized = _normalize(path)
            if normalized and normalized not in claim['evidence']:
                claim['evidence'].append(normalized)
        claim['evidence'].sort()
        claim['resumes'] += 1
        claim['updated_at'] = _now()
        registry['updated_at'] = _now()
        _save_registry(registry_path, registry)
    return _emit({
        'status': 'PRESERVED',
        'returncode': 0,
        'owner': _owner_summary(claim),
        'evidence': claim['evidence'],
        'rework_counters': claim['rework_counters'],
        'resumes': claim['resumes'],
    })


def _release_claim(claim, reason, proof, actor):
    claim['status'] = 'released'
    claim['released_at'] = _now()
    claim['release_reason'] = reason
    claim['release_proof'] = proof
    claim['released_by'] = actor
    claim['updated_at'] = claim['released_at']


def cmd_release(args, policy, registry_path):
    if not policy['enabled']:
        return _emit({'status': 'DISABLED', 'message': 'policies.ownership.enabled=false: nothing to release'})
    with RegistryLock(registry_path, args.lock_wait_seconds):
        registry = _load_registry(registry_path)
        claim = _find_active(registry['claims'], args.kind, args.scope) if registry else None
        if claim is None:
            return _emit({
                'status': 'REFUSED',
                'returncode': 1,
                'reason': f'no active {args.kind}:{args.scope} claim in this worktree',
            })
        if claim['run_id'] != args.run_id:
            return _emit({
                'status': 'REFUSED',
                'returncode': 1,
                'reason': 'only the owning run releases its claim',
                'owner': _owner_summary(claim),
            })
        _release_claim(claim, 'completed', args.proof or 'normal completion', args.run_id)
        registry['updated_at'] = _now()
        _save_registry(registry_path, registry)
    return _emit({'status': 'RELEASED', 'claim_id': claim['claim_id'], 'returncode': 0})


def cmd_break(args, policy, registry_path):
    if not policy['enabled']:
        return _emit({'status': 'DISABLED', 'message': 'policies.ownership.enabled=false: no active claims can exist'})
    if args.reason not in RELEASE_REASONS:
        return _emit({'status': 'REFUSED', 'returncode': 1, 'reason': REFUSED_REASONS, 'given_reason': args.reason})
    if not (args.proof or '').strip():
        return _emit({
            'status': 'REFUSED',
            'returncode': 1,
            'reason': f'--proof is required for {args.reason}: describe the proven completion or the explicit user decision',
        })
    with RegistryLock(registry_path, args.lock_wait_seconds):
        registry = _load_registry(registry_path)
        claim = _find_active(registry['claims'], args.kind, args.scope) if registry else None
        if claim is None:
            return _emit({
                'status': 'REFUSED',
                'returncode': 1,
                'reason': f'no active {args.kind}:{args.scope} claim in this worktree',
            })
        _release_claim(claim, args.reason, args.proof, args.actor)
        registry['updated_at'] = _now()
        _save_registry(registry_path, registry)
    return _emit({
        'status': 'BROKEN',
        'returncode': 0,
        'claim_id': claim['claim_id'],
        'release_reason': args.reason,
        'release_proof': args.proof,
        'released_by': args.actor,
    })


def cmd_status(args, policy, registry_path):
    registry = _load_registry(registry_path)
    if registry is None:
        return _emit({'status': 'EMPTY', 'registry': str(registry_path), 'ownership_enabled': policy['enabled'], 'returncode': 0})
    active = _active_claims(registry)
    if args.kind:
        active = [claim for claim in active if claim['kind'] == args.kind]
    if args.scope:
        active = [claim for claim in active if claim['scope'] == args.scope]
    return _emit({
        'status': 'ACTIVE' if active else 'FREE',
        'registry': str(registry_path),
        'ownership_enabled': policy['enabled'],
        'claims': [_owner_summary(claim) | {'write_scopes': claim['write_scopes'], 'evidence': claim['evidence'], 'rework_counters': claim['rework_counters'], 'resumes': claim['resumes']} for claim in active],
        'returncode': 0,
    })


def _add_scope_arguments(parser):
    parser.add_argument('--kind', choices=['stage', 'fix'], required=True)
    parser.add_argument('--scope', required=True)


def _add_common_arguments(parser):
    parser.add_argument('--repo', type=Path, default=REPO_ROOT)
    parser.add_argument('--config', type=Path, default=None)
    parser.add_argument('--lock-wait-seconds', type=float, default=LOCK_WAIT_SECONDS)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='command', required=True)

    reserve = subparsers.add_parser('reserve')
    _add_common_arguments(reserve)
    _add_scope_arguments(reserve)
    reserve.add_argument('--branch', required=True)
    reserve.add_argument('--run-id', required=True)
    reserve.add_argument('--owner', required=True)
    for dimension in DIMENSIONS:
        reserve.add_argument(f'--{dimension}', action='append', nargs='+', default=[])
    reserve.add_argument('--evidence', action='append', nargs='+', default=[])
    reserve.add_argument('--counter', action='append', nargs='+', default=[])
    reserve.set_defaults(handler=cmd_reserve)

    resume = subparsers.add_parser('resume')
    _add_common_arguments(resume)
    _add_scope_arguments(resume)
    resume.add_argument('--run-id', required=True)
    resume.add_argument('--evidence', action='append', nargs='+', default=[])
    resume.add_argument('--counter', action='append', nargs='+', default=[])
    resume.set_defaults(handler=cmd_resume)

    release = subparsers.add_parser('release')
    _add_common_arguments(release)
    _add_scope_arguments(release)
    release.add_argument('--run-id', required=True)
    release.add_argument('--proof', default='')
    release.set_defaults(handler=cmd_release)

    break_parser = subparsers.add_parser('break')
    _add_common_arguments(break_parser)
    _add_scope_arguments(break_parser)
    break_parser.add_argument('--actor', required=True)
    break_parser.add_argument('--reason', required=True)
    break_parser.add_argument('--proof', default='')
    break_parser.set_defaults(handler=cmd_break)

    status = subparsers.add_parser('status')
    _add_common_arguments(status)
    status.add_argument('--kind', choices=['stage', 'fix'])
    status.add_argument('--scope')
    status.set_defaults(handler=cmd_status)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    config = args.config if args.config is not None else repo / '.ai' / 'workflow.yaml'
    registry_path = repo / REGISTRY_RELATIVE
    try:
        policy = _load_policy(config)
        return args.handler(args, policy, registry_path)
    except OwnershipError as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
