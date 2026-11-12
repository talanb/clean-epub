"""Package the plugin into dist/epub_scrubber.zip for calibre."""

import os
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'plugin')
DIST = os.path.join(ROOT, 'dist')
FILES = ['__init__.py', 'cleaner.py', 'rules.py', 'config.py',
         'plugin-import-name-epub_scrubber.txt']


def main():
    os.makedirs(DIST, exist_ok=True)
    target = os.path.join(DIST, 'epub_scrubber.zip')
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name in FILES:
            zf.write(os.path.join(SRC, name), name)
    print(target)


if __name__ == '__main__':
    main()
