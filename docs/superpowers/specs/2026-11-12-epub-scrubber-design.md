# EPUB Scrubber — design

Date: 2026-11-12
Status: approved

## Intent

A calibre plugin that cleans unwanted text and files out of EPUBs as they are
imported. Nothing about a particular source is hardcoded: all cleanup is driven
by rules, entered in the plugin's preferences UI or installed as a "pack" — a
shareable file holding the rules for one use case. New cleanup jobs then need no
code changes.

## Goals

- User-defined **replacement rules**: find → replace, applied to EPUB content.
- User-defined **file-removal rules**: glob patterns for files to drop from the EPUB.
- **Packs**: installable rule sets that stay a separate unit (enable/disable/remove
  as a whole), alongside the user's own rules.
- An example pack, `packs/oceanofpdf.json`, ships in the repo.

## Non-goals

- Touching CSS, OPF, NCX, or other non-HTML content with replacement rules.
- Formats other than EPUB.
- A pack repository, downloads, or auto-update.
- Editing a pack's rules inside the UI.

## Anti-goals

- Losing or corrupting a book. Any failure must import the original unchanged.
- Producing an invalid EPUB (mimetype must stay first and stored).
- Variation-tolerance logic baked into code. All tolerance lives in the rule
  (regex / ignore-case).

## Rules

### Replacement rule

| Field        | Meaning |
|--------------|---------|
| `find`       | Text or regex to find. Required, non-empty. |
| `replace`    | Replacement text. Default `""`. With `regex`, supports Python `re` backreferences (`\1`, `\g<name>`). |
| `regex`      | bool, default false. If false, `find` is literal. |
| `ignore_case`| bool, default false. |
| `enabled`    | bool, default true (only meaningful for the user's own rules). |

Applied to entries whose names end in `.xhtml`, `.html`, `.htm`
(case-insensitive), decoded as UTF-8. Entries that fail to decode are left
unchanged. Rules apply in list order, each to the output of the previous one.

### File-removal rule

| Field     | Meaning |
|-----------|---------|
| `pattern` | Glob matched against the full zip entry path (e.g. `OPS/foo.info`). |
| `enabled` | bool, default true. |

Glob semantics: `*` matches within one path segment, `?` one character,
`**/` matches zero or more leading directories. So `**/marker.txt` matches
`marker.txt` and `OPS/x/marker.txt`; `**/*.info` matches every `.info` file at
any depth; `marker.txt` matches only the root file. Matching is case-sensitive
(zip paths are). Implemented by translating the glob to a regex — `fnmatch`
lets `*` cross `/` and has no `**`.

Zip paths never start with `/` or `./`, so a pattern that does can never match;
the UI warns when one is entered or arrives in an installed pack.

`mimetype`, `META-INF/container.xml`, and the OPF package document(s) named as
rootfiles in `container.xml` are never removed, even if a pattern matches them.
Beyond that, rules are the user's responsibility: removing a file does not
update the OPF manifest/spine, and changed HTML is not re-validated. The
"invalid EPUB" anti-goal means only the zip layout and these protected files.

## Packs

A pack is a UTF-8 JSON file, conventionally `*.json`:

```json
{
  "name": "Example",
  "description": "What this pack cleans.",
  "version": "1.0.0",
  "replacements": [
    {"find": "<p class=\"promo\">.*?</p>", "replace": "", "regex": true, "ignore_case": true}
  ],
  "remove_files": [
    {"pattern": "**/marker.txt"}
  ]
}
```

`name` is required (not blank) and is the pack's identity. `description`,
`version`, `replacements`, `remove_files` are optional (missing lists = empty).
Rule `enabled` flags inside a pack are ignored; packs are on/off as a whole.

- **Install:** "Install pack…" opens a file picker. The file is validated
  (valid JSON, has `name`, rules well-formed, every regex and replacement
  template compiles). On error, show the reason and install nothing. On
  success, the parsed pack is stored in the plugin's prefs, so the source file
  can be deleted afterwards. Installing a pack whose `name` is already installed
  replaces it (after a confirm prompt), keeping its enabled state and position.
- **Manage:** installed packs listed with name, version, description, enabled
  checkbox, Remove button, and a read-only view of their rules.
- **Export:** "Export my rules…" writes the user's own *enabled* rules as a
  pack file (prompts for a name); disabled rules are left out so they can't
  become active on install.
- Packs in the repo's `packs/` folder are not bundled in the plugin zip and
  not pre-installed.

## Preferences UI

Calibre plugin config dialog (`is_customizable` / `config_widget` /
`save_settings`), stored with `calibre.utils.config.JSONConfig`
(`plugins/epub_scrubber`). Layout:

1. **Packs** — list + Install / Remove / View rules, per-pack enabled checkbox.
2. **My replacements** — table (enabled, find, replace, regex, ignore case)
   with Add / Edit / Delete / Move up / Move down.
3. **My file removals** — table (enabled, pattern) with Add / Edit / Delete.
4. **Export my rules…** button.

Regexes and replacement templates are validated when a rule is saved in the
editor; an invalid one can't be saved.

## Import behaviour

On each EPUB import: collect enabled rules from enabled packs (in install
order) followed by the user's enabled rules. Run one pass over the zip:
drop entries matching any removal pattern, apply replacements to HTML entries.
If nothing changed, return the original path (book untouched). If anything
changed, write the cleaned EPUB (mimetype first, stored; everything else
deflated, original dates/attrs preserved). Any exception at any point → log
traceback and import the original. A rule whose regex or replacement template
is invalid at import time is logged and skipped; the remaining rules still run.
An unreadable `container.xml` doesn't stop cleaning; only the always-protected
paths are kept.

## Code structure

- `plugin/cleaner.py` — calibre-free and unit-testable:
  `clean_epub(src, dst, replacements, remove_patterns) -> bool`, plus glob and
  protected-path helpers. No knowledge of any particular source.
- `plugin/rules.py` — calibre-free: pack parsing/validation, install, export,
  and assembling the active rule list from prefs.
- `plugin/__init__.py` — `EpubScrubber(FileTypePlugin)`; loads prefs,
  assembles rules, calls `clean_epub`.
- `plugin/config.py` — prefs and the Qt config widget (`qt.core` imports).
- `packs/oceanofpdf.json` — example pack.
- Import name `epub_scrubber` (`plugin-import-name-epub_scrubber.txt`);
  `build.py` produces `dist/epub_scrubber.zip`.

## Testing

- Unit tests: literal vs regex, ignore-case, rule ordering, backreferences,
  glob matching (`**/x`, `**/*.ext`, root-only, `*` not crossing `/`),
  protected files, pack validation errors, bad regex skipped at import.
- The example pack has its own tests against small generated EPUBs.
- UI tested manually in calibre.

## Left to the builder

Widget specifics and dialog layout details, error-message wording, exact
helper names and module split within the structure above.
