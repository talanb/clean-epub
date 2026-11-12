# EPUB Scrubber

A [calibre](https://calibre-ebook.com) plugin that cleans EPUB files as they are
added to your library. It removes unwanted text (watermarks, footers, promo
links) and unwanted files using rules you define yourself or install as
**packs**.

- **Replacement rules** find text in the book's HTML/XHTML pages and replace
  it, usually with nothing. A rule can be plain text or a regular expression.
- **File-removal rules** drop files from the EPUB by path pattern, at any
  folder depth (`**/*.info`).
- **Packs** are shareable JSON files with a set of rules for one job. The repo
  includes a pack for OceanofPDF.com branding.

Books with nothing to clean are imported untouched. If anything goes wrong
while cleaning, the original book is imported, so a book is never lost.

## Installation

Requires calibre 5.13 or later.

1. Download `epub_scrubber.zip` from the
   [latest release](https://github.com/talanb/clean-epub/releases/latest).
   Don't unzip it; calibre loads the zip as is.

2. In calibre, open **Preferences → Plugins → Load plugin from file**, choose
   `epub_scrubber.zip`, and restart calibre.

   Or, from the command line:

   ```sh
   calibre-customize -a epub_scrubber.zip
   ```

   On macOS, `calibre-customize` is in `/Applications/calibre.app/Contents/MacOS/`.

To upgrade, install the newer zip the same way; it replaces the old version and
keeps your settings.

The plugin starts with no rules, so it does nothing until you add rules or
install a pack.

### Building from source

To install the current code instead of a release, build the zip yourself:

```sh
python3 build.py
```

This writes `dist/epub_scrubber.zip`, which you install as above.

## Usage

Open **Preferences → Plugins**, find **EPUB Scrubber** under *File type
plugins*, and click **Customize plugin**. Changes take effect when you click OK;
Cancel discards them.

The rules apply to EPUBs you add from then on. Books already in your library
are not changed.

### Packs

- **Install pack…** opens a file picker. Choose a pack `.json` file. The pack is
  checked first; if anything is wrong, you get the reason and nothing is
  installed. The pack is copied into calibre's settings, so you can delete the
  file afterwards.
- Installing a pack with the same name as an installed one replaces it, after
  asking you first. The pack stays switched on or off as it was.
- The checkbox next to a pack turns all of its rules on or off.
- **View rules** shows what a pack does. Packs can't be edited here; to change
  one, edit its JSON file and install it again.
- **Remove** uninstalls the selected pack.

To get the OceanofPDF cleaning, download
[`packs/oceanofpdf.json`](https://raw.githubusercontent.com/talanb/clean-epub/main/packs/oceanofpdf.json)
from this repo (use your browser's Save As) and install it.
It removes the OceanofPDF.com footer from every page and the `oceanofpdf.com`
marker file.

### My replacements

Your own text replacements. Each rule has:

| Field | Meaning |
|-------|---------|
| Find | The text to look for. Required. |
| Replace with | What to put in its place. Leave empty to delete the text. |
| Regular expression | Treat *Find* as a Python regular expression. *Replace with* can then use `\1` or `\g<name>` to insert matched groups. |
| Ignore case | Match regardless of upper or lower case. |

Use **Add**, **Edit** (or double-click a row), **Delete**, and **Move up** /
**Move down** to manage them. The *Enabled* checkbox turns a single rule on or
off.

Notes:

- Replacements apply only to the book's `.xhtml`, `.html`, and `.htm` pages.
  CSS, the OPF file, and other files are not touched.
- Rules run in order, each one working on the result of the one before.
- An invalid regular expression or replacement (for example, `\1` when the
  expression has no group) can't be saved.
- Replacements work on the raw HTML, so a rule that removes part of a tag can
  leave broken markup. Matching whole elements is safest.

### My file removals

Patterns for files to remove from the book. Patterns match the file's path
inside the EPUB, such as `OPS/images/cover.jpg`.

| Pattern | Matches |
|---------|---------|
| `marker.txt` | That file at the top level of the book only |
| `**/marker.txt` | That file in any folder, including the top level |
| `**/*.info` | Every `.info` file, in any folder |
| `OPS/*.info` | `.info` files directly inside `OPS/` (not in subfolders) |
| `OPS/**` | Everything under `OPS/` |

- `*` matches any characters within one folder name, `?` matches one
  character, and `**/` matches any number of folders.
- Matching is case-sensitive.
- Paths inside a book never start with `/` or `./`. A pattern that does will
  never match, and the plugin warns you about it.

Some files are never removed, even if a pattern matches them, because the book
can't be opened without them: `mimetype`, `META-INF/container.xml`, and the
book's OPF package file.

Removing a file doesn't update the book's table of contents or file list. Only
remove files that nothing else in the book needs, such as watermark files.

### Order of rules

On each import, rules from switched-on packs run first, in the order the packs
were installed. Your own switched-on rules run after them.

### Sharing your rules

**Export my rules…** saves your switched-on replacements and file removals as a
pack file. It asks for a name and a place to save it. Disabled rules are left
out, because packs have no per-rule on/off switch and a disabled rule would
become active when the pack is installed.

## Pack format

A pack is a UTF-8 JSON file:

```json
{
  "name": "Example",
  "description": "What this pack cleans.",
  "version": "1.0.0",
  "replacements": [
    {"find": "Downloaded from example.com", "replace": ""},
    {"find": "<p class=\"promo\">.*?</p>", "replace": "", "regex": true, "ignore_case": true}
  ],
  "remove_files": [
    {"pattern": "**/example.txt"}
  ]
}
```

| Key | Required | Notes |
|-----|----------|-------|
| `name` | yes | Identifies the pack. Installing another pack with the same name replaces it. |
| `description`, `version` | no | Shown in the pack list. |
| `replacements` | no | List of rules. Each has `find` (required); `replace`, `regex`, and `ignore_case` are optional (defaults: `""`, `false`, `false`). |
| `remove_files` | no | List of `{"pattern": "..."}`. |

Remember that backslashes in JSON strings must be doubled: the regular
expression `\s+` is written `"\\s+"`.

## Troubleshooting

To see what the plugin did, start calibre in debug mode (**Preferences →
Restart in debug mode**, or `calibre-debug -g`) and add a book. Each cleaned book
logs `EPUB Scrubber: cleaned <path>`. Errors and skipped rules are logged too.

## Development

```text
plugin/
  __init__.py   calibre plugin class; runs the rules on import
  cleaner.py    rewrites the EPUB (no calibre imports)
  rules.py      pack parsing, validation, export, rule assembly (no calibre imports)
  config.py     settings storage and the preferences screen
packs/          packs you can install (not bundled in the plugin)
tests/          unit tests
build.py        builds dist/epub_scrubber.zip
```

Run the tests with plain Python. calibre isn't needed:

```sh
python3 -m unittest discover -s tests -v
```
