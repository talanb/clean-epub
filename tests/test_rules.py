import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'plugin'))

from rules import PackError, pattern_warning, validate_regex, collect_rules, export_pack, install_pack, parse_pack  # noqa: E402


def rule(find, enabled=True):
    return {'find': find, 'replace': '', 'regex': False, 'ignore_case': False, 'enabled': enabled}


def pack(name, version='', enabled=True, finds=(), patterns=()):
    return {'name': name, 'description': '', 'version': version,
            'replacements': [{'find': f, 'replace': '', 'regex': False, 'ignore_case': False}
                             for f in finds],
            'remove_files': [{'pattern': p} for p in patterns],
            'enabled': enabled}


class ParsePackTest(unittest.TestCase):

    def test_parse_minimal(self):
        self.assertEqual(parse_pack('{"name": "X"}'), {
            'name': 'X', 'description': '', 'version': '', 'replacements': [], 'remove_files': []})

    def test_parse_normalizes_rules(self):
        parsed = parse_pack('{"name": "X", "replacements": [{"find": "a", "enabled": false}], '
                            '"remove_files": [{"pattern": "**/x", "enabled": false}], "extra": 1}')
        self.assertEqual(parsed['replacements'],
                         [{'find': 'a', 'replace': '', 'regex': False, 'ignore_case': False}])
        self.assertEqual(parsed['remove_files'], [{'pattern': '**/x'}])
        self.assertNotIn('extra', parsed)

    def test_parse_errors(self):
        bad = [
            'not json',
            '[]',
            '"x"',
            '{}',
            '{"name": ""}',
            '{"name": "   "}',
            '{"name": "X", "replacements": {}}',
            '{"name": "X", "replacements": ["a"]}',
            '{"name": "X", "replacements": [{"find": ""}]}',
            '{"name": "X", "replacements": [{"find": "a", "replace": 1}]}',
            '{"name": "X", "replacements": [{"find": "a", "regex": "yes"}]}',
            '{"name": "X", "replacements": [{"find": "(", "regex": true}]}',
            '{"name": "X", "replacements": [{"find": "a", "replace": "\\\\1", "regex": true}]}',
            '{"name": "X", "remove_files": [{"pattern": 3}]}',
        ]
        for text in bad:
            with self.assertRaises(PackError, msg=text):
                parse_pack(text)


class ValidateRegexTest(unittest.TestCase):

    def test_bad_template_rejected(self):
        self.assertIsNotNone(validate_regex('a', False, r'\1'))
        self.assertIsNotNone(validate_regex('(a)', False, r'\g<x>'))
        self.assertIsNone(validate_regex('(a)', False, r'\1'))


class PatternWarningTest(unittest.TestCase):

    def test_leading_slash_warns(self):
        for pattern in ('/marker.txt', './marker.txt', '/**/*.info'):
            self.assertIsNotNone(pattern_warning(pattern), pattern)

    def test_normal_patterns_do_not_warn(self):
        for pattern in ('marker.txt', '**/*.info', 'OPS/a.info', '.hidden'):
            self.assertIsNone(pattern_warning(pattern), pattern)


class InstallExportTest(unittest.TestCase):

    def test_install_appends_enabled(self):
        new = parse_pack('{"name": "A"}')
        self.assertEqual(install_pack([], new), [dict(new, enabled=True)])

    def test_install_replaces_in_place_keeping_enabled(self):
        packs = [pack('A', enabled=False), pack('B')]
        installed = install_pack(packs, parse_pack('{"name": "A", "version": "2"}'))
        self.assertEqual([(p['name'], p['version'], p['enabled']) for p in installed],
                         [('A', '2', False), ('B', '', True)])

    def test_export_skips_disabled(self):
        exported = export_pack('Mine', [rule('a'), rule('b', enabled=False)],
                               [{'pattern': 'x', 'enabled': False}, {'pattern': 'y'}])
        self.assertEqual(exported, {
            'name': 'Mine', 'description': '', 'version': '',
            'replacements': [{'find': 'a', 'replace': '', 'regex': False, 'ignore_case': False}],
            'remove_files': [{'pattern': 'y'}]})


class CollectRulesTest(unittest.TestCase):

    def test_collect_order_and_filters(self):
        prefs = {
            'packs': [pack('Off', enabled=False, finds=['off'], patterns=['off']),
                      pack('On', finds=['pack'], patterns=['pack'])],
            'replacements': [rule('mine'), rule('mine-off', enabled=False)],
            'remove_files': [{'pattern': 'mine', 'enabled': True},
                             {'pattern': 'mine-off', 'enabled': False}],
        }
        replacements, patterns = collect_rules(prefs)
        self.assertEqual([r['find'] for r in replacements], ['pack', 'mine'])
        self.assertEqual(patterns, ['pack', 'mine'])

    def test_collect_empty_prefs(self):
        self.assertEqual(collect_rules({}), ([], []))


if __name__ == '__main__':
    unittest.main()
