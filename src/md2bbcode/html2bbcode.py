# converts HTML to BBCode; the command is handled in main.py.
from typing import Optional

from mistune.core import BlockState

from md2bbcode.renderers.bbcode import BBCodeRenderer


def html_to_bbcode(
    html: str,
    domain: Optional[str] = None,
    link_base: Optional[str] = None,
    image_base: Optional[str] = None,
    dialect=None,
) -> str:
    """Convert an HTML document or fragment to BBCode."""
    renderer = BBCodeRenderer(domain=domain, link_base=link_base, image_base=image_base, dialect=dialect)
    # Treat the whole input as HTML, not Markdown.
    bbcode = renderer([{"type": "block_html", "raw": html}], BlockState())
    return bbcode.rstrip("\n")


def process_html(
    input_html: str,
    debug: bool = False,
    output_file: Optional[str] = None,
    domain: Optional[str] = None,
    link_base: Optional[str] = None,
    image_base: Optional[str] = None,
    dialect=None,
) -> str:
    converted_bbcode = html_to_bbcode(input_html, domain=domain, link_base=link_base, image_base=image_base, dialect=dialect)

    if debug:
        if output_file is None:
            output_file = "readme.finalpass"
        with open(output_file, "w", encoding="utf-8") as file:
            file.write(converted_bbcode)
    return converted_bbcode
