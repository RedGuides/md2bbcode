from md2bbcode.dialect import Dialect
from md2bbcode.main import package_version, process_readme

__version__ = package_version()

__all__ = ["process_readme", "Dialect", "__version__"]
