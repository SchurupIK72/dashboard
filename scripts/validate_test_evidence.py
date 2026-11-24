"""Match recorded test evidence against the prospective merge state.

Reads a step-3 or accepted small-fix evidence manifest and compares it with
the prospective merge state: changes since the recorded tested commit,
main-side changes since the recorded base commit, and the release artifacts
integrate-release produces itself. Every changed path is classified against
recorded hashes, selections and named sets: provably unchanged or
release-only paths allow reuse, version-only pins and declared impact maps
require a targeted rerun with a manifest supplement, and paths whose impact
boundaries cannot be proven require the full corresponding suite. A main-side
comparison that cannot be resolved or fails is itself an unproven boundary and
requires the full suite. A non-empty
tests diff and workflow emoji are never consulted as conditions or proof.
Exit codes: 0 reuse, 1 targeted, 2 full, 3 input error.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path('.ai/workflow.yaml')

VERDICT_REUSE = 'reuse'
VERDICT_TARGETED = 'targeted'
VERDICT_FULL = 'full'
EXIT_BY_VERDICT = {VERDICT_REUSE: 0, VERDICT_TARGETED: 1, VERDICT_FULL: 2}
EXIT_ERROR = 3
SUPPLEMENT_VERSION = 1

RELEASE_ONLY_EXACT = {
    '.ai/CHANGELOG.md',
    '.ai/DECISIONS.md',
    '.ai/TESTS_ARCHITECTURE.md',
    'CHANGELOG.md',
}
RELEASE_ONLY_PREFIXES = (
    '.ai/release-notes/',
    '.ai/specs/',
    '.ai/reports/',
    '.ai/fixes/',
    '.ai/workflow-runs/',
)
DEFAULT_VERSION_CARRIERS = {
    'pyproject.toml',
    'package.json',
    'Cargo.toml',
    'VERSION',
    'version.txt',
}
VERSION_LINE = re.compile(
    r'(?i)^\s*(?:["\']?version["\']?\s*[:=]\s*["\']?)?v?\d+(?:\.\d+){1,3}["\']?\s*,?\s*$'
)


class EvidenceFitnessError(ValueError):
    """Raised for malformed tool inputs: arguments, manifest or scope files."""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _git(repo, *args):
    try:
        result = subprocess.run(
            ['git', '-C', str(repo), *args],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=30,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _normalized(path):
    return str(path).replace('\\', '/')


def _path_under(path, prefix):
    normalized = _normalized(prefix).rstrip('/')
    if not normalized:
        return False
    return path == normalized or path.startswith(normalized + '/')


def _commit_exists(repo, commit):
    return _git(repo, 'cat-file', '-e', f'{commit}^{{commit}}') is not None


def _resolve_ref(repo, ref):
    out = _git(repo, 'rev-parse', '--verify', ref)
    return out.strip() if out and out.strip() else None


def _working_sha(repo, relative):
    try:
        return hashlib.sha256((repo / relative).read_bytes()).hexdigest()
    except OSError:
        return None


def _blob_sha(repo, ref, relative):
    try:
        result = subprocess.run(
            ['git', '-C', str(repo), 'show', f'{ref}:{relative}'],
            capture_output=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    return hashlib.sha256(result.stdout).hexdigest()


def _changed_paths(repo, diff_args):
    out = _git(repo, 'diff', '--name-only', *diff_args)
    if out is None:
        return None
    return [_normalized(line.strip()) for line in out.splitlines() if line.strip()]


def _untracked_paths(repo):
    out = _git(repo, 'status', '--porcelain', '--untracked-files=all')
    if out is None:
        return []
    return [
        _normalized(line[3:].strip())
        for line in out.splitlines()
        if line.startswith('?? ')
    ]


def _diff_changed_lines(repo, diff_args, path):
    out = _git(repo, 'diff', *diff_args, '--', path)
    if out is None:
        return None
    lines = []
    for line in out.splitlines():
        if line.startswith('+++') or line.startswith('---'):
            continue
        if line.startswith('+') or line.startswith('-'):
            lines.append(line[1:])
    return lines


def _is_version_only(lines):
    if not lines:
        return False
    return all(VERSION_LINE.match(line) for line in lines)


def _is_release_only(path, extra):
    if path in RELEASE_ONLY_EXACT:
        return True
    if any(path.startswith(prefix) for prefix in RELEASE_ONLY_PREFIXES):
        return True
    return any(_path_under(path, item) for item in extra)


def _repo_path(value, repo):
    path = Path(value)
    if path.is_absolute():
        return path
    return repo / path


def _repo_relative(path, repo):
    normalized = _normalized(path)
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            normalized = _normalized(str(candidate.resolve().relative_to(repo.resolve())))
        except (OSError, ValueError):
            pass
    return normalized.replace('\\', '/')


def _entry_path_matches(entry_path, path):
    if not entry_path:
        return False
    if entry_path == path:
        return True
    return entry_path.endswith('/' + path)


def _read_json(path, label):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceFitnessError(f'{label} error: {path}: {error}') from error


def load_manifest(path, repo):
    if path is None:
        return None, None
    resolved = _repo_path(path, repo)
    if not resolved.is_file():
        return None, str(path)
    raw = _read_json(resolved, 'manifest')
    if not isinstance(raw, dict):
        raise EvidenceFitnessError('manifest error: a top-level object is required')
    return raw, None


def selection_paths_by_set(manifest):
    selection = manifest.get('selection') or {}
    primary_name = selection.get('name')
    tiers = {}
    for tier in selection.get('tiers') or []:
        if isinstance(tier, dict) and tier.get('name'):
            tiers[tier['name']] = tier
    result = {}
    for stated in manifest.get('sets') or []:
        if not isinstance(stated, dict) or not stated.get('name'):
            continue
        name = stated['name']
        paths = []
        if name == primary_name:
            paths.extend(selection.get('paths') or [])
        elif name in tiers:
            paths.extend(tiers[name].get('paths') or [])
        for field in ('collected_node_ids', 'expected_node_ids', 'executed_node_ids'):
            for node in stated.get(field) or []:
                paths.append(_normalized(str(node).split('::')[0]))
        result[name] = sorted({_normalized(p) for p in paths if p})
    return result


def covering_sets(path, by_set):
    return sorted(
        name
        for name, prefixes in by_set.items()
        if any(_path_under(path, prefix) for prefix in prefixes)
    )


def load_impact_map(path, by_set, repo):
    if path is None:
        return {}, []
    raw = _read_json(_repo_path(path, repo), 'impact-map')
    if not isinstance(raw, dict):
        raise EvidenceFitnessError('impact-map error: a top-level object is required')
    mapping = {}
    unknown = []
    for key, sets in raw.items():
        if not isinstance(sets, list) or not all(isinstance(s, str) for s in sets):
            raise EvidenceFitnessError(
                f'impact-map error: {key}: a list of set names is required'
            )
        mapping[_normalized(key)] = list(sets)
        for name in sets:
            if name not in by_set:
                unknown.append(name)
    return mapping, sorted(set(unknown))


def load_defect_scope(path, repo):
    if path is None:
        return None
    raw = _read_json(_repo_path(path, repo), 'defect-scope')
    if not isinstance(raw, dict):
        raise EvidenceFitnessError('defect-scope error: a top-level object is required')
    scope = {}
    for field in ('defect', 'related'):
        value = raw.get(field)
        if value is None:
            value = []
        if not isinstance(value, list) or not all(
            isinstance(p, str) and p.strip() for p in value
        ):
            raise EvidenceFitnessError(
                f'defect-scope error: {field}: a list of paths is required'
            )
        scope[field] = [_normalized(p) for p in value]
    if not scope['defect']:
        raise EvidenceFitnessError('defect-scope error: defect paths are required')
    return scope


def load_budgets(config, repo):
    try:
        import workflow_config
    except ImportError as error:
        return None, f'workflow_config unavailable: {error}'
    path = Path(config)
    if not path.is_absolute():
        path = repo / path
    try:
        resolved = workflow_config.resolve(str(path))
    except Exception as error:
        return None, f'workflow configuration unavailable: {error}'
    checks = resolved['effective']['budgets']['checks']
    suites = (
        resolved['effective'].get('policies', {}).get('testing', {}).get('suites', [])
    )
    return {
        'config_path': str(config),
        'command_seconds': checks['command_seconds'],
        'hang_seconds': checks['hang_seconds'],
        'testing_suites': suites,
    }, None


def _lookup_recorded(recorded_files, path):
    if path in recorded_files:
        return recorded_files[path]
    for key, sha in recorded_files.items():
        if key.endswith('/' + path):
            return sha
    return None


def _classify(path, side, state):
    manifest = state['manifest']
    repo = state['repo']
    if side == 'branch':
        current = _working_sha(repo, path)
    else:
        current = _blob_sha(repo, state['base_ref'], path)
    recorded = _lookup_recorded(state['recorded_files'], path)
    if recorded is not None and current is not None and recorded == current:
        state['unchanged'].append(path)
        state['notes'].append(f'{path}: content matches the recorded evidence hash')
        return
    for label, entry, sha_ref in (
        ('workflow configuration', state['config_entry'], current),
        ('dependency lock', state['lock_entry'], current),
    ):
        if not _entry_path_matches(entry.get('repo_path'), path):
            continue
        recorded_sha = entry.get('sha256')
        if recorded_sha and sha_ref is not None and sha_ref != recorded_sha:
            state['blockers'].append(
                f'{path}: {label} changed after the evidence was recorded; '
                'the old proof does not cover the new configuration'
            )
        else:
            state['unchanged'].append(path)
            state['notes'].append(f'{path}: {label} entry compared')
        return
    if _is_release_only(path, state['release_artifacts']):
        state['release_only'].append(path)
        state['notes'].append(f'{path}: release artifact without test impact')
        return
    if path in state['version_carriers']:
        if side == 'branch':
            lines = _diff_changed_lines(repo, [state['tested']], path)
        else:
            lines = _diff_changed_lines(
                repo, [f"{state['base_commit']}..{state['base_ref']}"], path
            )
        if _is_version_only(lines):
            sets = covering_sets(path, state['by_set'])
            state['required_sets'].extend(sets)
            state['version_paths'].append(path)
            state['targeted_reasons'].append(
                f'{path}: version-only change; affected recorded sets: '
                + (', '.join(sets) if sets else 'none recorded')
            )
            return
    sets = covering_sets(path, state['by_set'])
    if recorded is not None:
        if sets:
            state['required_sets'].extend(sets)
            state['targeted_reasons'].append(
                f'{path}: checked file changed after the evidence; rerun sets: '
                + ', '.join(sets)
            )
            return
        state['blockers'].append(
            f'{path}: checked file changed after the evidence but no recorded set covers it'
        )
        return
    if sets:
        state['required_sets'].extend(sets)
        state['targeted_reasons'].append(
            f'{path}: change covered by recorded sets: ' + ', '.join(sets)
        )
        return
    mapped = state['impact_map'].get(path)
    if mapped is None:
        for prefix, names in state['impact_map'].items():
            if _path_under(path, prefix):
                mapped = names
                break
    if mapped is not None:
        known = [name for name in mapped if name in state['by_set']]
        if known:
            state['required_sets'].extend(known)
            state['targeted_reasons'].append(
                f'{path}: declared impact map requires sets: ' + ', '.join(known)
            )
            return
        if not mapped:
            state['notes'].append(f'{path}: impact map declares no affected sets')
            return
        state['blockers'].append(
            f'{path}: impact map does not reference any recorded set'
        )
        return
    state['blockers'].append(f'{path}: impact boundaries cannot be proven')


def evaluate(args):
    repo = Path(args.repo).resolve() if args.repo else REPO_ROOT
    branch = (_git(repo, 'rev-parse', '--abbrev-ref', 'HEAD') or '').strip() or None
    head = (_git(repo, 'rev-parse', 'HEAD') or '').strip() or None
    notes = []
    blockers = []
    targeted_reasons = []
    required_sets = []
    version_paths = []
    defect_checks = []

    manifest, manifest_missing = load_manifest(args.manifest, repo)
    by_set = selection_paths_by_set(manifest) if manifest else {}
    impact_map, unknown_mapped = load_impact_map(args.impact_map, by_set, repo)
    if unknown_mapped:
        notes.append(
            'impact map references unknown sets (treated as unmapped): '
            + ', '.join(unknown_mapped)
        )
    defect_scope = load_defect_scope(args.defect_scope, repo)

    tested = None
    base_commit = None
    base_ref = None
    branch_side = []
    main_side = []
    state = {
        'manifest': manifest,
        'repo': repo,
        'recorded_files': {},
        'config_entry': {},
        'lock_entry': {},
        'by_set': by_set,
        'impact_map': impact_map,
        'release_artifacts': [_normalized(p) for p in (args.release_artifact or [])],
        'version_carriers': set(DEFAULT_VERSION_CARRIERS) | {
            _normalized(p) for p in (args.version_carrier or [])
        },
        'notes': notes,
        'blockers': blockers,
        'targeted_reasons': targeted_reasons,
        'required_sets': required_sets,
        'version_paths': version_paths,
        'unchanged': [],
        'release_only': [],
        'tested': None,
        'base_commit': None,
        'base_ref': None,
    }

    if manifest is None:
        if manifest_missing is not None:
            blockers.append(f'evidence manifest not found: {manifest_missing}')
        elif args.route == 'small_fix' and defect_scope is not None:
            targeted_reasons.append(
                'agreed defect+related scope; the full suite is not imposed for the '
                'absence of step-3 evidence'
            )
        elif args.route == 'small_fix':
            blockers.append(
                'no evidence manifest and no agreed defect+related scope for the '
                'small-fix route'
            )
        else:
            blockers.append('no step-3 evidence manifest for the spec route')
    else:
        run_status = manifest.get('run_status')
        if run_status != 'completed':
            blockers.append(
                f'recorded evidence run status is {run_status!r}, not completed'
            )
        tested = manifest.get('tested_commit')
        if not tested:
            blockers.append('recorded evidence has no tested commit')
        elif not _commit_exists(repo, tested):
            blockers.append(f'tested commit {tested} is not present in the repository')
        else:
            branch_diff = _changed_paths(repo, [tested])
            if branch_diff is None:
                blockers.append(
                    f'branch-side diff against tested commit {tested} failed; '
                    'the impact boundaries of the prospective merge-state '
                    'cannot be proven'
                )
            else:
                branch_side = branch_diff + _untracked_paths(repo)
                state['tested'] = tested
        base_commit = manifest.get('base_commit')
        base_ref = _resolve_ref(repo, args.base) if base_commit else None
        if base_commit:
            if not base_ref or not _commit_exists(repo, base_commit):
                blockers.append(
                    f'main-side changes cannot be resolved (base {args.base} or '
                    f'base commit {base_commit} unavailable); the impact '
                    'boundaries of the prospective merge-state cannot be proven'
                )
            else:
                main_side = _changed_paths(repo, [f'{base_commit}..{base_ref}'])
                if main_side is None:
                    blockers.append(
                        f'main-side diff {base_commit}..{base_ref} failed; the '
                        'impact boundaries of the prospective merge-state cannot '
                        'be proven'
                    )
                else:
                    state['base_commit'] = base_commit
                    state['base_ref'] = base_ref
        hashes = manifest.get('hashes') or {}
        for entry_key in ('config', 'lock'):
            entry = hashes.get(entry_key) or {}
            if entry.get('path'):
                entry['repo_path'] = _repo_relative(entry['path'], repo)
        state['config_entry'] = hashes.get('config') or {}
        state['lock_entry'] = hashes.get('lock') or {}
        state['recorded_files'] = {
            _repo_relative(entry.get('path'), repo): entry.get('sha256')
            for entry in hashes.get('files') or []
            if isinstance(entry, dict) and entry.get('path') and entry.get('sha256')
        }
        recorded_branch = manifest.get('branch')
        if branch and recorded_branch and recorded_branch != branch:
            notes.append(
                f'evidence was recorded on branch {recorded_branch}, current branch is {branch}'
            )

    changed = {}
    for path in branch_side:
        changed[path] = 'branch'
    for path in main_side:
        changed.setdefault(path, 'main')
    input_paths = {
        _repo_relative(value, repo)
        for value in (args.manifest, args.impact_map, args.defect_scope)
        if value is not None
    }
    for path in sorted(changed):
        if path in input_paths:
            notes.append(f'{path}: tool input, not part of the classified state')
            continue
        _classify(path, changed[path], state)

    if args.route == 'small_fix' and defect_scope is not None:
        defect_checks.append({'kind': 'defect-reproduction', 'paths': defect_scope['defect']})
        if defect_scope['related']:
            defect_checks.append({'kind': 'related-checks', 'paths': defect_scope['related']})

    required_checks = []
    if blockers:
        verdict = VERDICT_FULL
        reasons = list(blockers)
        required_checks.append({'kind': 'full-suite', 'reasons': list(blockers)})
    else:
        required_checks.extend(defect_checks)
        if version_paths:
            required_checks.append(
                {'kind': 'version-consistency', 'paths': sorted(set(version_paths))}
            )
        for name in sorted(set(required_sets)):
            required_checks.append({'kind': 'set', 'set': name})
        if required_checks:
            verdict = VERDICT_TARGETED
            reasons = list(targeted_reasons)
        else:
            verdict = VERDICT_REUSE
            reasons = ['recorded evidence covers the prospective merge state']

    budgets, budgets_note = load_budgets(args.config, repo)
    if budgets_note:
        notes.append(budgets_note)
    if budgets:
        budgets['config_path'] = _normalized(budgets['config_path'])

    supplement = None
    if verdict == VERDICT_TARGETED:
        supplement = {
            'supplement_version': SUPPLEMENT_VERSION,
            'generated_at': _now(),
            'tool': 'scripts/validate_test_evidence.py',
            'verdict': verdict,
            'reason': '; '.join(targeted_reasons),
            'origin_manifest': str(args.manifest) if args.manifest else None,
            'required_sets': sorted(set(required_sets)),
            'required_checks': required_checks,
            'records': [],
        }

    document = {
        'tool': 'scripts/validate_test_evidence.py',
        'generated_at': _now(),
        'repo': str(repo),
        'branch': branch,
        'head': head,
        'route': args.route,
        'manifest': (
            None
            if manifest is None
            else {
                'path': str(args.manifest),
                'run_status': manifest.get('run_status'),
                'branch': manifest.get('branch'),
                'base_commit': manifest.get('base_commit'),
                'tested_commit': manifest.get('tested_commit'),
                'confirmed_scopes': manifest.get('confirmed_scopes') or [],
            }
        ),
        'prospective': {
            'base_ref': args.base,
            'branch_side_changed': sorted(p for p, s in changed.items() if s == 'branch'),
            'main_side_changed': sorted(p for p, s in changed.items() if s == 'main'),
        },
        'classifications': {
            'unchanged': sorted(set(state['unchanged'])),
            'release_only': sorted(set(state['release_only'])),
            'version_only': sorted(set(version_paths)),
        },
        'verdict': verdict,
        'reasons': reasons,
        'required_sets': sorted(set(required_sets)) if not blockers else [],
        'required_checks': required_checks,
        'budgets': budgets,
        'notes': notes,
        'supplement': supplement,
    }
    return document, verdict


def build_parser():
    parser = argparse.ArgumentParser(
        description='Match recorded test evidence against the prospective merge '
        'state: reuse, targeted rerun with a manifest supplement, or the full '
        'corresponding suite.',
    )
    parser.add_argument('--manifest', type=Path, default=None)
    parser.add_argument('--repo', type=Path, default=None)
    parser.add_argument('--base', default='main')
    parser.add_argument('--route', choices=('spec', 'small_fix'), default='spec')
    parser.add_argument('--defect-scope', type=Path, default=None)
    parser.add_argument('--impact-map', type=Path, default=None)
    parser.add_argument('--release-artifact', action='append', default=None)
    parser.add_argument('--version-carrier', action='append', default=None)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--json-out', type=Path, default=None)
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    args = build_parser().parse_args(argv)
    try:
        document, verdict = evaluate(args)
    except EvidenceFitnessError as error:
        print(f'validate_test_evidence: {error}', file=sys.stderr)
        return EXIT_ERROR
    payload = json.dumps(document, indent=2, ensure_ascii=False)
    print(payload)
    if args.json_out is not None:
        target = Path(args.json_out)
        if target.parent and not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload + '\n', encoding='utf-8')
    print(
        f'verdict: {verdict}; required sets: '
        f"{', '.join(document['required_sets']) or 'none'}",
        file=sys.stderr,
    )
    return EXIT_BY_VERDICT[verdict]


if __name__ == '__main__':
    raise SystemExit(main())
