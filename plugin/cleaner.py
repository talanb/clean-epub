"""Strip OceanofPDF.com branding from an EPUB.

Kept free of calibre imports so it can be tested with plain Python.
"""

import re
import zipfile
from xml.etree import ElementTree

MARKER_FILE = 'oceanofpdf.com'
CONTENT_EXTENSIONS = ('.xhtml', '.html', '.htm')
CONTAINER_FILE = 'META-INF/container.xml'
ALWAYS_PROTECTED = frozenset({'mimetype', CONTAINER_FILE})

FOOTER_RE = re.compile(
    r'<div\b[^>]*>\s*<p\b[^>]*>\s*'
    r'<a\b[^>]*href\s*=\s*["\']https?://(?:www\.)?oceanofpdf\.com/?["\'][^>]*>\s*'
    r'<i\b[^>]*>\s*OceanofPDF\.com\s*</i>\s*</a>\s*</p>\s*</div>',
    re.IGNORECASE)


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


def _clean_content(data):
    """Return the entry's bytes with footers removed, or None if it has none."""
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return None
    cleaned, count = FOOTER_RE.subn('', text)
    return cleaned.encode('utf-8') if count else None


def clean_epub(src_path, dst_path):
    """Write a cleaned copy of src_path to dst_path.

    Returns True if anything was removed. If the book has no OceanofPDF
    branding, returns False and dst_path is not written.
    """
    with zipfile.ZipFile(src_path) as src:
        entries = []
        changed = False
        for info in src.infolist():
            if info.filename == MARKER_FILE:
                changed = True
                continue
            data = src.read(info)
            if info.filename.lower().endswith(CONTENT_EXTENSIONS):
                cleaned = _clean_content(data)
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
