from mistune.core import BaseRenderer
from mistune.util import escape as escape_text, striptags, safe_entity
import re


class BBCodeRenderer(BaseRenderer):
    """A renderer for converting Markdown to BBCode."""
    _escape: bool
    NAME = 'bbcode'

    def __init__(self, escape=False):
        super(BBCodeRenderer, self).__init__()
        self._escape = escape

    def render_token(self, token, state):
        # backward compitable with v2
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

    def safe_url(self, url: str) -> str:
        # Simple URL sanitization
        if url.startswith(('javascript:', 'vbscript:', 'data:')):
            return '#harmful-link'
        return url

    def text(self, text: str) -> str:
        if self._escape:
            return escape_text(text)
        return text

    def emphasis(self, text: str) -> str:
        return '[i]' + text + '[/i]'

    def strong(self, text: str) -> str:
        return '[b]' + text + '[/b]'

    def link(self, text: str, url: str, title=None) -> str:
        return '[url=' + self.safe_url(url) + ']' + text + '[/url]'

    def image(self, text: str, url: str, title=None) -> str:
        return '[img]' + self.safe_url(url) + '[/img]'

    def codespan(self, text: str) -> str:
        return '[icode]' + text + '[/icode]'

    def linebreak(self) -> str:
        return '\n'

    def softbreak(self) -> str:
        return '\n'

    def inline_html(self, html: str) -> str:
        if self._escape:
            return escape_text(html)
        return html

    def paragraph(self, text: str) -> str:
        return text + '\n\n'

    def heading(self, text: str, level: int, **attrs) -> str:
        if 1 <= level <= 3:
            return f"[HEADING={level}]{text}[/HEADING]\n"
        else:
            # Handle cases where level is outside 1-3, you might want to default to level 3 or treat as normal text
            return f"[HEADING=3]{text}[/HEADING]\n"
    
    def blank_line(self) -> str:
        return ''
    
    def thematic_break(self) -> str:
        return '[hr][/hr]\n'
    
    def block_text(self, text: str) -> str:
        return text
    
    def block_code(self, code: str, info=None) -> str:
        """Renders blocks of code with optional language specification for BBCode."""
        if info is not None:
            # Extract the first word from `info` as the language
            lang = safe_entity(info.strip()).split(None, 1)[0]
            return f"[CODE={lang}]{escape_text(code)}[/CODE]\n\n"
        else:
            return f"[CODE]{escape_text(code)}[/CODE]\n\n"
        
    def block_quote(self, text: str) -> str:
        return '[QUOTE]\n' + text + '[/QUOTE]\n'

    def block_html(self, html: str) -> str:
        if self._escape:
            return '<p>' + escape_text(html.strip()) + '</p>\n'
        return html + '\n'

    def block_error(self, text: str) -> str:
        """
        Render an error block in BBCode. 
        We'll simulate an error block by using a color tag to change the text color to red, 
        which is a common practice for indicating errors. The '[code]' tag is used to preserve formatting.
        """
        return '[color=red][icode]' + text + '[/icode][/color]\n'

    def list(self, text: str, ordered: bool, **attrs) -> str:
        tag = 'list' if not ordered else 'list=1'
        return '[{}]'.format(tag) + text + '[/{}]\n'.format(tag)

    def list_item(self, text: str) -> str:
        return '[*]' + text + '\n'
    
    def strikethrough(self, text: str) -> str:
        return '[s]' + text + '[/s]'