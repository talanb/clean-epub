import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'plugin'))

from cleaner import clean_epub  # noqa: E402
from rules import collect_rules, parse_pack  # noqa: E402
from test_cleaner import CHAPTER, make_epub, read_all  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), '..')
PACK = os.path.join(ROOT, 'packs', 'oceanofpdf.json')
SAMPLE = os.path.join(ROOT, '12_Months_to_Retire_Right_-_Glen_James.epub')

FOOTER = ('<div style="float: none; margin: 10px 0px 10px 0px; text-align: center;">'
          '<p><a href="https://oceanofpdf.com"><i>OceanofPDF.com</i></a></p></div>')


def load_rules():
    with open(PACK, encoding='utf-8') as f:
        pack = parse_pack(f.read())
    return collect_rules({'packs': [dict(pack, enabled=True)]})


class OceanofPDFPackTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, 'in.epub')
        self.dst = os.path.join(self.tmp.name, 'out.epub')
        self.replacements, self.patterns = load_rules()

    def tearDown(self):
        self.tmp.cleanup()

    def clean(self, src=None):
        return clean_epub(src or self.src, self.dst, self.replacements, self.patterns)

    def test_removes_footer_and_root_marker(self):
        make_epub(self.src, [
            ('oceanofpdf.com', 'oceanofpdf.com\n'),
            ('OPS/c01.xhtml', CHAPTER.format(footer=FOOTER)),
            ('OPS/style.css', 'p { margin: 0 }'),
        ])
        self.assertTrue(self.clean())
        out = read_all(self.dst)
        self.assertNotIn('oceanofpdf.com', out)
        self.assertEqual(out['OPS/c01.xhtml'].decode('utf-8'), CHAPTER.format(footer=''))
        self.assertEqual(out['OPS/style.css'], b'p { margin: 0 }')

    def test_removes_nested_marker(self):
        make_epub(self.src, [('OPS/oceanofpdf.com', 'x'), ('OPS/c01.xhtml', CHAPTER.format(footer=''))])
        self.assertTrue(self.clean())
        self.assertNotIn('OPS/oceanofpdf.com', read_all(self.dst))

    def test_tolerates_small_footer_variations(self):
        variant = ("<div style='text-align:center'>\n  <p>\n"
                   "<a href='http://www.OceanOfPDF.com/'>  <i>OceanofPDF.com</i></a></p>\n</div>")
        make_epub(self.src, [('OPS/c01.xhtml', CHAPTER.format(footer=variant))])
        self.assertTrue(self.clean())
        self.assertNotIn(b'oceanofpdf', read_all(self.dst)['OPS/c01.xhtml'].lower())

    def test_leaves_other_links_alone(self):
        other = ('<div style="text-align: center;"><p><a href="https://example.com">'
                 '<i>Example.com</i></a></p></div>')
        make_epub(self.src, [('OPS/c01.xhtml', CHAPTER.format(footer=other))])
        self.assertFalse(self.clean())

    def test_clean_epub_is_untouched(self):
        make_epub(self.src, [('OPS/c01.xhtml', CHAPTER.format(footer=''))])
        self.assertFalse(self.clean())
        self.assertFalse(os.path.exists(self.dst))

    @unittest.skipUnless(os.path.exists(SAMPLE), 'sample epub not present')
    def test_sample_book(self):
        self.assertTrue(self.clean(SAMPLE))
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
