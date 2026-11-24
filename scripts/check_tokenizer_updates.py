"""Read-only official-source tiktoken update preflight."""

import argparse
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import sys
from urllib.request import Request, urlopen

try:
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version, InvalidVersion
except ImportError:
    from pip._vendor.packaging.specifiers import SpecifierSet
    from pip._vendor.packaging.version import Version, InvalidVersion

from workflow_config import resolve


PYPI = 'https://pypi.org/pypi/tiktoken/json'
GITHUB = 'https://api.github.com/repos/openai/tiktoken/releases?per_page=100'


def fetch_json(url, fixture=None):
    if fixture is not None:
        return json.loads(Path(fixture).read_text(encoding='utf-8'))
    error = None
    for attempt in range(2):
        try:
            request = Request(url, headers={'User-Agent': 'dot-ai-tokenizer-preflight', 'Accept': 'application/json'})
            with urlopen(request, timeout=10) as response:
                return json.load(response)
        except (OSError, ValueError) as caught:
            error = caught
    raise ValueError(f'{url}: unavailable after two attempts: {error}')


def stable(raw):
    try:
        parsed = Version(raw.removeprefix('v'))
    except (InvalidVersion, AttributeError):
        return None
    return None if parsed.is_prerelease or parsed.is_devrelease or parsed.local else parsed


def evaluate(pypi, github, pinned, installed=None, snapshot=None, python_version=None):
    result = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'sources': [PYPI, GITHUB], 'pinned': pinned, 'installed': installed,
              'latest': None, 'status': 'UNKNOWN', 'compatible': None, 'reason': ''}
    try:
        releases = {}
        for raw, files in pypi['releases'].items():
            parsed = stable(raw)
            usable = [file for file in files if not file.get('yanked', False)]
            if parsed is not None and usable:
                releases[parsed] = usable
        tags = {stable(release.get('tag_name')) for release in github
                if not release.get('draft') and not release.get('prerelease')}
        tags.discard(None)
        if not releases or not tags:
            raise ValueError('official source has no published stable releases')
        latest = max(releases)
        result['latest'] = str(latest)
        if latest != max(tags):
            raise ValueError('official PyPI and GitHub latest stable disagree')
        target_python = python_version or platform.python_version()
        compatible = any(not file.get('requires_python') or
                         SpecifierSet(file['requires_python']).contains(target_python)
                         for file in releases[latest])
        result['compatible'] = compatible
        if snapshot is not None:
            snapshot_pin = snapshot['effective_config']['tokenizer']['version']
            if snapshot_pin != pinned:
                raise ValueError('snapshot tokenizer pin differs from current configuration')
        if snapshot is not None and latest > Version(pinned):
            result.update(status='UPDATE_PENDING', reason='preserve snapshot and pin; verify compatibility and update next run')
        elif not compatible:
            result.update(status='INCOMPATIBLE', reason=f'latest stable excludes Python {target_python}; preserve existing state')
        elif latest > Version(pinned):
            result.update(status='UPDATE_PENDING' if snapshot is not None else 'UPDATE_AVAILABLE',
                          reason='preserve snapshot and pin; update next run' if snapshot is not None else
                          'verified update procedure required before creating snapshot')
        elif latest == Version(pinned):
            result.update(status='CURRENT', reason='official sources agree with configured pin')
        else:
            raise ValueError('configured pin is newer than official latest stable')
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        result.update(status='UNKNOWN', reason=str(error))
    return result


def report_markdown(result):
    lines = ['# tiktoken dependency check', '', '| Field | Value |', '| --- | --- |']
    for field in ('checked_at', 'sources', 'pinned', 'latest', 'installed', 'status', 'compatible', 'reason'):
        value = result[field]
        if isinstance(value, list):
            value = ', '.join(value)
        lines.append(f'| {field} | {value if value is not None else "UNKNOWN"} |')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('.ai/workflow.yaml'))
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--pypi-fixture', type=Path)
    parser.add_argument('--github-fixture', type=Path)
    parser.add_argument('--python-version')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--report-dir', type=Path)
    args = parser.parse_args(argv)
    result = {'checked_at': datetime.now(timezone.utc).isoformat(), 'sources': [PYPI, GITHUB],
              'pinned': None, 'latest': None, 'installed': None, 'status': 'UNKNOWN',
              'compatible': None, 'reason': ''}
    try:
        result['pinned'] = resolve(args.config)['effective']['tokenizer']['version']
        try:
            result['installed'] = version('tiktoken')
        except PackageNotFoundError:
            pass
        snapshot = json.loads(args.snapshot.read_text(encoding='utf-8')) if args.snapshot else None
        if snapshot is not None and 'snapshot' in snapshot:
            snapshot = snapshot['snapshot']
        result = evaluate(fetch_json(PYPI, args.pypi_fixture), fetch_json(GITHUB, args.github_fixture),
                          result['pinned'], result['installed'], snapshot, args.python_version)
    except (OSError, ValueError, TypeError, KeyError) as error:
        result['reason'] = str(error)
    report_path = args.report
    if report_path is None and args.report_dir is not None:
        report_path = args.report_dir / f"tiktoken-{result['pinned'] or 'unknown'}.md"
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_markdown(result), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 2 if result['status'] in ('UNKNOWN', 'INCOMPATIBLE') else 0


if __name__ == '__main__':
    sys.exit(main())
