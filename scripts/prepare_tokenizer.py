"""Explicit online provisioning; ordinary token counting never downloads data."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
from count_tokens import ASSETS_DIR, ENCODING, TABLE_SHA256, TABLE_URL


def provision(assets_dir=ASSETS_DIR):
    from workflow_config import resolve
    version = resolve(Path(__file__).resolve().parents[1] / '.ai' / 'workflow.yaml')['effective']['tokenizer']['version']
    raw = urllib.request.urlopen(TABLE_URL, timeout=60).read()
    if hashlib.sha256(raw).hexdigest() != TABLE_SHA256:
        raise ValueError('downloaded encoding table SHA256 mismatch')
    destination = Path(assets_dir)
    destination.mkdir(parents=True, exist_ok=True)
    table = destination / (ENCODING + '.tiktoken')
    table.write_bytes(raw)
    metadata = {'library': 'tiktoken', 'version': version, 'encoding': ENCODING, 'sha256': TABLE_SHA256, 'url': TABLE_URL, 'hash_source': f'https://github.com/openai/tiktoken/blob/{version}/tiktoken_ext/openai_public.py'}
    (destination / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    return dict(metadata, path=str(table), status='OK')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets-dir', type=Path, default=ASSETS_DIR)
    args = parser.parse_args(argv)
    try:
        result = provision(args.assets_dir)
    except Exception as error:
        print(json.dumps({'status': 'FAIL', 'error': str(error)}))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
