"""Test evidence engine: selection, chunk planning, reconciliation, manifests.

Builds an expected node-ID set from an explicit selection (paths, node ids,
markers, exclusions; never a repository-wide sweep), plans chunks that respect
the configured per-command budget, classifies chunk run records and reconciles
the executed node IDs against every named set as sets: retries count once, and
equal totals with a missing or swapped node ID are reported as a mismatch. A
pass requires process success together with a summary; a timeout without a
summary is an incomplete run; a summary followed by unfinished teardown is a
separately registered hang. Slow and UI tiers stay explicit named sets and are
never folded into the primary set. Manifests are validated against
schemas/test-evidence.json. Budgets come from the workflow configuration and
the hang limit must strictly exceed the command limit.
"""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    import jsonschema
    import workflow_config
except ImportError as import_error:
    print(
        'test_evidence: dependencies unavailable: '
        f'{import_error}; run with the project environment',
        file=sys.stderr,
    )
    raise SystemExit(2)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / 'schemas' / 'test-evidence.json'
DEFAULT_CONFIG = Path('.ai/workflow.yaml')

OUTCOME_PASS = 'pass'
OUTCOME_FAILED = 'failed'
OUTCOME_INCOMPLETE = 'incomplete'
OUTCOME_HANG = 'hang'
SET_COMPLETED = 'completed'
SET_MISMATCH = 'mismatch'
SET_INCOMPLETE = 'incomplete'
RUN_COMPLETED = 'completed'
RUN_INCOMPLETE = 'incomplete'
TIMEOUT_EXIT_CODE = 124


class EvidenceError(ValueError):
    """Raised for configuration, selection or record input errors."""


def load_budgets(config_path):
    """Resolve command and hang budgets from the workflow configuration."""
    try:
        resolved = workflow_config.resolve(str(config_path))
    except (workflow_config.ConfigError, OSError) as error:
        raise EvidenceError(f'config error: {error}') from error
    checks = resolved['effective']['budgets']['checks']
    command_seconds = checks['command_seconds']
    hang_seconds = checks['hang_seconds']
    if hang_seconds <= command_seconds:
        raise EvidenceError(
            'config error: hang_seconds ('
            f'{hang_seconds}) must exceed command_seconds ({command_seconds})'
        )
    testing = resolved['effective']['budgets']['testing']
    config_sha = resolved['snapshot']['yaml_sha256'] or ''
    return {
        'config_path': str(config_path),
        'command_seconds': command_seconds,
        'hang_seconds': hang_seconds,
        'slowest_test_target_seconds': testing['slowest_test_target_seconds'],
        'config_sha256': config_sha,
    }


def _string_list(container, field):
    value = container.get(field)
    if value is None:
        return []
    if not isinstance(value, list):
        raise EvidenceError(f'{field}: expected a list of strings')
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise EvidenceError(f'{field}: non-empty strings required')
    return list(value)


def load_selection(path):
    """Load and validate a selection description from a JSON file."""
    raw = _read_json(path, 'selection')
    if not isinstance(raw, dict):
        raise EvidenceError('selection error: a top-level object is required')
    name = raw.get('name') or 'full'
    if not isinstance(name, str) or not name.strip():
        raise EvidenceError('selection.name: non-empty string required')
    selection = {
        'name': name,
        'paths': _string_list(raw, 'paths'),
        'markers': _string_list(raw, 'markers'),
        'node_ids': _string_list(raw, 'node_ids'),
        'exclude_paths': _string_list(raw, 'exclude_paths'),
        'exclude_node_ids': _string_list(raw, 'exclude_node_ids'),
        'tiers': [],
    }
    if not selection['paths'] and not selection['node_ids']:
        raise EvidenceError(
            'selection error: explicit paths or node ids are required; '
            'repository-wide sweeps are not supported'
        )
    known_names = {selection['name']}
    tiers = raw.get('tiers') or []
    if not isinstance(tiers, list):
        raise EvidenceError('selection.tiers: expected a list')
    for position, tier in enumerate(tiers):
        where = f'selection.tiers[{position}]'
        if not isinstance(tier, dict):
            raise EvidenceError(f'{where}: object required')
        tier_name = tier.get('name')
        if not isinstance(tier_name, str) or not tier_name.strip():
            raise EvidenceError(f'{where}.name: non-empty string required')
        if tier_name in known_names:
            raise EvidenceError(f'{where}.name: duplicate set name {tier_name}')
        known_names.add(tier_name)
        entry = {
            'name': tier_name,
            'paths': _string_list(tier, 'paths'),
            'markers': _string_list(tier, 'markers'),
            'node_ids': _string_list(tier, 'node_ids'),
            'exclude_paths': _string_list(tier, 'exclude_paths'),
            'exclude_node_ids': _string_list(tier, 'exclude_node_ids'),
        }
        if not (entry['paths'] or entry['markers'] or entry['node_ids']):
            raise EvidenceError(
                f'{where}: at least one positive selector (paths, markers, '
                'node_ids) is required; an exclusion-only tier would silently '
                'select everything'
            )
        selection['tiers'].append(entry)
    estimate = raw.get('seconds_per_node_estimate')
    if estimate is not None:
        if not isinstance(estimate, (int, float)) or estimate <= 0:
            raise EvidenceError('seconds_per_node_estimate: positive number required')
        selection['seconds_per_node_estimate'] = estimate
    return selection


def _read_json(path, label):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceError(f'{label} error: {path}: {error}') from error


def _node_entry(node_id):
    return {
        'node_id': node_id,
        'path': node_id.split('::')[0],
        'markers': [],
    }


def load_collected(path):
    """Load collected node entries: bare node-ID strings or metadata objects."""
    raw = _read_json(path, 'collected')
    if not isinstance(raw, list):
        raise EvidenceError('collected error: a top-level list is required')
    entries = []
    for position, item in enumerate(raw):
        if isinstance(item, str):
            if not item.strip():
                raise EvidenceError(f'collected[{position}]: non-empty node id required')
            entries.append(_node_entry(item))
            continue
        if not isinstance(item, dict) or not isinstance(item.get('node_id'), str):
            raise EvidenceError(
                f'collected[{position}]: a node id string or an object with node_id'
            )
        markers = item.get('markers') or []
        if not isinstance(markers, list) or not all(isinstance(m, str) for m in markers):
            raise EvidenceError(f'collected[{position}].markers: list of strings required')
        entries.append({
            'node_id': item['node_id'],
            'path': item.get('path') or item['node_id'].split('::')[0],
            'markers': list(markers),
        })
    return entries


def collect_node_ids(selection, repo_root, hang_seconds):
    """Collect node IDs over the explicit selection only, via pytest."""
    args = [sys.executable, '-m', 'pytest', '--collect-only', '-q']
    args.extend(selection['node_ids'])
    args.extend(selection['paths'])
    if selection['markers']:
        args.extend(['-m', ' or '.join(selection['markers'])])
    try:
        result = subprocess.run(
            args,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=hang_seconds,
        )
    except subprocess.TimeoutExpired as error:
        raise EvidenceError(
            f'collection exceeded the hang limit ({hang_seconds}s)'
        ) from error
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or '').strip().splitlines()[-5:]
        raise EvidenceError(
            'collection failed with exit code '
            f'{result.returncode}: ' + ' | '.join(tail)
        )
    entries = []
    seen = set()
    for line in result.stdout.splitlines():
        candidate = line.strip()
        if '::' not in candidate or candidate.startswith('=') or candidate in seen:
            continue
        seen.add(candidate)
        entries.append(_node_entry(candidate))
    if not entries:
        raise EvidenceError('collection produced no node ids for the given selection')
    return entries


def _path_under(path, prefix):
    normalized = prefix.replace('\\', '/').rstrip('/')
    if not normalized:
        return False
    return path == normalized or path.startswith(normalized + '/')


def _excluded(entry, exclude_paths, exclude_node_ids):
    if entry['node_id'] in exclude_node_ids:
        return True
    return any(_path_under(entry['path'], prefix) for prefix in exclude_paths)


def _matches_positive(entry, selection):
    """Positive selection match: explicit ids win; paths and markers combine."""
    if entry['node_id'] in selection['node_ids']:
        return True
    if not selection['paths'] and not selection['markers']:
        return False
    path_ok = not selection['paths'] or any(
        _path_under(entry['path'], prefix) for prefix in selection['paths']
    )
    marker_ok = not selection['markers'] or bool(
        set(selection['markers']).intersection(entry['markers'])
    )
    return path_ok and marker_ok


def build_expected(selection, entries):
    """Primary expected set: positively selected node IDs minus exclusions."""
    exclude_ids = set(selection['exclude_node_ids'])
    expected = []
    seen = set()
    for entry in entries:
        node_id = entry['node_id']
        if node_id in seen:
            continue
        if not _matches_positive(entry, selection):
            continue
        if _excluded(entry, selection['exclude_paths'], exclude_ids):
            continue
        seen.add(node_id)
        expected.append(node_id)
    return expected


def build_tier_set(tier, entries):
    """Named tier set resolved from positive selectors minus tier exclusions."""
    explicit = set(tier['node_ids'])
    markers = set(tier['markers'])
    exclude_ids = set(tier['exclude_node_ids'])
    collected = []
    expected = []
    for entry in entries:
        matched = (
            entry['node_id'] in explicit
            or (markers and markers.intersection(entry['markers']))
            or any(_path_under(entry['path'], prefix) for prefix in tier['paths'])
        )
        if not matched:
            continue
        collected.append(entry['node_id'])
        if _excluded(entry, tier['exclude_paths'], exclude_ids):
            continue
        if entry['node_id'] not in expected:
            expected.append(entry['node_id'])
    return collected, expected


def plan_chunks(node_ids, command_seconds, seconds_per_node):
    """Split node IDs into chunks that fit the per-command budget estimate."""
    if seconds_per_node <= 0:
        raise EvidenceError('seconds_per_node must be positive')
    per_chunk = max(1, int(command_seconds // seconds_per_node))
    chunks = []
    for start in range(0, len(node_ids), per_chunk):
        part = node_ids[start:start + per_chunk]
        chunks.append({
            'index': len(chunks) + 1,
            'node_ids': part,
            'estimated_seconds': round(len(part) * seconds_per_node, 3),
            'timeout_seconds': command_seconds,
        })
    return chunks


def build_plan(selection, entries, budgets, source):
    """Build the plan document with the primary set and explicit tier sets."""
    seconds_per_node = selection.get(
        'seconds_per_node_estimate', budgets['slowest_test_target_seconds']
    )
    expected = build_expected(selection, entries)
    if not expected:
        raise EvidenceError('expected node-ID set is empty after exclusions')
    sets = [{
        'name': selection['name'],
        'tier': False,
        'collected_node_ids': [e['node_id'] for e in entries],
        'expected_node_ids': expected,
        'chunks': plan_chunks(expected, budgets['command_seconds'], seconds_per_node),
    }]
    for tier in selection['tiers']:
        collected, tier_expected = build_tier_set(tier, entries)
        sets.append({
            'name': tier['name'],
            'tier': True,
            'collected_node_ids': collected,
            'expected_node_ids': tier_expected,
            'chunks': (
                plan_chunks(tier_expected, budgets['command_seconds'], seconds_per_node)
                if tier_expected
                else []
            ),
        })
    return {
        'plan_version': 1,
        'generated_at': _now(),
        'collection_source': source,
        'seconds_per_node_estimate': seconds_per_node,
        'budgets': {
            'config_path': budgets['config_path'],
            'command_seconds': budgets['command_seconds'],
            'hang_seconds': budgets['hang_seconds'],
            'config_sha256': budgets['config_sha256'],
        },
        'selection': {
            'name': selection['name'],
            'paths': selection['paths'],
            'markers': selection['markers'],
            'node_ids': selection['node_ids'],
            'exclude_paths': selection['exclude_paths'],
            'exclude_node_ids': selection['exclude_node_ids'],
            'tiers': [
                {
                    'name': tier['name'],
                    'paths': tier['paths'],
                    'markers': tier['markers'],
                    'node_ids': tier['node_ids'],
                    'exclude_paths': tier['exclude_paths'],
                    'exclude_node_ids': tier['exclude_node_ids'],
                }
                for tier in selection['tiers']
            ],
        },
        'sets': sets,
    }


def _dedup_keep_order(values):
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def load_records(paths):
    """Load and normalize chunk run record files."""
    records = []
    for raw_path in paths:
        data = _read_json(raw_path, 'record')
        if not isinstance(data, dict):
            raise EvidenceError(f'record error: {raw_path}: object required')
        where = f'record {raw_path}'
        set_name = data.get('set')
        if not isinstance(set_name, str) or not set_name:
            raise EvidenceError(f'{where}: set (named set this record belongs to) required')
        timeout_seconds = data.get('timeout_seconds')
        if not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
            raise EvidenceError(f'{where}: timeout_seconds must be positive')
        exit_code = data.get('exit_code', 0)
        if exit_code is not None and not isinstance(exit_code, int):
            raise EvidenceError(f'{where}: exit_code must be an integer or null')
        summary = data.get('summary')
        if summary is not None and not isinstance(summary, dict):
            raise EvidenceError(f'{where}: summary must be an object or null')
        duration_seconds = data.get('duration_seconds')
        if duration_seconds is not None and (
            not isinstance(duration_seconds, (int, float)) or duration_seconds < 0
        ):
            raise EvidenceError(f'{where}: duration_seconds must be a number or null')
        attempt = data.get('attempt', 1)
        if not isinstance(attempt, int) or attempt < 1:
            raise EvidenceError(f'{where}: attempt must be a positive integer')
        chunk = data.get('chunk')
        if chunk is not None and (not isinstance(chunk, int) or chunk < 1):
            raise EvidenceError(f'{where}: chunk must be a positive integer or null')
        command = data.get('command') or []
        if not isinstance(command, list) or not all(isinstance(c, str) for c in command):
            raise EvidenceError(f'{where}: command must be a list of strings')
        executed = _string_list({'executed_node_ids': data.get('executed_node_ids')}, 'executed_node_ids')
        skipped = _string_list({'skipped_node_ids': data.get('skipped_node_ids')}, 'skipped_node_ids')
        deselected = _string_list({'deselected_node_ids': data.get('deselected_node_ids')}, 'deselected_node_ids')
        log_path = data.get('log_path')
        if log_path is not None and not isinstance(log_path, str):
            raise EvidenceError(f'{where}: log_path must be a string or null')
        records.append({
            'set': set_name,
            'chunk': chunk,
            'attempt': attempt,
            'command': list(command),
            'timeout_seconds': float(timeout_seconds),
            'duration_seconds': (
                float(duration_seconds) if duration_seconds is not None else None
            ),
            'exit_code': exit_code,
            'timed_out': bool(data.get('timed_out', False)),
            'summary': summary,
            'executed_node_ids': _dedup_keep_order(executed),
            'skipped_node_ids': _dedup_keep_order(skipped),
            'deselected_node_ids': _dedup_keep_order(deselected),
            'log_path': log_path,
            'source': str(raw_path),
            'order': len(records),
        })
    if not records:
        raise EvidenceError('at least one record file is required')
    return records


def classify_record(record):
    """Classify one run record.

    A pass needs process success and a summary. A timeout without a summary is
    an incomplete run. A timeout after the summary line means the teardown did
    not finish: a hang, registered separately and never a pass.
    """
    timed_out = record['timed_out'] or record['exit_code'] == TIMEOUT_EXIT_CODE
    duration = record['duration_seconds']
    if not timed_out and duration is not None and duration >= record['timeout_seconds']:
        timed_out = True
    has_summary = isinstance(record['summary'], dict)
    if timed_out:
        return OUTCOME_HANG if has_summary else OUTCOME_INCOMPLETE
    if record['exit_code'] == 0:
        return OUTCOME_PASS if has_summary else OUTCOME_INCOMPLETE
    return OUTCOME_FAILED


def _group_key(record):
    if record['chunk'] is not None:
        return record['set'], 'chunk', record['chunk']
    return record['set'], 'ids', tuple(sorted(record['executed_node_ids']))


def reconcile(plan, records):
    """Compare executed node IDs per named set against the planned expectation.

    Records sharing a group (same chunk, or the same executed selection when no
    chunk is given) are attempts of one logical run: the last attempt decides
    the group outcome and the group is counted once. The union of the final
    attempts must equal the expected set exactly; equal totals with a missing
    or duplicated node ID are reported as a mismatch.
    """
    by_name = {planned['name']: planned for planned in plan['sets']}
    groups = {}
    unknown = []
    for record in records:
        if record['set'] not in by_name:
            unknown.append(record['source'])
            continue
        groups.setdefault(_group_key(record), []).append(record)
    set_reports = []
    notes = []
    for planned in plan['sets']:
        name = planned['name']
        expected = set(planned['expected_node_ids'])
        final_records = []
        for key, members in groups.items():
            if key[0] != name:
                continue
            final_records.append(max(members, key=lambda r: (r['attempt'], r['order'])))
        executed = set()
        skipped = set()
        deselected = set()
        for record in final_records:
            executed.update(record['executed_node_ids'])
            skipped.update(record['skipped_node_ids'])
            deselected.update(record['deselected_node_ids'])
        missing = sorted(expected - executed)
        unexpected = sorted(executed - expected)
        counter = Counter()
        for record in final_records:
            counter.update(record['executed_node_ids'])
        duplicates = sorted(node_id for node_id, count in counter.items() if count > 1)
        mismatch = bool(missing or unexpected)
        all_pass = bool(final_records) and all(
            record['outcome'] == OUTCOME_PASS for record in final_records
        )
        if mismatch:
            outcome = SET_MISMATCH
        elif not all_pass:
            outcome = SET_INCOMPLETE
        else:
            outcome = SET_COMPLETED
        if duplicates:
            notes.append(
                f'set {name}: node ids executed in more than one run group: '
                + ', '.join(duplicates)
            )
        set_reports.append({
            'name': name,
            'tier': planned['tier'],
            'collected_node_ids': planned['collected_node_ids'],
            'expected_node_ids': sorted(expected),
            'executed_node_ids': sorted(executed),
            'missing_node_ids': missing,
            'unexpected_node_ids': unexpected,
            'duplicate_node_ids': duplicates,
            'skipped_node_ids': sorted(skipped),
            'deselected_node_ids': sorted(deselected),
            'outcome': outcome,
        })
    completed_sets = sum(1 for report in set_reports if report['outcome'] == SET_COMPLETED)
    mismatch_any = any(report['outcome'] == SET_MISMATCH for report in set_reports)
    all_completed = all(report['outcome'] == SET_COMPLETED for report in set_reports)
    run_status = (
        RUN_COMPLETED if not unknown and not mismatch_any and all_completed
        else RUN_INCOMPLETE
    )
    if unknown:
        notes.append('records referencing unknown set names: ' + ', '.join(sorted(set(unknown))))
    return {
        'run_status': run_status,
        'mismatch': mismatch_any,
        'completed_sets': completed_sets,
        'total_sets': len(set_reports),
        'unknown_set_records': sorted(set(unknown)),
        'notes': notes,
        'sets': set_reports,
    }


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
    return result.stdout.strip() or None


def _sha256(path):
    digest = hashlib.sha256()
    digest.update(Path(path).read_bytes())
    return digest.hexdigest()


def build_manifest(plan, records, reconciliation, budgets, repo, base, lock, ui_decisions, notes):
    """Assemble the evidence manifest."""
    file_hashes = []
    selection_paths = list(plan['selection']['paths'])
    for tier in plan['selection']['tiers']:
        selection_paths.extend(tier['paths'])
    for relative in _dedup_keep_order(selection_paths):
        candidate = Path(relative)
        if not candidate.is_absolute():
            candidate = repo / candidate
        if candidate.is_file():
            file_hashes.append({'path': relative, 'sha256': _sha256(candidate)})
        else:
            notes.append(f'checked file not found for hashing: {relative}')
    lock_entry = None
    if lock is not None:
        lock_candidate = Path(lock)
        if not lock_candidate.is_absolute():
            lock_candidate = repo / lock_candidate
        if lock_candidate.is_file():
            lock_entry = {'path': str(lock), 'sha256': _sha256(lock_candidate)}
        else:
            notes.append(f'lock file not found for hashing: {lock}')
    return {
        'manifest_version': 1,
        'run_status': reconciliation['run_status'],
        'generated_at': _now(),
        'branch': _git(repo, 'rev-parse', '--abbrev-ref', 'HEAD'),
        'base_commit': base,
        'tested_commit': _git(repo, 'rev-parse', 'HEAD'),
        'environment': {
            'python': platform.python_version(),
            'platform': platform.platform(),
            'tool': 'scripts/test_evidence.py',
        },
        'budgets': {
            'config_path': budgets['config_path'],
            'command_seconds': budgets['command_seconds'],
            'hang_seconds': budgets['hang_seconds'],
            'config_sha256': budgets['config_sha256'],
        },
        'hashes': {
            'config': {
                'path': budgets['config_path'],
                'sha256': budgets['config_sha256'],
            },
            'lock': lock_entry,
            'files': file_hashes,
        },
        'confirmed_scopes': [
            report['name'] for report in reconciliation['sets']
            if report['outcome'] == SET_COMPLETED
        ],
        'selection': plan['selection'],
        'sets': [
            {key: value for key, value in report.items() if key != 'records'}
            for report in reconciliation['sets']
        ],
        'records': [
            {
                'set': record['set'],
                'chunk': record['chunk'],
                'attempt': record['attempt'],
                'command': record['command'],
                'timeout_seconds': record['timeout_seconds'],
                'duration_seconds': record['duration_seconds'],
                'exit_code': record['exit_code'],
                'timed_out': record['timed_out'],
                'summary': record['summary'],
                'executed_node_ids': record['executed_node_ids'],
                'skipped_node_ids': record['skipped_node_ids'],
                'deselected_node_ids': record['deselected_node_ids'],
                'outcome': record['outcome'],
                'log_path': record['log_path'],
            }
            for record in records
        ],
        'reconciliation': {
            'run_status': reconciliation['run_status'],
            'mismatch': reconciliation['mismatch'],
            'completed_sets': reconciliation['completed_sets'],
            'total_sets': reconciliation['total_sets'],
            'unknown_set_records': reconciliation['unknown_set_records'],
            'notes': reconciliation['notes'],
        },
        'ui_decisions': ui_decisions,
        'notes': notes,
    }


def validate_manifest(manifest, schema_path=SCHEMA_PATH):
    """Validate a manifest against the evidence schema."""
    schema = json.loads(Path(schema_path).read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator(schema).validate(manifest)


def load_ui_decisions(path):
    """Load UI-decision/evidence entries from a JSON list file."""
    if path is None:
        return []
    raw = _read_json(path, 'ui-decisions')
    if not isinstance(raw, list):
        raise EvidenceError('ui-decisions error: a top-level list is required')
    decisions = []
    for position, item in enumerate(raw):
        if not isinstance(item, dict):
            raise EvidenceError(f'ui-decisions[{position}]: object required')
        built = {}
        for field in ('decision', 'reason', 'evidence'):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                raise EvidenceError(f'ui-decisions[{position}].{field}: non-empty string required')
            built[field] = value
        decisions.append(built)
    return decisions


def load_plan(path):
    """Load a plan document produced by the plan command."""
    raw = _read_json(path, 'plan')
    if not isinstance(raw, dict) or not isinstance(raw.get('sets'), list) or not raw['sets']:
        raise EvidenceError('plan error: sets array required')
    for planned in raw['sets']:
        if not isinstance(planned, dict) or not isinstance(planned.get('name'), str):
            raise EvidenceError('plan error: every set needs a name')
        if not isinstance(planned.get('expected_node_ids'), list):
            raise EvidenceError(f"plan error: set {planned['name']} needs expected_node_ids")
    return raw


def _write_json(path, payload):
    target = Path(path)
    if target.parent and not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
    )


def _resolve_repo(value):
    return Path(value).resolve() if value else REPO_ROOT


def _config_repo_path(config_arg, repo):
    config = Path(config_arg)
    if not config.is_absolute():
        config = repo / config
    return config


def command_plan(args):
    """Build a chunk plan from a selection."""
    repo = _resolve_repo(args.repo)
    budgets = load_budgets(_config_repo_path(args.config, repo))
    selection = load_selection(args.selection)
    needs_collection = selection['paths'] or selection['markers']
    if args.collect:
        entries = collect_node_ids(selection, repo, budgets['hang_seconds'])
        source = 'live-collect'
    elif args.collected is not None:
        entries = load_collected(args.collected)
        known = {entry['node_id'] for entry in entries}
        for node_id in selection['node_ids']:
            if node_id not in known:
                entries.append(_node_entry(node_id))
        source = f'collected-file:{args.collected}'
    elif selection['node_ids']:
        entries = [_node_entry(node_id) for node_id in selection['node_ids']]
        source = 'selection-node-ids'
    else:
        raise EvidenceError(
            'selection error: paths or markers require --collect or --collected; '
            'refusing to guess a node-ID set'
        )
    plan = build_plan(selection, entries, budgets, source)
    _write_json(args.out, plan)
    chunk_count = sum(len(planned['chunks']) for planned in plan['sets'])
    print(
        f"plan: {len(plan['sets'])} set(s), "
        f"{sum(len(p['expected_node_ids']) for p in plan['sets'])} expected node id(s), "
        f"{chunk_count} chunk(s); command budget {budgets['command_seconds']}s, "
        f"hang limit {budgets['hang_seconds']}s"
    )
    return 0


def command_reconcile(args):
    """Reconcile chunk records against the plan and write the manifest."""
    repo = _resolve_repo(args.repo)
    budgets = load_budgets(_config_repo_path(args.config, repo))
    plan = load_plan(args.plan)
    records = load_records(args.records)
    for record in records:
        record['outcome'] = classify_record(record)
    reconciliation = reconcile(plan, records)
    ui_decisions = load_ui_decisions(args.ui_decisions)
    notes = []
    plan_budgets = plan.get('budgets') or {}
    if plan_budgets.get('config_sha256') and plan_budgets['config_sha256'] != budgets['config_sha256']:
        notes.append('workflow configuration changed between planning and reconciliation')
    manifest = build_manifest(
        plan, records, reconciliation, budgets, repo, args.base, args.lock,
        ui_decisions, notes,
    )
    validate_manifest(manifest)
    _write_json(args.manifest, manifest)
    for report in reconciliation['sets']:
        print(
            f"set {report['name']}: {report['outcome']} "
            f"(expected {len(report['expected_node_ids'])}, "
            f"executed {len(report['executed_node_ids'])}, "
            f"missing {len(report['missing_node_ids'])}, "
            f"unexpected {len(report['unexpected_node_ids'])})"
        )
    for record in records:
        print(
            f"record {record['source']}: set {record['set']}, "
            f"attempt {record['attempt']}, outcome {record['outcome']}"
        )
    print(f'run_status: {reconciliation["run_status"]}')
    print(f'manifest: {args.manifest}')
    return 0 if reconciliation['run_status'] == RUN_COMPLETED else 1


def command_validate_manifest(args):
    """Validate an existing manifest against the evidence schema."""
    manifest = _read_json(args.manifest, 'manifest')
    validate_manifest(manifest)
    print(f'manifest valid: {args.manifest} (run_status {manifest.get("run_status")})')
    return 0


SUPPLEMENT_VERDICTS = ('reuse', 'targeted', 'full')


def load_supplement(path):
    """Load and validate a merge-time supplement document."""
    raw = _read_json(path, 'supplement')
    if not isinstance(raw, dict):
        raise EvidenceError('supplement error: a top-level object is required')
    for field in ('generated_at', 'tool', 'verdict', 'reason', 'required_sets', 'required_checks'):
        if field not in raw:
            raise EvidenceError(f'supplement error: {field} is required')
    if raw['verdict'] not in SUPPLEMENT_VERDICTS:
        raise EvidenceError(
            'supplement error: verdict must be one of ' + ', '.join(SUPPLEMENT_VERDICTS)
        )
    if not isinstance(raw['generated_at'], str) or not raw['generated_at']:
        raise EvidenceError('supplement error: generated_at must be a non-empty string')
    if not isinstance(raw['tool'], str) or not raw['tool']:
        raise EvidenceError('supplement error: tool must be a non-empty string')
    if not isinstance(raw['reason'], str) or not raw['reason']:
        raise EvidenceError('supplement error: reason must be a non-empty string')
    if not isinstance(raw['required_sets'], list) or not all(
        isinstance(name, str) and name for name in raw['required_sets']
    ):
        raise EvidenceError('supplement error: required_sets must be a list of set names')
    if not isinstance(raw['required_checks'], list) or not all(
        isinstance(check, dict) and isinstance(check.get('kind'), str) and check['kind']
        for check in raw['required_checks']
    ):
        raise EvidenceError(
            'supplement error: required_checks must be a list of objects with a kind'
        )
    records = raw.get('records')
    if records is None:
        records = []
    if not isinstance(records, list):
        raise EvidenceError('supplement error: records must be a list or null')
    return {
        'generated_at': raw['generated_at'],
        'tool': raw['tool'],
        'verdict': raw['verdict'],
        'reason': raw['reason'],
        'required_sets': list(raw['required_sets']),
        'required_checks': list(raw['required_checks']),
        'records': list(records),
    }


def command_supplement(args):
    """Append a merge-time supplement (targeted rerun provenance) to a manifest."""
    manifest = _read_json(args.manifest, 'manifest')
    if not isinstance(manifest, dict):
        raise EvidenceError('manifest error: a top-level object is required')
    validate_manifest(manifest)
    supplement = load_supplement(args.supplement)
    known_sets = {
        stated['name']
        for stated in manifest.get('sets') or []
        if isinstance(stated, dict) and stated.get('name')
    }
    unknown = [name for name in supplement['required_sets'] if name not in known_sets]
    if unknown:
        raise EvidenceError(
            'supplement error: unknown required sets: ' + ', '.join(unknown)
        )
    entry = {key: value for key, value in supplement.items() if key != 'records'}
    manifest.setdefault('supplements', []).append(entry)
    if supplement['records']:
        manifest.setdefault('records', []).extend(supplement['records'])
    validate_manifest(manifest)
    out = args.out or args.manifest
    _write_json(out, manifest)
    print(
        f"supplement: verdict {supplement['verdict']}, required sets "
        + (', '.join(supplement['required_sets']) or 'none')
    )
    print(f'manifest: {out}')
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description='Test evidence engine: selection, chunk planning, '
        'reconciliation and schema-validated manifests.',
    )
    sub = parser.add_subparsers(dest='command', required=True)

    plan_parser = sub.add_parser('plan', help='build a chunk plan from a selection')
    plan_parser.add_argument('--selection', type=Path, required=True)
    plan_parser.add_argument('--out', type=Path, required=True)
    plan_parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    plan_parser.add_argument('--collected', type=Path, default=None)
    plan_parser.add_argument(
        '--collect',
        action='store_true',
        help='collect node ids live with pytest over the explicit selection',
    )
    plan_parser.add_argument('--repo', type=Path, default=None)
    plan_parser.set_defaults(handler=command_plan)

    reconcile_parser = sub.add_parser(
        'reconcile', help='reconcile chunk records against a plan, write a manifest'
    )
    reconcile_parser.add_argument('--plan', type=Path, required=True)
    reconcile_parser.add_argument('--records', type=Path, nargs='+', required=True)
    reconcile_parser.add_argument('--manifest', type=Path, required=True)
    reconcile_parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    reconcile_parser.add_argument('--base', default=None)
    reconcile_parser.add_argument('--lock', type=Path, default=None)
    reconcile_parser.add_argument('--ui-decisions', type=Path, default=None)
    reconcile_parser.add_argument('--repo', type=Path, default=None)
    reconcile_parser.set_defaults(handler=command_reconcile)

    validate_parser = sub.add_parser(
        'validate-manifest', help='validate a manifest against the evidence schema'
    )
    validate_parser.add_argument('--manifest', type=Path, required=True)
    validate_parser.set_defaults(handler=command_validate_manifest)

    supplement_parser = sub.add_parser(
        'supplement', help='append a merge-time supplement to an evidence manifest'
    )
    supplement_parser.add_argument('--manifest', type=Path, required=True)
    supplement_parser.add_argument('--supplement', type=Path, required=True)
    supplement_parser.add_argument('--out', type=Path, default=None)
    supplement_parser.set_defaults(handler=command_supplement)
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except EvidenceError as error:
        print(f'test_evidence: {error}', file=sys.stderr)
        return 2
    except jsonschema.ValidationError as error:
        print(f'test_evidence: manifest schema violation: {error.message}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
