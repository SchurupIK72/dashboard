"""Advisory token budgets for each skill's LEARNINGS and EVALS memory."""
import argparse
import json
from pathlib import Path
from count_tokens import count_file
from workflow_config import resolve


def validate_memory(skills_dir, config, *, preset=None, assets_dir=None):
    skills_dir = Path(skills_dir)
    if not skills_dir.is_dir():
        raise ValueError(f'Skills directory not found: {skills_dir}')
    resolve(config, preset=preset)
    skills = []
    findings = []
    for directory in sorted(skills_dir.iterdir()):
        if not directory.is_dir():
            continue
        effective = resolve(config, preset=preset, skill=directory.name)['effective']
        files = []
        for name, key in [('LEARNINGS.md', 'learnings_tokens'), ('EVALS.md', 'evals_tokens')]:
            path = directory / name
            limit = effective['budgets']['memory'][key]
            if not path.is_file():
                files.append({'path': str(path), 'status': 'MISSING', 'tokens': None, 'limit': limit})
                continue
            result = count_file(path, assets_dir=assets_dir, tokenizer=effective['tokenizer'], target_tokens=limit)
            result['limit'] = limit
            files.append(result)
            if result['status'] in ('UNKNOWN', 'OVER'):
                findings.append({'level': 'WARN', 'code': result.get('code', 'OVER_BUDGET'), 'skill': directory.name, 'path': str(path), 'message': result.get('reason', f'{result["tokens"]} tokens exceeds {limit}')})
        status = 'UNKNOWN' if any(x['status'] == 'UNKNOWN' for x in files) else 'OVER' if any(x['status'] == 'OVER' for x in files) else 'OK'
        skills.append({'skill': directory.name, 'status': status, 'files': files})
    overall = 'UNKNOWN' if any(x['status'] == 'UNKNOWN' for x in skills) else 'OVER' if any(x['status'] == 'OVER' for x in skills) else 'OK'
    return {'status': overall, 'advisory': True, 'skills_checked': len(skills), 'skills': skills, 'findings': findings}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument('--skills-dir', type=Path, default=root / 'skills')
    parser.add_argument('--config', type=Path, default=root / '.ai' / 'workflow.yaml')
    parser.add_argument('--preset')
    parser.add_argument('--assets-dir', type=Path)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = validate_memory(args.skills_dir, args.config, preset=args.preset, assets_dir=args.assets_dir)
    except Exception as error:
        print(json.dumps({'status': 'FAIL', 'error': str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
