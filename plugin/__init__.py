import traceback

from calibre.customize import FileTypePlugin


class CleanOcean(FileTypePlugin):

    name = 'Clean Ocean'
    description = 'Removes OceanofPDF.com branding from EPUB files as they are added to the library.'
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Todd Breiholz'
    version = (1, 0, 0)
    minimum_calibre_version = (5, 0, 0)
    file_types = {'epub'}
    on_import = True

    def run(self, path_to_ebook):
        from calibre_plugins.clean_ocean.cleaner import clean_epub

        out = self.temporary_file('.epub')
        out.close()
        try:
            if clean_epub(path_to_ebook, out.name):
                print('Clean Ocean: removed OceanofPDF branding from', path_to_ebook)
                return out.name
        except Exception:
            # Never lose a book: fall back to importing the original
            traceback.print_exc()
        return path_to_ebook
