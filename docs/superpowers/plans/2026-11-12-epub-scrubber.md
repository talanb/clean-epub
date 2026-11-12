# EPUB Scrubber Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the hardcoded "Clean Ocean" calibre plugin into "EPUB Scrubber", driven by user rules and installable packs.

**Architecture:** `cleaner.py` becomes a generic, calibre-free EPUB rewriter (replacement rules + glob file removal). A new calibre-free `rules.py` handles pack parsing/validation, install/export, and assembling the active rule list from prefs. `config.py` holds the calibre prefs and Qt preferences widget; `__init__.py` wires it together on import.

**Tech Stack:** Python 3 stdlib (`zipfile`, `re`, `json`, `xml.etree`), calibre plugin API (`FileTypePlugin`, `JSONConfig`, `qt.core`), `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-12-epub-scrubber-design.md`

## Global Constraints

- Plugin name `EPUB Scrubber`; class `EpubScrubber`; import name `epub_scrubber`; version `(2, 0, 0)`; `minimum_calibre_version = (5, 13, 0)` (first with `qt.core`).
- Prefs: `JSONConfig('plugins/epub_scrubber')`, defaults `{'packs': [], 'replacements': [], 'remove_files': []}`.
- `cleaner.py` and `rules.py` import nothing from calibre or Qt; tests run with plain Python.
- Replacement rules apply only to entries ending `.xhtml`/`.html`/`.htm` (case-insensitive), decoded UTF-8; undecodable entries untouched.
- Never removable: `mimetype`, `META-INF/container.xml`, and every rootfile `full-path` in `container.xml`.
- Output EPUB: `mimetype` first and `ZIP_STORED`; all else `ZIP_DEFLATED`; original `date_time` and `external_attr` kept.
- Any exception during import → traceback printed, original path returned.
- Pack OceanofPDF ships at `packs/oceanofpdf.json` only — NOT in the plugin zip, not pre-installed.
- Test command: `python3 -m unittest discover -s tests -v` (run from repo root).

## Review Focus

1. Fresh install / empty prefs → `collect_rules({})` returns `([], [])` and the book imports untouched (test in Task 3).
2. A pack file that is not JSON, or is a JSON array/string → `PackError` with a readable message, not a crash (Task 3).
3. A replacement that matches but leaves text identical (e.g. `find == replace`) → not counted as a change; book untouched (Task 2).
4. Malformed or missing `META-INF/container.xml` → cleaning still runs; only `mimetype` and `container.xml` path are protected (Task 1).
5. Upper-case content extensions (`CH1.XHTML`) still get replacements (Task 2).

---

### Task 1: Glob matching and protected files

**Files:**
- Modify: `plugin/cleaner.py`
- Test: `tests/test_glob.py` (new)

**Interfaces:**
- Produces: `glob_to_regex(pattern: str) -> re.Pattern` (full-match regex); `protected_paths(container_xml: bytes | None) -> set[str]`.

- [ ] **Step 1: Write failing tests** in `tests/test_glob.py` (same `sys.path` insert as `tests/test_cleaner.py`), helper `m(p, path) = bool(glob_to_regex(p).fullmatch(path))`:
  - `test_double_star_any_depth`: `m('**/oceanofpdf.com', x)` True for `'oceanofpdf.com'`, `'OPS/oceanofpdf.com'`, `'a/b/oceanofpdf.com'`; False for `'OPS/xoceanofpdf.com'`.
  - `test_double_star_extension`: `m('**/*.info', ...)` True for `'a.info'`, `'OPS/x/a.info'`; False for `'a.info.bak'`.
  - `test_root_only`: `m('oceanofpdf.com', 'OPS/oceanofpdf.com')` False; `m('oceanofpdf.com', 'oceanofpdf.com')` True.
  - `test_star_does_not_cross_slash`: `m('*.info', 'OPS/a.info')` False; `m('OPS/*.info', 'OPS/a.info')` True.
  - `test_question_and_literals`: `m('a?.html', 'ab.html')` True; `m('a.html', 'aXhtml')` False (dot is literal).
  - `test_trailing_double_star`: `m('OPS/**', 'OPS/a/b.css')` True.
  - `test_case_sensitive`: `m('**/*.INFO', 'a.info')` False.
  - `test_protected_paths_reads_rootfiles`: container with `<rootfile full-path="OEBPS/content.opf" .../>` (namespace `urn:oasis:names:tc:opendocument:xmlns:container`) → `{'mimetype', 'META-INF/container.xml', 'OEBPS/content.opf'}`.
  - `test_protected_paths_bad_xml`: `protected_paths(b'<not xml')` and `protected_paths(None)` → `{'mimetype', 'META-INF/container.xml'}`.

- [ ] **Step 2: Run** `python3 -m unittest tests.test_glob -v` — expect ImportError on `glob_to_regex`.

- [ ] **Step 3: Implement** both functions in `plugin/cleaner.py`. Glob translation, scanning left to right: `**/` → `(?:.*/)?`; `**` (not followed by `/`) → `.*`; `*` → `[^/]*`; `?` → `[^/]`; any other char → `re.escape(ch)`. Compile without flags. `protected_paths` parses with `xml.etree.ElementTree`, collects `full-path` of every element whose tag ends in `rootfile`; any parse error → base set only.

- [ ] **Step 4: Run** `python3 -m unittest tests.test_glob -v` — all PASS.

- [ ] **Step 5: Commit** `git add plugin/cleaner.py tests/test_glob.py && git commit -m "Add glob matching and protected EPUB paths"`

### Task 2: Generic `clean_epub`

**Files:**
- Modify: `plugin/cleaner.py` (remove `MARKER_FILE`, `FOOTER_RE`; rewrite `_clean_content`, `clean_epub`; update module docstring to describe generic scrubbing)
- Test: `tests/test_cleaner.py` (rewrite generic tests; the OceanofPDF parity tests move to Task 3)

**Interfaces:**
- Consumes: `glob_to_regex`, `protected_paths` (Task 1).
- Produces: `clean_epub(src_path: str, dst_path: str, replacements: list[dict], remove_patterns: list[str]) -> bool`. Each replacement dict has `find: str`, `replace: str`, `regex: bool`, `ignore_case: bool` (missing keys default `''`/`False`). Returns True and writes `dst_path` iff any entry was removed or any entry's bytes changed; otherwise returns False and does not write `dst_path`.

- [ ] **Step 1: Rewrite `tests/test_cleaner.py`** keeping `make_epub`, `read_all`, `CHAPTER`, setUp/tearDown, and `test_mimetype_stays_first_and_stored`; drop the OceanofPDF-specific tests and `SAMPLE`/`FOOTER` (moved to Task 3). Add, using `R(find, replace='', regex=False, ignore_case=False)` dict helper:
  - `test_literal_replacement`: `R('Chapter text.', 'Body.')` → chapter contains `<p>Body.</p>`; returns True.
  - `test_literal_is_not_regex`: `R('a.c')` on text `abc a.c` → `abc ` (only literal removed).
  - `test_literal_replace_has_no_backrefs`: `R('x', r'\1')` → output contains `\1` literally.
  - `test_regex_with_backref`: `R(r'<p>(\w+) text\.</p>', r'<p>\1!</p>', regex=True)` → `<p>Chapter!</p>`.
  - `test_ignore_case`: `R('CHAPTER', 'Ch', ignore_case=True)` → `Ch text.`; same rule without `ignore_case` → returns False.
  - `test_rules_apply_in_order`: `[R('Chapter', 'X'), R('X text', 'Y')]` → `<p>Y.</p>`.
  - `test_only_html_entries_touched`: rule `R('p')` leaves `OPS/style.css` (`p { margin: 0 }`) identical; `OPS/C1.XHTML` (upper case) is changed (Review Focus 5).
  - `test_non_utf8_entry_untouched`: `OPS/c02.xhtml` containing `b'\xff\xfeChapter'` stays byte-identical while `c01.xhtml` is changed.
  - `test_identical_result_is_no_change`: `R('Chapter', 'Chapter')` → returns False, `dst` not written (Review Focus 3).
  - `test_bad_regex_skipped`: `[R('(', regex=True), R('Chapter', 'X')]` → returns True, `X text.` present, no exception.
  - `test_removes_matching_files`: `remove_patterns=['**/*.info']` with `a.info`, `OPS/b.info`, `OPS/c01.xhtml` → `.info` entries gone, chapter kept.
  - `test_protected_files_never_removed`: valid `META-INF/container.xml` pointing at `OPS/content.opf`; `remove_patterns=['**']` → output keeps `mimetype`, `META-INF/container.xml`, `OPS/content.opf`; drops the chapter.
  - `test_no_rules_no_change`: `clean_epub(src, dst, [], [])` → False, `dst` not written.

- [ ] **Step 2: Run** `python3 -m unittest tests.test_cleaner -v` — expect failures (TypeError on new signature).

- [ ] **Step 3: Implement** in `plugin/cleaner.py`: compile replacements once per call — literal rules use `re.escape(find)` with a function replacement returning `replace` verbatim; regex rules use `replace` as a template; `re.IGNORECASE` when `ignore_case`. A rule whose regex fails to compile prints `EPUB Scrubber: skipping invalid regex <find!r>: <error>` and is dropped. Read `META-INF/container.xml` (if present) for `protected_paths`. An entry is removed if it matches any `glob_to_regex(p)` and is not protected. Keep the existing output-writing block unchanged.

- [ ] **Step 4: Run** `python3 -m unittest tests.test_cleaner tests.test_glob -v` — all PASS.

- [ ] **Step 5: Commit** `git add plugin/cleaner.py tests/test_cleaner.py && git commit -m "Make clean_epub rule-driven"`

### Task 3: Packs, rule assembly, and the OceanofPDF pack

**Files:**
- Create: `plugin/rules.py`, `packs/oceanofpdf.json`
- Test: `tests/test_rules.py` (new), `tests/test_oceanofpdf_pack.py` (new; parity tests moved from old `test_cleaner.py`)

**Interfaces:**
- Consumes: `clean_epub` (Task 2) in the pack test.
- Produces (all in `plugin/rules.py`):
  - `class PackError(ValueError)`.
  - `parse_pack(text: str) -> dict` → normalized `{'name': str, 'description': str, 'version': str, 'replacements': [{'find','replace','regex','ignore_case'}], 'remove_files': [{'pattern'}]}`; any `enabled` keys dropped; unknown keys dropped; raises `PackError` on: invalid JSON, top level not an object, missing/empty/non-string `name`, a list field not a list, a rule not an object, empty/non-string `find` or `pattern`, non-string `replace`, non-bool `regex`/`ignore_case`, or a regex rule that fails `re.compile` (message names the rule's `find`).
  - `validate_regex(find: str, ignore_case: bool) -> str | None` → error text or None (shared with the UI editor).
  - `install_pack(packs: list[dict], pack: dict) -> list[dict]` → new list; stored entry is `pack` plus `'enabled'`; same `name` replaces in place keeping its `enabled` and position; otherwise appended with `enabled=True`.
  - `export_pack(name: str, replacements: list[dict], remove_files: list[dict]) -> dict` → pack dict (same shape as `parse_pack` output, `description`/`version` `''`) containing only rules with `enabled` true (missing `enabled` = true), with `enabled` stripped.
  - `collect_rules(prefs: Mapping) -> tuple[list[dict], list[str]]` → enabled packs' rules in list order, then the user's enabled `replacements`; second element is the patterns of the matching `remove_files`. Missing keys treated as empty.

- [ ] **Step 1: Write `tests/test_rules.py`:**
  - `test_parse_minimal`: `parse_pack('{"name": "X"}')` == `{'name': 'X', 'description': '', 'version': '', 'replacements': [], 'remove_files': []}`.
  - `test_parse_normalizes_rules`: `{"find": "a"}` → `{'find': 'a', 'replace': '', 'regex': False, 'ignore_case': False}`; `{"pattern": "**/x", "enabled": false}` → `{'pattern': '**/x'}`.
  - `test_parse_errors`: each of `'not json'`, `'[]'`, `'"x"'`, `'{}'`, `'{"name": ""}'`, `'{"name": "X", "replacements": {}}'`, `'{"name": "X", "replacements": [{"find": ""}]}'`, `'{"name": "X", "replacements": [{"find": "(", "regex": true}]}'`, `'{"name": "X", "remove_files": [{"pattern": 3}]}'` raises `PackError` (Review Focus 2).
  - `test_install_appends_enabled`, `test_install_replaces_in_place_keeping_enabled` (existing `[A(enabled False), B]`, install new A with version `'2'` → `[A v2 enabled False, B]`).
  - `test_export_skips_disabled`: one enabled and one `enabled: False` replacement → only the enabled one, without `enabled` key.
  - `test_collect_order_and_filters`: disabled pack's rules absent; enabled pack rules precede user rules; disabled user rules absent; remove patterns likewise.
  - `test_collect_empty_prefs`: `collect_rules({}) == ([], [])` (Review Focus 1).

- [ ] **Step 2: Run** `python3 -m unittest tests.test_rules -v` — expect ImportError.

- [ ] **Step 3: Implement `plugin/rules.py`.**

- [ ] **Step 4: Run** `python3 -m unittest tests.test_rules -v` — PASS.

- [ ] **Step 5: Create `packs/oceanofpdf.json`** by generating it with `json.dumps(..., indent=2)` (avoids hand-escaping) from: name `OceanofPDF`, description `Removes OceanofPDF.com footers and marker file.`, version `1.0.0`, one replacement with `regex: true`, `ignore_case: true`, `replace: ""`, and `find` exactly:
  ```
  <div\b[^>]*>\s*<p\b[^>]*>\s*<a\b[^>]*href\s*=\s*["']https?://(?:www\.)?oceanofpdf\.com/?["'][^>]*>\s*<i\b[^>]*>\s*OceanofPDF\.com\s*</i>\s*</a>\s*</p>\s*</div>
  ```
  and `remove_files: [{"pattern": "**/oceanofpdf.com"}]`.

- [ ] **Step 6: Write `tests/test_oceanofpdf_pack.py`:** loads the pack via `parse_pack`, gets rules via `collect_rules({'packs': [dict(pack, enabled=True)]})`, and ports the old tests verbatim in intent: `test_removes_footer_and_root_marker`, `test_tolerates_small_footer_variations`, `test_leaves_other_links_alone`, `test_clean_epub_is_untouched`, `test_sample_book` (skip if sample absent; same assertions as before). Add `test_removes_nested_marker`: `OPS/oceanofpdf.com` is removed.

- [ ] **Step 7: Run** `python3 -m unittest discover -s tests -v` — all PASS (sample test runs if the epub is present locally).

- [ ] **Step 8: Commit** `git add plugin/rules.py packs/ tests/test_rules.py tests/test_oceanofpdf_pack.py && git commit -m "Add packs and the OceanofPDF pack"`

### Task 4: Rename and wire up the plugin

**Files:**
- Modify: `plugin/__init__.py`, `build.py`
- Rename: `plugin/plugin-import-name-clean_ocean.txt` → `plugin/plugin-import-name-epub_scrubber.txt` (`git mv`)
- Create: `plugin/config.py` (prefs only in this task; widget in Task 5)

**Interfaces:**
- Consumes: `collect_rules` (Task 3), `clean_epub` (Task 2).
- Produces: `config.prefs` (the `JSONConfig` with defaults from Global Constraints); `EpubScrubber.config_widget()` returns `config.ConfigWidget()`, `EpubScrubber.save_settings(w)` calls `w.save_settings()` — both referencing Task 5's class.

- [ ] **Step 1:** `plugin/config.py`: `prefs = JSONConfig('plugins/epub_scrubber')` with `prefs.defaults[...]` for the three keys.

- [ ] **Step 2:** `plugin/__init__.py`: class `EpubScrubber`, name/version/min version per Global Constraints, description `Removes unwanted text and files from EPUB files as they are added to the library, using your own rules or installed packs.`; `run` imports from `calibre_plugins.epub_scrubber`, calls `collect_rules(prefs)`, returns the original path immediately if both lists are empty, else calls `clean_epub`; keeps the try/except fallback; log line `EPUB Scrubber: cleaned <path>`. Add `is_customizable(self): return True`, `config_widget`, `save_settings` (lazy-import `config`).

- [ ] **Step 3:** `build.py`: `FILES = ['__init__.py', 'cleaner.py', 'rules.py', 'config.py', 'plugin-import-name-epub_scrubber.txt']`, target `dist/epub_scrubber.zip`, docstring updated.

- [ ] **Step 4: Verify** `python3 build.py` prints `.../dist/epub_scrubber.zip`, and `python3 -c "import zipfile;print(zipfile.ZipFile('dist/epub_scrubber.zip').namelist())"` lists exactly the five files (no `packs/`). `python3 -m unittest discover -s tests -v` still PASS.

- [ ] **Step 5: Commit** `git add -A plugin build.py && git commit -m "Rename plugin to EPUB Scrubber"`

### Task 5: Preferences UI

**Files:**
- Modify: `plugin/config.py`

**Interfaces:**
- Consumes: `prefs` (Task 4); `parse_pack`, `PackError`, `install_pack`, `export_pack`, `validate_regex` (Task 3).
- Produces: `class ConfigWidget(QWidget)` with `save_settings(self) -> None` writing `packs`, `replacements`, `remove_files` back to `prefs`.

All Qt from `qt.core`. Widget edits a working copy of prefs; nothing is persisted until `save_settings`. Layout per spec "Preferences UI":

- [ ] **Step 1: Packs section** — list (checkable items: `name version — description`), buttons *Install pack…* (`QFileDialog.getOpenFileName`, filter `Pack files (*.json)`; read UTF-8; `parse_pack`; on `PackError`/`OSError`/`UnicodeDecodeError` show `QMessageBox.warning` with the message and change nothing; if the name already exists, `QMessageBox.question` "Replace installed pack '<name>'?" before `install_pack`), *Remove* (confirm), *View rules* (read-only dialog listing the pack's replacements and file patterns).

- [ ] **Step 2: My replacements** — `QTableWidget` columns Enabled / Find / Replace / Regex / Ignore case (checkbox cells for bools), buttons Add / Edit / Delete / Move up / Move down. Add/Edit open a small dialog (find, replace, two checkboxes); OK is refused with an inline error when `find` is empty or `validate_regex` returns an error for a regex rule.

- [ ] **Step 3: My file removals** — table Enabled / Pattern, Add / Edit / Delete; empty pattern refused.

- [ ] **Step 4: Export my rules…** — prompt for name (`QInputDialog.getText`, non-empty), `QFileDialog.getSaveFileName` default `<name>.json`, write `json.dumps(export_pack(...), indent=2)` UTF-8.

- [ ] **Step 5: Manual verification in calibre** (`python3 build.py && calibre-customize -a dist/epub_scrubber.zip`, restart calibre). Check, in order:
  1. Preferences → Plugins → EPUB Scrubber → Customize opens with three empty sections.
  2. Install `packs/oceanofpdf.json`; it appears enabled; *View rules* shows the regex and `**/oceanofpdf.com`.
  3. Installing a file containing `[]` shows an error and installs nothing.
  4. Adding an OceanofPDF sample book removes the footers and marker file (open it in the viewer / check with `unzip -l`).
  5. Disable the pack, add the sample again → book unchanged.
  6. Add a user regex rule `(` → editor refuses it.
  7. Add a user literal rule and a `**/*.info` removal, export, reinstall the export as a pack → rules match.
  8. Cancel the dialog after changes → reopening shows the old state.

- [ ] **Step 6: Commit** `git add plugin/config.py && git commit -m "Add EPUB Scrubber preferences UI"`
