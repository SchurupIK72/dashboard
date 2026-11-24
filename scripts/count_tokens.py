"""Exact, pinned, offline token counting for workflow artifacts."""
import argparse
import base64
import hashlib
import importlib.metadata
import json
from pathlib import Path
import types

ENCODING = 'cl100k_base'
TABLE_SHA256 = '223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7'
TABLE_URL = 'https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken'
ASSETS_DIR = Path(__file__).resolve().parents[1] / 'assets' / 'tokenizers'


def normalize_text(text):
    return text.removeprefix('\ufeff').replace('\r\n', '\n').replace('\r', '\n')


def count_text(text, *, assets_dir=None, tokenizer=None, target_tokens=None):
    if tokenizer is None:
        from workflow_config import resolve
        tokenizer = resolve(Path(__file__).resolve().parents[1] / '.ai' / 'workflow.yaml')['effective']['tokenizer']
    diagnostic = {key: tokenizer[key] for key in ('library', 'version', 'encoding')}
    diagnostic['installed_version'] = None
    result = {'status': 'UNKNOWN', 'tokens': None, 'target_tokens': target_tokens, 'over_target': None, 'tokenizer': diagnostic}
    try:
        diagnostic['installed_version'] = importlib.metadata.version('tiktoken')
        if diagnostic['library'] != 'tiktoken' or diagnostic['encoding'] != ENCODING:
            raise ValueError('unsupported tokenizer library or encoding')
        if diagnostic['installed_version'] != diagnostic['version']:
            raise ValueError('installed tiktoken differs from pinned version')
        raw = (Path(assets_dir) if assets_dir is not None else ASSETS_DIR).joinpath(ENCODING + '.tiktoken').read_bytes()
        if hashlib.sha256(raw).hexdigest() != TABLE_SHA256:
            raise ValueError('encoding table SHA256 mismatch')
        import tiktoken
        import tiktoken_ext.openai_public as public
        ranks = {base64.b64decode(token, validate=True): int(rank) for token, rank in (line.split() for line in raw.splitlines() if line)}
    except (ImportError, importlib.metadata.PackageNotFoundError, OSError, ValueError) as error:
        result.update(code='TOKENIZER_UNAVAILABLE', reason=str(error))
        return result
    isolated = types.ModuleType('offline_tiktoken_public')
    exec(compile(Path(public.__file__).read_bytes(), public.__file__, 'exec'), isolated.__dict__)
    isolated.load_tiktoken_bpe = lambda *args, **kwargs: ranks
    parameters = isolated.cl100k_base()
    encoder = tiktoken.Encoding(**parameters)
    tokens = len(encoder.encode_ordinary(normalize_text(text)))
    over = target_tokens is not None and tokens > target_tokens
    result.update(status='OVER' if over else 'OK', tokens=tokens, over_target=over)
    return result


def count_file(path, **kwargs):
    result = count_text(Path(path).read_text(encoding='utf-8'), **kwargs)
    return dict(result, path=str(path))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', type=Path)
    parser.add_argument('--assets-dir', type=Path)
    parser.add_argument('--target-tokens', type=int)
    parser.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[1] / '.ai' / 'workflow.yaml')
    for option in ('preset', 'skill', 'host', 'role'):
        parser.add_argument('--' + option)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        tokenizer = None
        target = args.target_tokens
        if args.config:
            from workflow_config import resolve
            resolved = resolve(args.config, args.preset, args.skill, args.host, args.role)
            effective = resolved['selected'] or resolved['effective']
            tokenizer = resolved['effective']['tokenizer']
            if target is None:
                target = effective['budgets']['reports']['target_tokens']
        if target is not None and target <= 0:
            raise ValueError('target_tokens must be positive')
        files = [count_file(path, assets_dir=args.assets_dir, tokenizer=tokenizer, target_tokens=target) for path in args.files]
        status = 'UNKNOWN' if any(x['status'] == 'UNKNOWN' for x in files) else 'OVER' if any(x['status'] == 'OVER' for x in files) else 'OK'
        output = {'status': status, 'files': files}
    except Exception as error:
        output = {'status': 'FAIL', 'error': str(error)}
        print(json.dumps(output, ensure_ascii=False))
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
