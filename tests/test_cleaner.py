import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'plugin'))

from cleaner import clean_epub  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), '..')
SAMPLE = os.path.join(ROOT, '12_Months_to_Retire_Right_-_Glen_James.epub')

FOOTER = ('<div style="float: none; margin: 10px 0px 10px 0px; text-align: center;">'
          '<p><a href="https://oceanofpdf.com"><i>OceanofPDF.com</i></a></p></div>')

CHAPTER = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<html xmlns="http://www.w3.org/1999/xhtml"><body>\n'
           '<p>Chapter text.</p>\n{footer}</body>\n</html>')


def make_epub(path, entries):
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        for name, data in entries:
            zf.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)


def read_all(path):
    with zipfile.ZipFile(path) as zf:
        return {i.filename: zf.read(i) for i in zf.infolist()}


class CleanEpubTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, 'in.epub')
        self.dst = os.path.join(self.tmp.name, 'out.epub')

    def tearDown(self):
        self.tmp.cleanup()

    def test_removes_footer_and_root_marker(self):
        make_epub(self.src, [
            ('oceanofpdf.com', 'oceanofpdf.com\n'),
            ('OPS/c01.xhtml', CHAPTER.format(footer=FOOTER)),
            ('OPS/style.css', 'p { margin: 0 }'),
        ])
        self.assertTrue(clean_epub(self.src, self.dst))
        out = read_all(self.dst)
        self.assertNotIn('oceanofpdf.com', out)
        self.assertEqual(out['OPS/c01.xhtml'].decode('utf-8'), CHAPTER.format(footer=''))
        self.assertEqual(out['OPS/style.css'], b'p { margin: 0 }')

    def test_mimetype_stays_first_and_stored(self):
        make_epub(self.src, [('OPS/c01.xhtml', CHAPTER.format(footer=FOOTER))])
        clean_epub(self.src, self.dst)
        with zipfile.ZipFile(self.dst) as zf:
            first = zf.infolist()[0]
        self.assertEqual(first.filename, 'mimetype')
        self.assertEqual(first.compress_type, zipfile.ZIP_STORED)

    def test_tolerates_small_footer_variations(self):
        variant = ("<div style='text-align:center'>\n  <p>\n"
                   "<a href='http://www.OceanOfPDF.com/'>  <i>OceanofPDF.com</i></a></p>\n</div>")
        make_epub(self.src, [('OPS/c01.xhtml', CHAPTER.format(footer=variant))])
        self.assertTrue(clean_epub(self.src, self.dst))
        self.assertNotIn(b'oceanofpdf', read_all(self.dst)['OPS/c01.xhtml'].lower())

    def test_leaves_other_links_alone(self):
        other = ('<div style="text-align: center;"><p><a href="https://example.com">'
                 '<i>Example.com</i></a></p></div>')
        make_epub(self.src, [('OPS/c01.xhtml', CHAPTER.format(footer=other))])
        self.assertFalse(clean_epub(self.src, self.dst))

    def test_clean_epub_is_untouched(self):
        make_epub(self.src, [('OPS/c01.xhtml', CHAPTER.format(footer=''))])
        self.assertFalse(clean_epub(self.src, self.dst))
        self.assertFalse(os.path.exists(self.dst))

    @unittest.skipUnless(os.path.exists(SAMPLE), 'sample epub not present')
    def test_sample_book(self):
        self.assertTrue(clean_epub(SAMPLE, self.dst))
        before, after = read_all(SAMPLE), read_all(self.dst)
        self.assertEqual(set(before) - set(after), {'oceanofpdf.com'})
        for name, data in after.items():
            self.assertNotIn(b'oceanofpdf', data.lower(), name)
            if name.endswith('.xhtml'):
                self.assertEqual(data, before[name].replace(FOOTER.encode('utf-8'), b''), name)
            else:
                self.assertEqual(data, before[name], name)


if __name__ == '__main__':
    unittest.main()
