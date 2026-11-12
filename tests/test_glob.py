import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'plugin'))

from cleaner import glob_to_regex, protected_paths  # noqa: E402

BASE = {'mimetype', 'META-INF/container.xml'}

CONTAINER = (b'<?xml version="1.0"?>\n'
             b'<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
             b'<rootfiles><rootfile full-path="OEBPS/content.opf" '
             b'media-type="application/oebps-package+xml"/></rootfiles></container>')


def m(pattern, path):
    return bool(glob_to_regex(pattern).fullmatch(path))


class GlobTest(unittest.TestCase):

    def test_double_star_any_depth(self):
        for path in ('oceanofpdf.com', 'OPS/oceanofpdf.com', 'a/b/oceanofpdf.com'):
            self.assertTrue(m('**/oceanofpdf.com', path), path)
        self.assertFalse(m('**/oceanofpdf.com', 'OPS/xoceanofpdf.com'))

    def test_double_star_extension(self):
        self.assertTrue(m('**/*.info', 'a.info'))
        self.assertTrue(m('**/*.info', 'OPS/x/a.info'))
        self.assertFalse(m('**/*.info', 'a.info.bak'))

    def test_root_only(self):
        self.assertFalse(m('oceanofpdf.com', 'OPS/oceanofpdf.com'))
        self.assertTrue(m('oceanofpdf.com', 'oceanofpdf.com'))

    def test_star_does_not_cross_slash(self):
        self.assertFalse(m('*.info', 'OPS/a.info'))
        self.assertTrue(m('OPS/*.info', 'OPS/a.info'))

    def test_question_and_literals(self):
        self.assertTrue(m('a?.html', 'ab.html'))
        self.assertFalse(m('a.html', 'aXhtml'))

    def test_trailing_double_star(self):
        self.assertTrue(m('OPS/**', 'OPS/a/b.css'))

    def test_case_sensitive(self):
        self.assertFalse(m('**/*.INFO', 'a.info'))


class ProtectedPathsTest(unittest.TestCase):

    def test_protected_paths_reads_rootfiles(self):
        self.assertEqual(protected_paths(CONTAINER), BASE | {'OEBPS/content.opf'})

    def test_protected_paths_bad_xml(self):
        self.assertEqual(protected_paths(b'<not xml'), BASE)
        self.assertEqual(protected_paths(None), BASE)


if __name__ == '__main__':
    unittest.main()
