import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'plugin'))

from cleaner import clean_epub  # noqa: E402

CHAPTER = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<html xmlns="http://www.w3.org/1999/xhtml"><body>\n'
           '<p>Chapter text.</p>\n{footer}</body>\n</html>')

CONTAINER = ('<?xml version="1.0"?>\n'
             '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
             '<rootfiles><rootfile full-path="OPS/content.opf" '
             'media-type="application/oebps-package+xml"/></rootfiles></container>')


def make_epub(path, entries):
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        for name, data in entries:
            zf.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)


def read_all(path):
    with zipfile.ZipFile(path) as zf:
        return {i.filename: zf.read(i) for i in zf.infolist()}


def R(find, replace='', regex=False, ignore_case=False):
    return {'find': find, 'replace': replace, 'regex': regex, 'ignore_case': ignore_case}


class CleanEpubTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, 'in.epub')
        self.dst = os.path.join(self.tmp.name, 'out.epub')

    def tearDown(self):
        self.tmp.cleanup()

    def chapter_after(self, replacements, chapter=CHAPTER.format(footer='')):
        make_epub(self.src, [('OPS/c01.xhtml', chapter)])
        self.assertTrue(clean_epub(self.src, self.dst, replacements, []))
        return read_all(self.dst)['OPS/c01.xhtml'].decode('utf-8')

    def test_mimetype_stays_first_and_stored(self):
        make_epub(self.src, [('OPS/c01.xhtml', CHAPTER.format(footer=''))])
        clean_epub(self.src, self.dst, [R('Chapter', 'X')], [])
        with zipfile.ZipFile(self.dst) as zf:
            first = zf.infolist()[0]
        self.assertEqual(first.filename, 'mimetype')
        self.assertEqual(first.compress_type, zipfile.ZIP_STORED)

    def test_literal_replacement(self):
        self.assertIn('<p>Body.</p>', self.chapter_after([R('Chapter text.', 'Body.')]))

    def test_literal_is_not_regex(self):
        self.assertEqual(self.chapter_after([R('a.c')], chapter='abc a.c'), 'abc ')

    def test_literal_replace_has_no_backrefs(self):
        self.assertIn(r'\1', self.chapter_after([R('Chapter', r'\1')]))

    def test_regex_with_backref(self):
        out = self.chapter_after([R(r'<p>(\w+) text\.</p>', r'<p>\1!</p>', regex=True)])
        self.assertIn('<p>Chapter!</p>', out)

    def test_ignore_case(self):
        self.assertIn('Ch text.', self.chapter_after([R('CHAPTER', 'Ch', ignore_case=True)]))
        self.assertFalse(clean_epub(self.src, self.dst, [R('CHAPTER', 'Ch')], []))

    def test_rules_apply_in_order(self):
        out = self.chapter_after([R('Chapter', 'X'), R('X text', 'Y')])
        self.assertIn('<p>Y.</p>', out)

    def test_only_html_entries_touched(self):
        make_epub(self.src, [
            ('OPS/C1.XHTML', CHAPTER.format(footer='')),
            ('OPS/style.css', 'p { margin: 0 }'),
        ])
        self.assertTrue(clean_epub(self.src, self.dst, [R('<p>')], []))
        out = read_all(self.dst)
        self.assertEqual(out['OPS/style.css'], b'p { margin: 0 }')
        self.assertNotIn(b'<p>', out['OPS/C1.XHTML'])

    def test_non_utf8_entry_untouched(self):
        make_epub(self.src, [
            ('OPS/c01.xhtml', CHAPTER.format(footer='')),
            ('OPS/c02.xhtml', b'\xff\xfeChapter'),
        ])
        self.assertTrue(clean_epub(self.src, self.dst, [R('Chapter', 'X')], []))
        out = read_all(self.dst)
        self.assertEqual(out['OPS/c02.xhtml'], b'\xff\xfeChapter')
        self.assertIn(b'X text.', out['OPS/c01.xhtml'])

    def test_identical_result_is_no_change(self):
        make_epub(self.src, [('OPS/c01.xhtml', CHAPTER.format(footer=''))])
        self.assertFalse(clean_epub(self.src, self.dst, [R('Chapter', 'Chapter')], []))
        self.assertFalse(os.path.exists(self.dst))

    def test_bad_regex_skipped(self):
        out = self.chapter_after([R('(', regex=True), R('Chapter', 'X')])
        self.assertIn('X text.', out)

    def test_removes_matching_files(self):
        make_epub(self.src, [
            ('a.info', 'x'),
            ('OPS/b.info', 'x'),
            ('OPS/c01.xhtml', CHAPTER.format(footer='')),
        ])
        self.assertTrue(clean_epub(self.src, self.dst, [], ['**/*.info']))
        self.assertEqual(set(read_all(self.dst)), {'mimetype', 'OPS/c01.xhtml'})

    def test_protected_files_never_removed(self):
        make_epub(self.src, [
            ('META-INF/container.xml', CONTAINER),
            ('OPS/content.opf', '<package/>'),
            ('OPS/c01.xhtml', CHAPTER.format(footer='')),
        ])
        self.assertTrue(clean_epub(self.src, self.dst, [], ['**']))
        self.assertEqual(set(read_all(self.dst)),
                         {'mimetype', 'META-INF/container.xml', 'OPS/content.opf'})

    def test_no_rules_no_change(self):
        make_epub(self.src, [('OPS/c01.xhtml', CHAPTER.format(footer=''))])
        self.assertFalse(clean_epub(self.src, self.dst, [], []))
        self.assertFalse(os.path.exists(self.dst))


if __name__ == '__main__':
    unittest.main()
