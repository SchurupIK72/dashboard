"""Render derived host agent profiles from workflow configuration templates.

The adapter consumes the shared resolver (scripts/workflow_config.py) for
every effective value: per-host/per-role models, check budgets with the hang
limit above the command limit, report token targets, the acceptance rework
policy and the optional generation limit. Structural templates under
templates/ carry {{UPPER_SNAKE}} placeholders; rendered bytes are the only
content of the runtime copies. Modes: render summary (default, no writes),
--write (regenerate the runtime copies), --check (exit 1 on any drift
between rendered output and the on-disk runtime copies), --snapshot
(run-parameter snapshot with the config hash and the selected preset for
task-package composition). A one-off --preset selection never rewrites the
config bytes or active_preset. An optional generation limit that no host
adapter supports is reported as NOT_APPLIED with a reason and is never
simulated by truncation or a character ceiling.

Rendering scope follows the delivery contract: only hosts whose structural
templates exist in this tree are rendered. Without a flag the adapter renders
every host with a delivered template, so a tree shipped for a single host
renders exactly that host and a tree without any render template is an
error; the full template set of the source repository therefore keeps the
all-hosts default. An explicit --hosts codex,zcode selection pins the scope
and fails when a requested host's template is absent.

The stage impact-reporter targets render model, effort/thought level and the
report token target only: the reporter runs no check commands and has no
rework loop, so the check-budget and rework placeholders are optional for its
templates and the resolved values still flow through the summary and the
snapshot with the same provenance.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

try:
    import workflow_config
except ImportError as import_error:
    print(
        'render_agent_profiles: resolver unavailable: '
        f'{import_error}; run via "uv run python" with the project environment',
        file=sys.stderr,
    )
    raise SystemExit(2)


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = 'implement-spec-stage'
GENERATION_PARAMETER = 'budgets.generation.max_output_tokens'
NOT_APPLIED_REASON = (
    'no host profile adapter supports a generation output limit for this '
    'target; the value is not applied and never simulated by truncation or '
    'a character ceiling'
)
PLACEHOLDER_RE = re.compile(r'\{\{([A-Z][A-Z0-9_]*)\}\}')

TARGETS = (
    {
        'key': 'codex/implementer',
        'host': 'codex',
        'role': 'implementer',
        'template': 'templates/codex/workflow_implementer.toml',
        'runtime': '.codex/agents/workflow_implementer.toml',
    },
    {
        'key': 'zcode/implementer',
        'host': 'zcode',
        'role': 'implementer',
        'template': 'templates/zcode/workflow-implementer.md',
        'runtime': '.zcode/agents/workflow-implementer.md',
    },
    {
        'key': 'zcode/acceptance',
        'host': 'zcode',
        'role': 'acceptance',
        'template': 'templates/zcode/workflow-acceptance-tester.md',
        'runtime': '.zcode/agents/workflow-acceptance-tester.md',
        'optional': ('_REWORK_RETURNS',),
    },
    {
        'key': 'codex/impact_reporter',
        'host': 'codex',
        'role': 'impact_reporter',
        'template': 'templates/codex/workflow_impact_reporter.toml',
        'runtime': '.codex/agents/workflow_impact_reporter.toml',
        'optional': ('_CHECK_COMMAND_SECONDS', '_CHECK_HANG_SECONDS', '_REWORK_RETURNS'),
    },
    {
        'key': 'zcode/impact_reporter',
        'host': 'zcode',
        'role': 'impact_reporter',
        'template': 'templates/zcode/workflow-impact-reporter.md',
        'runtime': '.zcode/agents/workflow-impact-reporter.md',
        'optional': ('_CHECK_COMMAND_SECONDS', '_CHECK_HANG_SECONDS', '_REWORK_RETURNS'),
    },
)

MODEL_KEYS = {
    'codex': ('_MODEL', '_REASONING_EFFORT'),
    'zcode': ('_MODEL', '_THOUGHT_LEVEL'),
}

EFFORT_NAMES = {'codex': 'reasoning_effort', 'zcode': 'thoughtLevel'}

HOST_NAMES = tuple(dict.fromkeys(target['host'] for target in TARGETS))

JSON_EXCLUDED_KEYS = ('runtime_path', 'rendered_bytes', 'on_disk_bytes')


class AdapterError(ValueError):
    """Profile rendering error naming the offending target or parameter."""


def _prefix(key):
    return key.upper().replace('/', '_')


def _parse_hosts(value):
    if value is None:
        return None
    parts = [part.strip() for part in value.split(',')]
    if not all(parts) or len(parts) != len(set(parts)):
        raise AdapterError(
            f'hosts: expected unique comma-separated names of {list(HOST_NAMES)}, got {value!r}')
    unknown = [part for part in parts if part not in HOST_NAMES]
    if unknown:
        raise AdapterError(f'hosts: unknown host(s) {unknown}; known hosts: {list(HOST_NAMES)}')
    return parts


def _select_targets(hosts):
    if hosts is None:
        selected = [target for target in TARGETS if (REPO_ROOT / target['template']).is_file()]
        if not selected:
            raise AdapterError(
                'no structural profile templates found under templates/; nothing to render')
        return selected
    selected = [target for target in TARGETS if target['host'] in hosts]
    missing = sorted(
        target['template'] for target in selected
        if not (REPO_ROOT / target['template']).is_file())
    if missing:
        raise AdapterError(
            f'hosts: structural template(s) missing for the requested selection: {missing}')
    return selected


def _ascii(text):
    return text.encode('ascii', 'replace').decode()


def _selected(config, preset, target):
    try:
        resolved = workflow_config.resolve_config(
            config, preset=preset, skill=SKILL, host=target['host'], role=target['role'])
    except workflow_config.ConfigError as error:
        raise AdapterError(f"{target['key']}: {error}") from error
    if resolved['selected'] is None:
        raise AdapterError(f"{target['key']}: resolver returned no role selection")
    return resolved


def _placeholder_map(target, resolved):
    selected = resolved['selected']
    model = selected['model']
    checks = selected['budgets']['checks']
    if checks['hang_seconds'] <= checks['command_seconds']:
        raise AdapterError(
            f"{target['key']}: budgets.checks.hang_seconds "
            f"({checks['hang_seconds']}) must exceed command_seconds "
            f"({checks['command_seconds']})")
    rework = resolved['effective']['policies']['acceptance']['rework_returns']
    prefix = _prefix(target['key'])
    mapping = {
        prefix + '_MODEL': model['model'],
        prefix + '_CHECK_COMMAND_SECONDS': checks['command_seconds'],
        prefix + '_CHECK_HANG_SECONDS': checks['hang_seconds'],
        prefix + '_REWORK_RETURNS': rework,
        prefix + '_REPORT_TARGET_TOKENS': selected['budgets']['reports']['target_tokens'],
    }
    effort_key = MODEL_KEYS[target['host']][1]
    mapping[prefix + effort_key] = model['reasoning_effort' if target['host'] == 'codex' else 'thoughtLevel']
    return mapping


def _generation_row(resolved):
    value = resolved['selected']['budgets']['generation']['max_output_tokens']
    if value is None:
        return {'value': None, 'status': 'not_set', 'reason': None}
    return {'value': value, 'status': 'NOT_APPLIED', 'reason': NOT_APPLIED_REASON}


def _render_template(target, mapping):
    template_path = REPO_ROOT / target['template']
    try:
        text = template_path.read_bytes().decode('utf-8')
    except OSError as error:
        raise AdapterError(f"{target['template']}: {error}") from error
    used = set(PLACEHOLDER_RE.findall(text))
    prefix = _prefix(target['key'])
    optional = {prefix + suffix for suffix in target.get('optional', ())}
    required = set(mapping) - optional
    unknown = sorted(used - set(mapping))
    missing = sorted(required - used)
    if unknown:
        raise AdapterError(f"{target['template']}: unknown placeholders {unknown}")
    if missing:
        raise AdapterError(f"{target['template']}: missing placeholders {missing}")
    rendered = PLACEHOLDER_RE.sub(lambda match: str(mapping[match.group(1)]), text)
    residue = PLACEHOLDER_RE.search(rendered)
    if residue:
        raise AdapterError(f"{target['template']}: unresolved placeholder {residue.group(0)}")
    return rendered


def _merge_not_applied(rows, target, generation):
    if generation['status'] != 'NOT_APPLIED':
        return
    for row in rows:
        if row['parameter'] == GENERATION_PARAMETER and row['value'] == generation['value']:
            row['targets'].append(target['key'])
            return
    rows.append({
        'parameter': GENERATION_PARAMETER,
        'value': generation['value'],
        'status': 'NOT_APPLIED',
        'reason': generation['reason'],
        'targets': [target['key']],
    })


def _first_difference(on_disk, rendered):
    disk_lines = on_disk.decode('utf-8', 'replace').splitlines()
    rendered_lines = rendered.decode('utf-8', 'replace').splitlines()
    total = max(len(disk_lines), len(rendered_lines))
    for index in range(total):
        disk_line = disk_lines[index] if index < len(disk_lines) else '<missing>'
        rendered_line = rendered_lines[index] if index < len(rendered_lines) else '<missing>'
        if disk_line != rendered_line:
            return index + 1, disk_line, rendered_line
    return 0, '', ''


def render_all(config_path, preset, target_root, hosts=None):
    """Resolve, render and compare the derived profile targets in scope."""
    try:
        raw = Path(config_path).read_bytes()
        config = workflow_config.load_config(config_path)
        active = workflow_config.resolve_config(config)['preset']
        selected_preset = preset if preset is not None else active
        workflow_config.resolve_config(config, preset=selected_preset)
    except (workflow_config.ConfigError, OSError) as error:
        raise AdapterError(str(error)) from error
    scope = _select_targets(hosts)
    yaml_sha256 = hashlib.sha256(raw).hexdigest()
    not_applied = []
    entries = []
    for target in scope:
        resolved = _selected(config, selected_preset, target)
        mapping = _placeholder_map(target, resolved)
        generation = _generation_row(resolved)
        _merge_not_applied(not_applied, target, generation)
        rendered = _render_template(target, mapping)
        rendered_bytes = rendered.encode('utf-8')
        runtime_path = target_root / target['runtime']
        on_disk_bytes = runtime_path.read_bytes() if runtime_path.is_file() else None
        entries.append({
            'key': target['key'],
            'host': target['host'],
            'role': target['role'],
            'template': target['template'],
            'runtime': target['runtime'],
            'placeholders': mapping,
            'generation': generation,
            'rendered': rendered,
            'rendered_sha256': hashlib.sha256(rendered_bytes).hexdigest(),
            'on_disk_sha256': None if on_disk_bytes is None else hashlib.sha256(on_disk_bytes).hexdigest(),
            'drift': on_disk_bytes is None or on_disk_bytes != rendered_bytes,
            'runtime_path': runtime_path,
            'rendered_bytes': rendered_bytes,
            'on_disk_bytes': on_disk_bytes,
        })
    return {
        'config': str(config_path),
        'yaml_sha256': yaml_sha256,
        'skill': SKILL,
        'preset': selected_preset,
        'active_preset': active,
        'preset_scope': 'one-off' if preset is not None else 'active',
        'hosts': sorted({target['host'] for target in scope}),
        'targets': entries,
        'not_applied': not_applied,
    }


def _summary_line(entry):
    placeholders = entry['placeholders']
    prefix = _prefix(entry['key'])
    model, effort_key = MODEL_KEYS[entry['host']]
    return (
        f"{entry['key']}: {entry['runtime']} "
        f"model={placeholders[prefix + model]} "
        f"{EFFORT_NAMES[entry['host']]}={placeholders[prefix + effort_key]} "
        f"checks={placeholders[prefix + '_CHECK_COMMAND_SECONDS']}s/"
        f"{placeholders[prefix + '_CHECK_HANG_SECONDS']}s(hang>command) "
        f"report_target_tokens={placeholders[prefix + '_REPORT_TARGET_TOKENS']} "
        f"rework_returns={placeholders[prefix + '_REWORK_RETURNS']} "
        f"generation.max_output_tokens={entry['generation']['status']}"
    )


def _snapshot(result):
    targets = {}
    for entry in result['targets']:
        prefix = _prefix(entry['key'])
        model, effort_key = MODEL_KEYS[entry['host']]
        targets[entry['key']] = {
            'model': {
                'model': entry['placeholders'][prefix + model],
                EFFORT_NAMES[entry['host']]: entry['placeholders'][prefix + effort_key],
            },
            'budgets': {
                'checks': {
                    'command_seconds': entry['placeholders'][prefix + '_CHECK_COMMAND_SECONDS'],
                    'hang_seconds': entry['placeholders'][prefix + '_CHECK_HANG_SECONDS'],
                },
                'reports': {
                    'target_tokens': entry['placeholders'][prefix + '_REPORT_TARGET_TOKENS'],
                },
                'generation': entry['generation'],
            },
            'policies': {
                'acceptance': {
                    'rework_returns': entry['placeholders'][prefix + '_REWORK_RETURNS'],
                },
            },
        }
    return {
        'schema_version': 1,
        'yaml_sha256': result['yaml_sha256'],
        'selected_preset': result['preset'],
        'active_preset': result['active_preset'],
        'preset_scope': result['preset_scope'],
        'skill': result['skill'],
        'targets': targets,
    }


def _write_runtime_copies(result):
    written = []
    for entry in result['targets']:
        entry['runtime_path'].parent.mkdir(parents=True, exist_ok=True)
        entry['runtime_path'].write_bytes(entry['rendered_bytes'])
        written.append(entry['runtime'])
        entry['on_disk_bytes'] = entry['runtime_path'].read_bytes()
        entry['on_disk_sha256'] = hashlib.sha256(entry['on_disk_bytes']).hexdigest()
        entry['drift'] = entry['on_disk_bytes'] != entry['rendered_bytes']
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('.ai/workflow.yaml'))
    parser.add_argument('--preset', help='one-off preset selection; never rewrites the config or active_preset')
    parser.add_argument('--hosts',
                        help='comma-separated host scope (codex, zcode); default: every host '
                             'whose structural template exists in this tree')
    parser.add_argument('--target-root', type=Path, default=REPO_ROOT,
                        help='base directory holding the runtime copies')
    parser.add_argument('--write', action='store_true',
                        help='regenerate the runtime copies from the rendered output')
    parser.add_argument('--check', action='store_true',
                        help='compare rendered output with the runtime copies; exit 1 on drift')
    parser.add_argument('--snapshot', action='store_true',
                        help='emit the run-parameter snapshot as JSON')
    parser.add_argument('--json', action='store_true', help='emit machine-readable render results')
    args = parser.parse_args(argv)
    try:
        hosts = _parse_hosts(args.hosts)
        result = render_all(args.config, args.preset, args.target_root.resolve(), hosts)
    except (AdapterError, OSError) as error:
        message = json.dumps({'error': str(error)}) if args.json else f'render_agent_profiles: {error}'
        print(message, file=sys.stderr)
        return 2
    if args.snapshot:
        print(json.dumps(_snapshot(result), indent=2))
        return 0
    written = _write_runtime_copies(result) if args.write else []
    drift_entries = [entry for entry in result['targets'] if entry['drift']]
    if args.json:
        payload = {key: value for key, value in result.items() if key != 'targets'}
        payload['mode'] = 'write' if args.write else ('check' if args.check else 'render')
        payload['written'] = written
        payload['drift_count'] = len(drift_entries)
        payload['targets'] = [
            {key: value for key, value in entry.items() if key not in JSON_EXCLUDED_KEYS}
            for entry in result['targets']
        ]
        print(json.dumps(payload, indent=2))
        return 0
    print(
        f"render_agent_profiles: config={result['config']} preset={result['preset']} "
        f"({result['preset_scope']}, active_preset={result['active_preset']}) "
        f"skill={result['skill']} yaml_sha256={result['yaml_sha256']} "
        f"hosts={','.join(result['hosts'])}")
    for entry in result['targets']:
        print(_summary_line(entry))
    for row in result['not_applied']:
        print(f"NOT_APPLIED {row['parameter']}={row['value']} for "
              f"{', '.join(sorted(row['targets']))}: {row['reason']}")
    if written:
        print(f'written: {len(written)} runtime copies regenerated under {args.target_root}')
    if args.check:
        if not drift_entries:
            print(f"OK: no drift between rendered profiles and runtime copies "
                  f"({len(result['targets'])} targets, preset={result['preset']})")
            return 0
        for entry in drift_entries:
            if entry['on_disk_bytes'] is None:
                print(f"DRIFT: {entry['runtime']} missing on disk "
                      f"(rendered sha256 {entry['rendered_sha256']})")
                continue
            _, disk_line, rendered_line = _first_difference(
                entry['on_disk_bytes'], entry['rendered_bytes'])
            print(f"DRIFT: {entry['runtime']} on-disk sha256 {entry['on_disk_sha256']} != "
                  f"rendered sha256 {entry['rendered_sha256']}")
            print(f"  first difference: on-disk={_ascii(disk_line)}")
            print(f"                  rendered={_ascii(rendered_line)}")
        fail_total = len(drift_entries)
        print(f'FAIL: drift detected in {fail_total} of {len(result["targets"])} runtime copies')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
