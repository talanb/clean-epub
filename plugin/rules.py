"""Packs and rule assembly for EPUB Scrubber.

Kept free of calibre imports so it can be tested with plain Python.
"""

import json
import re


class PackError(ValueError):
    pass


def validate_regex(find, ignore_case, replace=''):
    """Return an error message if find or its replacement template is invalid, else None."""
    try:
        # sub() parses the template up front, so bad group references fail here
        re.compile(find, re.IGNORECASE if ignore_case else 0).sub(replace, '')
    except (re.error, IndexError) as err:
        return str(err)
    return None


def _string(value, what, required=False):
    if value is None and not required:
        return ''
    if not isinstance(value, str) or (required and not value):
        raise PackError('%s must be a non-empty string' % what if required
                        else '%s must be a string' % what)
    return value


def _flag(value, what):
    if value is None:
        return False
    if not isinstance(value, bool):
        raise PackError('%s must be true or false' % what)
    return value


def _list(data, key):
    value = data.get(key, [])
    if not isinstance(value, list):
        raise PackError('"%s" must be a list' % key)
    for item in value:
        if not isinstance(item, dict):
            raise PackError('every entry in "%s" must be an object' % key)
    return value


def _replacement(rule):
    find = _string(rule.get('find'), 'Replacement "find"', required=True)
    normalized = {
        'find': find,
        'replace': _string(rule.get('replace'), 'Replacement "replace" for %r' % find),
        'regex': _flag(rule.get('regex'), 'Replacement "regex" for %r' % find),
        'ignore_case': _flag(rule.get('ignore_case'), 'Replacement "ignore_case" for %r' % find),
    }
    if normalized['regex']:
        error = validate_regex(find, normalized['ignore_case'], normalized['replace'])
        if error:
            raise PackError('Invalid regex %r: %s' % (find, error))
    return normalized


def parse_pack(text):
    """Parse and validate a pack file's text, returning the normalized pack."""
    try:
        data = json.loads(text)
    except ValueError as err:
        raise PackError('Not a valid JSON file: %s' % err)
    if not isinstance(data, dict):
        raise PackError('A pack must be a JSON object')
    return {
        'name': _string(data.get('name'), 'Pack "name"', required=True),
        'description': _string(data.get('description'), 'Pack "description"'),
        'version': _string(data.get('version'), 'Pack "version"'),
        'replacements': [_replacement(r) for r in _list(data, 'replacements')],
        'remove_files': [{'pattern': _string(r.get('pattern'), 'File "pattern"', required=True)}
                         for r in _list(data, 'remove_files')],
    }


def install_pack(packs, pack):
    """Return packs with pack added, replacing (in place) any pack of the same name."""
    result = []
    replaced = False
    for existing in packs:
        if existing['name'] == pack['name']:
            result.append(dict(pack, enabled=existing.get('enabled', True)))
            replaced = True
        else:
            result.append(existing)
    if not replaced:
        result.append(dict(pack, enabled=True))
    return result


def _enabled(rules):
    return [r for r in rules if r.get('enabled', True)]


def export_pack(name, replacements, remove_files):
    """Build a pack from the user's enabled rules."""
    return {
        'name': name,
        'description': '',
        'version': '',
        'replacements': [{k: r[k] for k in ('find', 'replace', 'regex', 'ignore_case')}
                         for r in _enabled(replacements)],
        'remove_files': [{'pattern': r['pattern']} for r in _enabled(remove_files)],
    }


def collect_rules(prefs):
    """Return (replacements, remove_patterns) from enabled packs, then the user's rules."""
    replacements = []
    patterns = []
    for pack in prefs.get('packs') or []:
        if pack.get('enabled', True):
            replacements.extend(pack['replacements'])
            patterns.extend(r['pattern'] for r in pack['remove_files'])
    replacements.extend(_enabled(prefs.get('replacements') or []))
    patterns.extend(r['pattern'] for r in _enabled(prefs.get('remove_files') or []))
    return replacements, patterns
