"""Advisory pre-merge memory audit: entry diff, token counts, limits and hashes versus the base ref.

Builds the durable Markdown report `.ai/reports/memory/<version>.md` (or an
explicit `--output` path) plus a machine-readable `--json` view. Covers every
active skill, resolves effective limits through the shared YAML resolver
(defaults -> preset -> skills.<name>), counts tokens with the pinned offline
tokenizer and lists runtime mirrors next to their canonical copies without
counting mirrors as new lessons. Memory findings are advisory only: the exit
code stays 0 for them; only usage or real execution errors return non-zero.
"""

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

from count_tokens import count_text
from workflow_config import resolve

MEMORY_FILES = ('LEARNINGS.md', 'EVALS.md')
DEFAULT_MIRRORS = ('.agents/skills', '.claude/skills')
TABLE_SEPARATOR_CHARS = frozenset('|-:')


class AuditError(Exception):
    """Real execution error (git, config, filesystem) that must fail the audit."""


def git_bytes(root, args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=60)
    if result.returncode:
        detail = result.stderr.decode('utf-8', errors='replace').strip()
        raise AuditError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def base_commit_id(root, base):
    return git_bytes(root, ['rev-parse', '--verify', f'{base}^{{commit}}']).decode('utf-8').strip()


def base_tree_files(root, base, prefix):
    raw = git_bytes(root, ['ls-tree', '-r', '-z', '--name-only', base, '--', prefix]).decode('utf-8')
    return {name for name in raw.split('\0') if name}


def base_blob(root, base, rel_path):
    return git_bytes(root, ['cat-file', 'blob', f'{base}:{rel_path}'])


def entry_lines(text):
    """Significant memory lines: list items and table rows, without headings and separators."""
    entries = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        compact = stripped.replace(' ', '')
        if compact.startswith('|') and set(compact) <= TABLE_SEPARATOR_CHARS:
            continue
        entries.append(stripped)
    return entries


def diff_entries(before, after):
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    added, removed, changed = [], [], 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'insert':
            added.extend(after[j1:j2])
        elif tag == 'delete':
            removed.extend(before[i1:i2])
        elif tag == 'replace':
            old, new = before[i1:i2], after[j1:j2]
            pairs = min(len(old), len(new))
            changed += pairs
            removed.extend(old[pairs:])
            added.extend(new[pairs:])
    return {'added': added, 'removed': removed, 'changed_count': changed}


def resolved_layers(config, preset, skill):
    """Resolve defaults -> preset -> skills.<skill>; unknown skill names fall back to the preset layer."""
    try:
        return resolve(config, preset=preset, skill=skill)
    except ValueError:
        return resolve(config, preset=preset)


def audit_memory_file(skill, rel_path, name, current_bytes, base_bytes, resolved, assets_dir):
    effective = resolved['effective']
    key = 'learnings_tokens' if name == 'LEARNINGS.md' else 'evals_tokens'
    limit = effective['budgets']['memory'][key]
    base_text = base_bytes.decode('utf-8', errors='replace') if base_bytes is not None else None
    base_entries = entry_lines(base_text) if base_text is not None else []
    record = {
        'skill': skill,
        'path': rel_path,
        'file': name,
        'status': None,
        'limit': limit,
        'limit_source': resolved['provenance'].get(f'budgets.memory.{key}', 'defaults.budgets.memory'),
        'sha256': None,
        'base_sha256': hashlib.sha256(base_bytes).hexdigest() if base_bytes is not None else None,
        'before_tokens': None,
        'after_tokens': None,
        'delta_tokens': None,
        'before_bytes': len(base_bytes) if base_bytes is not None else None,
        'after_bytes': None,
        'tokenizer_status': None,
        'reason': None,
        'entry_count': None,
        'table_rows': None,
        'case_headings': None,
        'diff': diff_entries(base_entries, []),
    }
    if current_bytes is None:
        record['status'] = 'DELETED'
        before = count_text(base_text, assets_dir=assets_dir, tokenizer=effective['tokenizer'], target_tokens=limit)
        record['tokenizer_status'] = before['status']
        if before['status'] == 'UNKNOWN':
            record['reason'] = before.get('reason')
        else:
            record['before_tokens'] = before['tokens']
        return record
    record['sha256'] = hashlib.sha256(current_bytes).hexdigest()
    record['after_bytes'] = len(current_bytes)
    text = current_bytes.decode('utf-8', errors='replace')
    entries = entry_lines(text)
    record['entry_count'] = len(entries)
    record['table_rows'] = sum(1 for entry in entries if entry.startswith('|'))
    record['case_headings'] = sum(1 for line in text.splitlines() if line.strip().startswith('## '))
    record['diff'] = diff_entries(base_entries, entries)
    count = count_text(text, assets_dir=assets_dir, tokenizer=effective['tokenizer'], target_tokens=limit)
    record['tokenizer_status'] = count['status']
    if count['status'] == 'UNKNOWN':
        record['status'] = 'UNKNOWN'
        record['reason'] = count.get('reason')
    else:
        record['after_tokens'] = count['tokens']
        record['status'] = 'OVER' if count['over_target'] else 'OK'
    if base_text is not None:
        before = count_text(base_text, assets_dir=assets_dir, tokenizer=effective['tokenizer'], target_tokens=limit)
        if before['status'] != 'UNKNOWN':
            record['before_tokens'] = before['tokens']
    if record['after_tokens'] is not None and record['before_tokens'] is not None:
        record['delta_tokens'] = record['after_tokens'] - record['before_tokens']
    return record


def current_memory_files(skills_dir, prefix, excluded):
    if not skills_dir.is_dir():
        raise AuditError(f'Skills directory not found: {skills_dir}')
    files = {}
    skills = []
    for directory in sorted(skills_dir.iterdir()):
        if not directory.is_dir():
            continue
        skills.append(directory.name)
        for name in MEMORY_FILES:
            path = directory / name
            if path.is_file() and path.resolve() not in excluded:
                files[f'{prefix}/{directory.name}/{name}'] = path.read_bytes()
    return skills, files


def mirror_inventory(root, mirror_rel, prefix, canonical_hashes):
    mirror_dir = root / mirror_rel
    inventory = {'path': mirror_rel, 'exists': mirror_dir.is_dir(), 'files': []}
    if not mirror_dir.is_dir():
        return inventory
    for directory in sorted(mirror_dir.iterdir()):
        if not directory.is_dir():
            continue
        for name in MEMORY_FILES:
            path = directory / name
            if not path.is_file():
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            canonical = f'{prefix}/{directory.name}/{name}'
            inventory['files'].append({
                'path': f'{mirror_rel}/{directory.name}/{name}',
                'canonical': canonical,
                'sha256': digest,
                'in_sync': canonical_hashes.get(canonical) == digest,
            })
    return inventory


def collect_findings(records, mirrors):
    findings = []
    for record in records:
        if record['status'] == 'OVER':
            findings.append({'level': 'WARN', 'code': 'OVER_BUDGET', 'skill': record['skill'], 'path': record['path'], 'message': f"{record['after_tokens']} tokens exceeds effective limit {record['limit']}"})
        elif record['status'] == 'UNKNOWN':
            findings.append({'level': 'WARN', 'code': 'TOKENIZER_UNAVAILABLE', 'skill': record['skill'], 'path': record['path'], 'message': f"token count UNKNOWN: {record['reason']}"})
        elif record['status'] == 'DELETED':
            findings.append({'level': 'WARN', 'code': 'MEMORY_FILE_DELETED', 'skill': record['skill'], 'path': record['path'], 'message': 'memory file existed in the base ref but is missing in the working tree'})
        if record['file'] == 'EVALS.md' and record['status'] in ('OK', 'OVER') and record['entry_count'] and not record['table_rows'] and not record['case_headings']:
            findings.append({'level': 'WARN', 'code': 'FORMAT_DEFECT', 'skill': record['skill'], 'path': record['path'], 'message': 'EVALS memory has entries but neither table rows nor case headings'})
    for mirror in mirrors:
        if not mirror['exists']:
            findings.append({'level': 'WARN', 'code': 'MIRROR_MISSING', 'skill': '-', 'path': mirror['path'], 'message': 'mirror directory not found'})
        for item in mirror['files']:
            if not item['in_sync']:
                findings.append({'level': 'WARN', 'code': 'MIRROR_DRIFT', 'skill': '-', 'path': item['path'], 'message': f"runtime copy differs from canonical {item['canonical']}"})
    return findings


def build_report(root, skills_dir, config_path, preset, base, assets_dir, mirror_args, version, output_path):
    prefix = skills_dir.resolve().relative_to(root.resolve()).as_posix()
    excluded = {output_path.resolve()} if output_path is not None else set()
    commit = base_commit_id(root, base)
    base_names = {name for name in base_tree_files(root, base, prefix) if name.rsplit('/', 1)[-1] in MEMORY_FILES}
    skills, current = current_memory_files(skills_dir, prefix, excluded)
    records = []
    tokenizer_report = None
    for rel_path in sorted(set(base_names) | set(current)):
        skill = rel_path.split('/')[1]
        name = rel_path.rsplit('/', 1)[-1]
        resolved = resolved_layers(config_path, preset, skill)
        record = audit_memory_file(skill, rel_path, name, current.get(rel_path), base_blob(root, base, rel_path) if rel_path in base_names else None, resolved, assets_dir)
        if record['tokenizer_status'] is not None and tokenizer_report is None:
            probe = count_text('', assets_dir=assets_dir, tokenizer=resolved['effective']['tokenizer'])
            tokenizer_report = probe['tokenizer']
            tokenizer_report['availability'] = 'unavailable' if probe['status'] == 'UNKNOWN' else 'available'
            tokenizer_report['reason'] = probe.get('reason')
        records.append(record)
    canonical_hashes = {record['path']: record['sha256'] for record in records if record['sha256']}
    mirrors = [mirror_inventory(root, mirror_rel, prefix, canonical_hashes) for mirror_rel in mirror_args]
    findings = collect_findings(records, mirrors)
    if tokenizer_report is None:
        resolved = resolved_layers(config_path, preset, None)
        tokenizer_report = {key: resolved['effective']['tokenizer'][key] for key in ('library', 'version', 'encoding')}
        tokenizer_report['installed_version'] = None
        tokenizer_report['availability'] = 'UNKNOWN'
        tokenizer_report['reason'] = 'no memory files counted'
    statuses = {record['status'] for record in records}
    overall = 'UNKNOWN' if 'UNKNOWN' in statuses else 'OVER' if 'OVER' in statuses else 'DELETED' if 'DELETED' in statuses else 'OK'
    return {
        'advisory': True,
        'status': overall,
        'base_ref': base,
        'base_commit': commit,
        'version': version,
        'report_path': str(output_path) if output_path is not None else None,
        'report_excluded_from_hashing': output_path is not None,
        'preset': preset,
        'skills_checked': len(skills),
        'tokenizer': tokenizer_report,
        'files': records,
        'mirrors': mirrors,
        'findings': findings,
        'counts': {
            'files_ok': sum(1 for r in records if r['status'] == 'OK'),
            'files_over': sum(1 for r in records if r['status'] == 'OVER'),
            'files_unknown': sum(1 for r in records if r['status'] == 'UNKNOWN'),
            'files_deleted': sum(1 for r in records if r['status'] == 'DELETED'),
            'entries_added': sum(len(r['diff']['added']) for r in records),
            'entries_changed': sum(r['diff']['changed_count'] for r in records),
            'entries_removed': sum(len(r['diff']['removed']) for r in records),
        },
    }


def render_markdown(result):
    lines = [f"# Memory audit — {result['version'] or 'unversioned'}", '']
    lines.append('Обязательный advisory-аудит памяти: замечания ниже не блокируют merge и не дают failed функциональной приёмки только из-за содержимого памяти; функциональные проверки остаются блокирующими.')
    lines.append('')
    lines.append(f"- Status: **{result['status']}** (advisory)")
    lines.append(f"- Base ref: `{result['base_ref']}` ({result['base_commit'][:12]})")
    lines.append(f"- Skills checked: {result['skills_checked']}")
    lines.append(f"- Entries vs base: +{result['counts']['entries_added']} / ~{result['counts']['entries_changed']} / -{result['counts']['entries_removed']}")
    lines.append(f"- Files: {result['counts']['files_ok']} OK / {result['counts']['files_over']} OVER / {result['counts']['files_unknown']} UNKNOWN / {result['counts']['files_deleted']} DELETED")
    if result['report_path']:
        lines.append(f"- Report path: `{result['report_path']}` (сам отчёт исключён из хеширования и подсчёта)")
    lines.append('')
    lines.append('## Tokenizer')
    lines.append('')
    tokenizer = result['tokenizer']
    lines.append('| library | encoding | pinned | installed | availability |')
    lines.append('|---|---|---|---|---|')
    reason = tokenizer.get('reason')
    lines.append(f"| {tokenizer.get('library')} | {tokenizer.get('encoding')} | {tokenizer.get('version')} | {tokenizer.get('installed_version')} | {tokenizer.get('availability')}" + (f" ({reason})" if reason else '') + ' |')
    lines.append('')
    lines.append('При недоступном tokenizer размеры остаются UNKNOWN с причиной; эвристическая подмена счётчика запрещена.')
    lines.append('')
    lines.append('## Effective limits')
    lines.append('')
    lines.append('| skill | file | limit | source |')
    lines.append('|---|---|---|---|')
    for record in result['files']:
        lines.append(f"| {record['skill']} | {record['file']} | {record['limit']} | {record['limit_source']} |")
    lines.append('')
    lines.append('## Skills')
    lines.append('')
    lines.append('| skill | file | status | before | after | delta | limit |')
    lines.append('|---|---|---|---|---|---|---|')
    for record in result['files']:
        before_cell = record['before_tokens'] if record['before_tokens'] is not None else ('-' if record['before_bytes'] is None else 'UNKNOWN')
        after_cell = record['after_tokens'] if record['after_tokens'] is not None else ('-' if record['status'] == 'DELETED' else 'UNKNOWN')
        lines.append(f"| {record['skill']} | {record['file']} | {record['status']} | {before_cell} | {after_cell} | {record['delta_tokens'] if record['delta_tokens'] is not None else '-'} | {record['limit']} |")
    lines.append('')
    lines.append('Подсчёт охватывает все активные навыки, а не только изменённые.')
    lines.append('')
    lines.append('## Entry diff')
    lines.append('')
    changed_files = [record for record in result['files'] if record['diff']['added'] or record['diff']['removed'] or record['diff']['changed_count']]
    if not changed_files:
        lines.append('Нет изменений записей относительно базы.')
    for record in changed_files:
        lines.append(f"### {record['skill']} / {record['file']}")
        lines.append('')
        diff = record['diff']
        lines.append(f"- added: {len(diff['added'])}")
        for entry in diff['added']:
            lines.append(f"  - {entry}")
        lines.append(f"- changed: {diff['changed_count']}")
        lines.append(f"- removed: {len(diff['removed'])}")
        for entry in diff['removed']:
            lines.append(f"  - {entry}")
        lines.append('')
    lines.append('## Mirrors')
    lines.append('')
    lines.append('Runtime-копии перечислены с канонической копией; они не считаются новыми уроками, счёт ведётся только по каноническим копиям `skills/<name>/...`.')
    lines.append('')
    lines.append('| mirror | canonical | in_sync |')
    lines.append('|---|---|---|')
    for mirror in result['mirrors']:
        if not mirror['exists']:
            lines.append(f"| {mirror['path']} | - | missing |")
        for item in mirror['files']:
            lines.append(f"| {item['path']} | {item['canonical']} | {str(item['in_sync']).lower()} |")
    lines.append('')
    lines.append('## Hashes')
    lines.append('')
    lines.append('| path | sha256 | base sha256 |')
    lines.append('|---|---|---|')
    for record in result['files']:
        lines.append(f"| {record['path']} | {record['sha256'] or '-'} | {record['base_sha256'] or '-'} |")
    lines.append('')
    lines.append('## Findings (advisory)')
    lines.append('')
    if result['findings']:
        for finding in result['findings']:
            lines.append(f"- {finding['level']} {finding['code']} [{finding['skill']}] {finding['path']}: {finding['message']}")
    else:
        lines.append('Нет advisory-замечаний.')
    lines.append('')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument('--root', type=Path, default=default_root)
    parser.add_argument('--skills-dir', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--preset')
    parser.add_argument('--base', default='main')
    parser.add_argument('--assets-dir', type=Path)
    parser.add_argument('--mirror', action='append', dest='mirrors')
    parser.add_argument('--version')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    def under_root(candidate):
        path = Path(candidate)
        return path if path.is_absolute() else root / path
    skills_dir = under_root(args.skills_dir) if args.skills_dir else root / 'skills'
    config_path = under_root(args.config) if args.config else root / '.ai' / 'workflow.yaml'
    assets_dir = under_root(args.assets_dir) if args.assets_dir else None
    mirrors = args.mirrors if args.mirrors else list(DEFAULT_MIRRORS)
    output_path = under_root(args.output) if args.output else (root / '.ai' / 'reports' / 'memory' / f'{args.version}.md' if args.version else None)
    if output_path is None and not args.json:
        parser.error('--version or --output is required for the Markdown report (or use --json)')
    try:
        result = build_report(root, skills_dir, config_path, args.preset, args.base, assets_dir, mirrors, args.version, output_path)
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(render_markdown(result), encoding='utf-8')
    except (AuditError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({'advisory': False, 'status': 'FAIL', 'error': str(error)}, ensure_ascii=False))
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        counts = result['counts']
        print(f"Memory audit: {result['status']} (advisory; memory findings never block merge)")
        print(f"Base: {result['base_ref']} ({result['base_commit'][:12]})")
        print(f"Skills checked: {result['skills_checked']}; files: {counts['files_ok']} OK / {counts['files_over']} OVER / {counts['files_unknown']} UNKNOWN / {counts['files_deleted']} DELETED")
        print(f"Entries vs base: +{counts['entries_added']} / ~{counts['entries_changed']} / -{counts['entries_removed']}")
        print(f"Findings (advisory): {len(result['findings'])}")
        if output_path is not None:
            print(f"Report: {output_path}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
