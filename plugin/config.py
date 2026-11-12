from calibre.utils.config import JSONConfig

prefs = JSONConfig('plugins/epub_scrubber')
prefs.defaults['packs'] = []
prefs.defaults['replacements'] = []
prefs.defaults['remove_files'] = []
