from mistune.core import BaseRenderer
from mistune.util import safe_entity
import re
from urllib.parse import urljoin, urlparse

from md2bbcode.dialect import get_dialect
from md2bbcode.image_rewrite import rewrite_svg_url

_HARMFUL_SCHEMES = ('javascript:', 'vbscript:', 'data:')


def resolve_url(url: str, base=None) -> str:
    """Join relative URLs to a base and block unsafe URLs."""
    if url.strip().lower().startswith(_HARMFUL_SCHEMES):
        return '#harmful-link'
    if not base or url.startswith(('#', '//')):
        return url
    try:
        if urlparse(url).scheme:
            return url
        return urljoin(base, url)
    except ValueError:
        # Leave invalid URLs unchanged.
        return url


def resolve_bases(link_base=None, image_base=None, domain=None):
    """Use ``domain`` for missing bases, then share either base if only one is set."""
    link_base = link_base or domain
    image_base = image_base or domain
    return link_base or image_base or None, image_base or link_base or None


class BBCodeRenderer(BaseRenderer):
    """A renderer for converting Markdown to BBCode."""
    NAME = 'bbcode'

    def __init__(self, domain=None, link_base=None, image_base=None, dialect=None):
        super(BBCodeRenderer, self).__init__()
        self.link_base, self.image_base = resolve_bases(link_base, image_base, domain)
        self.dialect = get_dialect(dialect)
        self.tag = self.dialect.render

    def render_token(self, token, state):
        func = self._get_method(token['type'])
        attrs = token.get('attrs')

        if 'raw' in token:
            text = token['raw']
        elif 'children' in token:
            text = self.render_tokens(token['children'], state)
        else:
            if attrs:
                return func(**attrs)
            else:
                return func()
        if attrs:
            return func(text, **attrs)
        else:
            return func(text)

    def text(self, text: str) -> str:
        return text

    def emphasis(self, text: str) -> str:
        return self.tag('emphasis', text=text)

    def strong(self, text: str) -> str:
        return self.tag('strong', text=text)

    def link(self, text: str, url: str, title=None) -> str:
        return self.tag('link', text=text, url=resolve_url(url, self.link_base))

    def image(self, text: str, url: str, title=None) -> str:
        safe_url = resolve_url(url, self.image_base)
        rewritten_url = rewrite_svg_url(safe_url)
        if rewritten_url is None:
            # An SVG we cannot turn into a PNG: link to it instead.
            return self.tag('link', text=text or safe_url, url=safe_url)
        if text:
            img_tag = self.tag('image_alt', url=rewritten_url, alt=text)
        else:
            img_tag = self.tag('image', url=rewritten_url)
        # Check if alt text starts with 'pixel' and treat it as pixel art
        if text and text.lower().startswith('pixel'):
            return self.tag('pixelate', text=img_tag)
        return img_tag

    def codespan(self, text: str) -> str:
        return self.tag('codespan', text=text)

    def linebreak(self) -> str:
        return self.tag('linebreak')

    def softbreak(self) -> str:
        # Keep soft line breaks as spaces; hard breaks still use linebreak().
        return ' '

    def inline_html(self, html: str) -> str:
        # Leave HTML as it is for now. html2bbcode converts it later.
        return html

    def paragraph(self, text: str) -> str:
        return text + self.dialect.paragraph_separator

    def heading(self, text: str, level: int, **attrs) -> str:
        return self.dialect.heading(level, text) + '\n'

    def blank_line(self) -> str:
        return ''

    def thematic_break(self) -> str:
        return self.tag('thematic_break') + '\n'

    def block_text(self, text: str) -> str:
        return text

    def block_code(self, code: str, **attrs) -> str:
        # Code is emitted verbatim; the html2bbcode pass stashes [CODE] blocks
        # before HTML parsing, so escaping here would only leak entities.
        special_cases = {
            'plaintext': None  # Default [CODE]
        }

        bbcode_lang = None
        if 'info' in attrs:
            lang_info = safe_entity(attrs['info'].strip())
            lang = lang_info.split(None, 1)[0].lower()
            # Check if the language needs special handling
            bbcode_lang = special_cases.get(lang, lang)  # Use the special case if it exists, otherwise use lang as is

        if bbcode_lang:
            return self.tag('block_code', text=code, lang=bbcode_lang) + '\n'
        # No language specified, render with a generic [CODE] tag
        return self.tag('block_code_nolang', text=code) + '\n'

    def block_quote(self, text: str) -> str:
        # GFMD "alerts"/admonitions are expressed as a blockquote
        # Render these into a dedicated XenForo custom BBCode, rather than a normal QUOTE.
        m = re.match(r"^\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*", text, flags=re.IGNORECASE)
        if m:
            kind = m.group(1).lower()
            body = text[m.end():].strip()
            return self.tag('admonition', text=body, kind=kind) + '\n'

        return self.tag('block_quote', text=text) + '\n'

    def block_html(self, html: str) -> str:
        return html + '\n'

    def block_error(self, text: str) -> str:
        return self.tag('block_error', text=text) + '\n'

    def list(self, text: str, ordered: bool, **attrs) -> str:
        # For ordered lists, always use [list=1] to get automatic sequential numbering
        # For unordered lists, use [list]
        return self.tag('list_ordered' if ordered else 'list_unordered', text=text) + '\n'

    def list_item(self, text: str) -> str:
        return self.tag('list_item', text=text) + '\n'

    def strikethrough(self, text: str) -> str:
        return self.tag('strikethrough', text=text)

    def mark(self, text: str) -> str:
        return self.tag('mark', text=text)

    def insert(self, text: str) -> str:
        # Use underline to represent insertion
        return self.tag('insert', text=text)

    def superscript(self, text: str) -> str:
        return self.tag('superscript', text=text)

    def subscript(self, text: str) -> str:
        return self.tag('subscript', text=text)

    def inline_spoiler(self, text: str) -> str:
        return self.tag('inline_spoiler', text=text)

    def block_spoiler(self, text: str) -> str:
        return self.tag('block_spoiler_notitle', text='\n' + text + '\n')

    def footnote_ref(self, key: str, index: int):
        # Use superscript for the footnote reference
        return self.tag('footnote_ref', index=index)

    def footnotes(self, text: str):
        # Optionally wrap all footnotes in a specific section if needed
        return self.tag('footnotes', text=text)

    def footnote_item(self, text: str, key: str, index: int):
        # Define the footnote with an anchor at the end of the document
        return self.tag('footnote_item', text=text, index=index)

    def table(self, children, **attrs):
        return self.tag('table', text=children) + '\n'

    def table_head(self, children, **attrs):
        return self.tag('table_row', text=children) + '\n'

    def table_body(self, children, **attrs):
        return children

    def table_row(self, children, **attrs):
        return self.tag('table_row', text=children) + '\n'

    def table_cell(self, text, align=None, head=False, **attrs):
        # BBCode does not support direct cell alignment,
        # use [LEFT], [CENTER], or [RIGHT] tags
        if align in ('left', 'center', 'right'):
            text = self.tag('align_' + align, text=text)

        # Use th for header cells and td for normal cells
        return self.tag('table_head_cell' if head else 'table_cell', text=text) + '\n'

    def task_list_item(self, text: str, checked: bool = False) -> str:
        # Using emojis to represent the checkbox
        return self.tag('task_checked' if checked else 'task_unchecked', text=text) + '\n'

    def def_list(self, text: str) -> str:
        # No specific BBCode tag for <dl>, so we just use the plain text grouping
        return '\n' + self.tag('def_list', text=text) + '\n'

    def def_list_head(self, text: str) -> str:
        return self.tag('def_list_head', text=text) + '\n'

    def def_list_item(self, text: str) -> str:
        return self.tag('def_list_item', text=text) + '\n'

    def abbr(self, text: str, title: str) -> str:
        if title:
            return self.tag('abbr', text=text, title=title)
        return text
