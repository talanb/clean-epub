import traceback

from calibre.customize import FileTypePlugin


class EpubScrubber(FileTypePlugin):

    name = 'EPUB Scrubber'
    description = ('Removes unwanted text and files from EPUB files as they are added to the '
                   'library, using your own rules or installed packs.')
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Todd Breiholz'
    version = (1, 0, 0)
    minimum_calibre_version = (5, 13, 0)
    file_types = {'epub'}
    on_import = True

    def run(self, path_to_ebook):
        from calibre_plugins.epub_scrubber.cleaner import clean_epub
        from calibre_plugins.epub_scrubber.config import prefs
        from calibre_plugins.epub_scrubber.rules import collect_rules

        try:
            replacements, remove_patterns = collect_rules(prefs)
            if not replacements and not remove_patterns:
                return path_to_ebook
            out = self.temporary_file('.epub')
            out.close()
            if clean_epub(path_to_ebook, out.name, replacements, remove_patterns):
                print('EPUB Scrubber: cleaned', path_to_ebook)
                return out.name
        except Exception:
            # Never lose a book: fall back to importing the original
            traceback.print_exc()
        return path_to_ebook

    def is_customizable(self):
        return True

    def config_widget(self):
        from calibre_plugins.epub_scrubber.config import ConfigWidget
        return ConfigWidget()

    def save_settings(self, config_widget):
        config_widget.save_settings()
