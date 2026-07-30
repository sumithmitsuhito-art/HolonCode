"""Build-time hook: collect all Pygments lexers, formatters, styles and filters.

The application references Pygments components through dynamic dispatch:
- HtmlFormatter(style="friendly") loads a style by name
- get_lexer_by_name(lang) / get_lexer_for_filename(path) load lexers by name
- guess_lexer(code) walks registered lexers

Without this hook, PyInstaller may miss submodules that are never
statically imported, resulting in code blocks rendering without
syntax highlighting on target machines.
"""
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = []
hiddenimports += collect_submodules('pygments.lexers')
hiddenimports += collect_submodules('pygments.formatters')
hiddenimports += collect_submodules('pygments.styles')
hiddenimports += collect_submodules('pygments.filters')

datas = collect_data_files('pygments')
