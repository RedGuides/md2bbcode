from md2bbcode.dialect import Dialect, DialectError
from md2bbcode.main import Converter, convert, html_to_bbcode, package_version, process_readme

__version__ = package_version()

__all__ = ["convert", "Converter", "Dialect", "DialectError", "html_to_bbcode", "process_readme", "__version__"]
