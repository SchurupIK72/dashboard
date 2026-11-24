"""Strict workflow configuration loading and immutable effective run snapshots."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

import jsonschema
import yaml


STRICT_VALIDATOR = jsonschema.validators.extend(
    jsonschema.Draft202012Validator,
    type_checker=jsonschema.Draft202012Validator.TYPE_CHECKER.redefine(
        'integer', lambda checker, value: type(value) is int))


SCHEMA_PATH = Path(__file__).resolve().parents[1] / 'schemas' / 'workflow-config.json'


class ConfigError(ValueError):
    """Configuration error containing the offending source path."""


class StrictLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ConfigError(f'line {key_node.start_mark.line + 1}: mapping key must be a string')
        if key in result:
            raise ConfigError(f'{key}: duplicate key at line {key_node.start_mark.line + 1}')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def _leaves(value, prefix=''):
    if isinstance(value, dict) and value:
        for key, child in value.items():
            yield from _leaves(child, f'{prefix}.{key}' if prefix else key)
    else:
        yield prefix, value


def _merge(target, override, provenance, source, prefix=''):
    for key, value in override.items():
        destination = f'{prefix}.{key}' if prefix else key
        origin = f'{source}.{key}'
        if isinstance(value, dict):
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
            _merge(target[key], value, provenance, origin, destination)
        else:
            target[key] = copy.deepcopy(value)
            for old in list(provenance):
                if old == destination or old.startswith(destination + '.'):
                    del provenance[old]
            provenance[destination] = origin


def _complete(value, template, path):
    if isinstance(template, dict):
        if not isinstance(value, dict):
            raise ConfigError(f'{path}: expected object')
        for key, child in template.items():
            if key not in value:
                raise ConfigError(f'{path}.{key}: required effective field is missing')
            _complete(value[key], child, f'{path}.{key}')


def _invariants(effective, path):
    checks = effective['budgets']['checks']
    if checks['hang_seconds'] <= checks['command_seconds']:
        raise ConfigError(f'{path}.budgets.checks.hang_seconds: must exceed command_seconds')


def _expanded_schema(schema):
    def expand(value):
        if isinstance(value, list):
            return [expand(child) for child in value]
        if not isinstance(value, dict):
            return value
        if '$ref' in value:
            return expand(schema['$defs'][value['$ref'].split('/')[-1]])
        return {key: expand(child) for key, child in value.items() if key != '$defs'}
    return expand(schema)


def _baseline_shape(schema):
    budgets = schema['properties']['defaults']['properties']['budgets']['properties']
    budget_shape = {key: {field: None for field in val['properties']} for key, val in budgets.items()}
    model_schema = schema['properties']['defaults']['properties']['models']['properties']
    model_shape = {host: {role: {field: None for field in fields['properties']} for role, fields in val['properties'].items()} for host, val in model_schema.items()}
    return {'budgets': budget_shape, 'models': model_shape}


def _resolve_layer(config, preset, skill=None):
    effective = {}
    provenance = {}
    _merge(effective, config['defaults'], provenance, 'defaults')
    _merge(effective, config['presets'][preset], provenance, f'presets.{preset}')
    if skill:
        entry = config['skills'].get(skill, {})
        _merge(effective, {key: entry[key] for key in ('budgets', 'models') if key in entry}, provenance, f'skills.{skill}')
    return effective, provenance


def _selected(effective, provenance, entry, skill, host, role):
    selected = {'budgets': copy.deepcopy(effective['budgets']), 'model': copy.deepcopy(effective['models'][host][role])}
    sources = {key: source for key, source in provenance.items() if key.startswith('budgets.')}
    model_prefix = f'models.{host}.{role}.'
    sources.update({'model.' + key[len(model_prefix):]: source for key, source in provenance.items() if key.startswith(model_prefix)})
    override = entry.get('roles', {}).get(host, {}).get(role, {})
    if override:
        _merge(selected, override, sources, f'skills.{skill}.roles.{host}.{role}')
    _invariants(selected, f'skills.{skill}.roles.{host}.{role}')
    return selected, sources


def validate_config(config, schema=None):
    """Validate source types, all references, completeness and every merged variant."""
    schema = schema or json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
    errors = sorted(STRICT_VALIDATOR(schema).iter_errors(config), key=lambda error: str(list(error.absolute_path)))
    if errors:
        error = errors[0]
        path = '.'.join(str(part) for part in error.absolute_path) or '$'
        raise ConfigError(f'{path}: {error.message}')
    if config['active_preset'] not in config['presets']:
        raise ConfigError('active_preset: unknown preset ' + config['active_preset'])
    schema = _expanded_schema(schema)
    shape = _baseline_shape(schema)
    _complete(config['defaults'], shape, 'defaults')
    _complete(config['policies'], {key: {field: None for field in val['properties']} for key, val in schema['properties']['policies']['properties'].items()}, 'policies')
    for preset in config['presets']:
        for skill in [None] + list(config['skills']):
            effective, provenance = _resolve_layer(config, preset, skill)
            _complete(effective, shape, 'effective')
            _invariants(effective, f'presets.{preset}')
            if skill:
                for host, roles in config['skills'][skill].get('roles', {}).items():
                    for role in roles:
                        _selected(effective, provenance, config['skills'][skill], skill, host, role)
    return config


def load_config(path):
    """Load safe YAML; reject duplicate keys and unsupported tags before schema checks."""
    try:
        return _parse_config(Path(path).read_bytes(), path)
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise ConfigError(f'{path}: {error}') from error


def _parse_config(raw, path):
    try:
        config = yaml.load(raw.decode('utf-8-sig'), Loader=StrictLoader)
    except (UnicodeError, yaml.YAMLError) as error:
        raise ConfigError(f'{path}: {error}') from error
    validate_config(config)
    return config


def resolve_config(config, preset=None, skill=None, host=None, role=None, yaml_sha256=None):
    """Resolve a validated document without mutating it or selecting any main-agent model."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
    validate_config(config, schema)
    preset = config['active_preset'] if preset is None else preset
    if preset not in config['presets']:
        raise ConfigError(f'preset: unknown preset {preset}')
    schema = _expanded_schema(schema)
    known_skills = schema['properties']['skills']['properties']
    known_hosts = schema['properties']['defaults']['properties']['models']['properties']
    if skill is not None and skill not in known_skills:
        raise ConfigError(f'skill: unknown skill {skill}')
    if host is not None and host not in known_hosts:
        raise ConfigError(f'host: unknown host {host}')
    if role is not None and role not in next(iter(known_hosts.values()))['properties']:
        raise ConfigError(f'role: unknown role {role}')
    if (host is None) != (role is None):
        raise ConfigError('host/role: must be selected together')
    effective, provenance = _resolve_layer(config, preset, skill)
    effective['tokenizer'] = copy.deepcopy(config['tokenizer'])
    effective['policies'] = copy.deepcopy(config['policies'])
    provenance.update({path: path for path, value in _leaves({'tokenizer':config['tokenizer'], 'policies':config['policies']})})
    selected = None
    selected_provenance = None
    if host is not None:
        selected, selected_provenance = _selected(effective, provenance, config['skills'].get(skill, {}), skill, host, role)
    return {'schema_version': 1, 'preset': preset, 'skill': skill, 'host': host, 'role': role, 'effective': effective, 'provenance': provenance, 'selected': selected, 'selected_provenance': selected_provenance, 'snapshot': {'yaml_sha256': yaml_sha256, 'preset': preset, 'effective_config': copy.deepcopy(effective), 'selected': copy.deepcopy(selected)}}


def resolve(path, preset=None, skill=None, host=None, role=None):
    raw = Path(path).read_bytes()
    config = _parse_config(raw, path)
    return resolve_config(config, preset, skill, host, role, hashlib.sha256(raw).hexdigest())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('.ai/workflow.yaml'))
    for option in ('preset', 'skill', 'host', 'role'):
        parser.add_argument('--' + option)
    parser.add_argument('--json', action='store_true', help='emit machine-readable effective values and provenance')
    args = parser.parse_args(argv)
    try:
        result = resolve(args.config, args.preset, args.skill, args.host, args.role)
    except (ConfigError, OSError) as error:
        print(json.dumps({'error':str(error)}) if args.json else str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
