"""Scrub unwanted text and files from an EPUB using user-supplied rules.

Kept free of calibre imports so it can be tested with plain Python.
"""

import re
import zipfile
from xml.etree import ElementTree

CONTENT_EXTENSIONS = ('.xhtml', '.html', '.htm')
CONTAINER_FILE = 'META-INF/container.xml'
ALWAYS_PROTECTED = frozenset({'mimetype', CONTAINER_FILE})


def glob_to_regex(pattern):
    """Compile a path glob: * and ? stay within a segment, **/ spans directories."""
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith('**/', i):
            out.append('(?:.*/)?')
            i += 3
        elif pattern.startswith('**', i):
            out.append('.*')
            i += 2
        elif pattern[i] == '*':
            out.append('[^/]*')
            i += 1
        elif pattern[i] == '?':
            out.append('[^/]')
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile(''.join(out))


def protected_paths(container_xml):
    """Paths that must never be removed: mimetype, container.xml and its rootfiles."""
    paths = set(ALWAYS_PROTECTED)
    if container_xml is None:
        return paths
    try:
        root = ElementTree.fromstring(container_xml)
    except ElementTree.ParseError:
        return paths
    for elem in root.iter():
        if elem.tag.endswith('rootfile') and elem.get('full-path'):
            paths.add(elem.get('full-path'))
    return paths


def _compile_replacements(replacements):
    """Return (regex, replacement) pairs, skipping rules whose regex is invalid."""
    compiled = []
    for rule in replacements:
        find = rule.get('find', '')
        replace = rule.get('replace', '')
        flags = re.IGNORECASE if rule.get('ignore_case') else 0
        if rule.get('regex'):
            try:
                compiled.append((re.compile(find, flags), replace))
            except re.error as err:
                print('EPUB Scrubber: skipping invalid regex %r: %s' % (find, err))
        else:
            # A function replacement keeps backslashes in literal text literal
            compiled.append((re.compile(re.escape(find), flags), lambda m, r=replace: r))
    return compiled


def _clean_content(data, replacements):
    """Return the entry's bytes with replacements applied, or None if unchanged."""
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return None
    cleaned = text
    for regex, replace in replacements:
        cleaned = regex.sub(replace, cleaned)
    return cleaned.encode('utf-8') if cleaned != text else None


def clean_epub(src_path, dst_path, replacements, remove_patterns):
    """Write a cleaned copy of src_path to dst_path.

    Returns True if anything was removed or changed. Otherwise returns
    False and dst_path is not written.
    """
    compiled = _compile_replacements(replacements)
    removals = [glob_to_regex(p) for p in remove_patterns]
    with zipfile.ZipFile(src_path) as src:
        try:
            container = src.read(CONTAINER_FILE)
        except KeyError:
            container = None
        protected = protected_paths(container)
        entries = []
        changed = False
        for info in src.infolist():
            name = info.filename
            if name not in protected and any(r.fullmatch(name) for r in removals):
                changed = True
                continue
            data = src.read(info)
            if compiled and name.lower().endswith(CONTENT_EXTENSIONS):
                cleaned = _clean_content(data, compiled)
                if cleaned is not None:
                    data = cleaned
                    changed = True
            entries.append((info, data))

    if not changed:
        return False

    # The EPUB spec requires mimetype first and uncompressed
    entries.sort(key=lambda entry: entry[0].filename != 'mimetype')
    with zipfile.ZipFile(dst_path, 'w') as dst:
        for info, data in entries:
            out = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            out.external_attr = info.external_attr
            if info.filename == 'mimetype':
                out.compress_type = zipfile.ZIP_STORED
            else:
                out.compress_type = zipfile.ZIP_DEFLATED
            dst.writestr(out, data)
    return True
