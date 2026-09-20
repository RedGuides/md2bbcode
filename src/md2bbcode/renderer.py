import re
from urllib.parse import unquote, urldefrag, urljoin, urlparse

from mistune import BaseRenderer, safe_entity

from md2bbcode.dialect import get_dialect
from md2bbcode.html_tokens import BLOCK_TOKEN_TYPES, plain_text, unescape_references
from md2bbcode.image_rewrite import rewrite_svg_url
from md2bbcode.plugins import emoji_shortcodes, heading_anchors, pair_html

_HARMFUL_SCHEMES = ('javascript:', 'vbscript:', 'data:')

# Prose blocks use paragraph_separator; tagged blocks such as quotes and lists
# need only a newline because XenForo already displays them as blocks.
_FLOW_BLOCKS = {'paragraph', 'block_text', 'div'}

# Where the heading map is kept, so the footnote pass can see it too.
_ANCHORS = 'heading_anchors'

# GitHub shows an image whose URL ends in one of these in that theme only. A forum post
# cannot follow the reader's theme, so the light image is posted and the dark one is left out.
_LIGHT_ONLY = 'gh-light-mode-only'
_DARK_ONLY = 'gh-dark-mode-only'

# A GitHub alert marker at the start of a quote: "[!NOTE]", "[!TIP]" and so on.
_ALERT_MARKER_RE = re.compile(r"^\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*", re.IGNORECASE)


def _option(value: str) -> str:
    """Make free text safe as a quoted tag option, e.g. [SPOILER="{title}"].

    XenForo reads a quoted option up to the first "] and never across a line, so
    line breaks become spaces and double quotes become single quotes.
    """
    return " ".join(value.split()).replace('"', "'")


def _footnote_anchor(index: int) -> str:
    """Return the shared anchor name for a footnote and its references."""
    return f'fn-{index}'


def _holds_blocks(token: dict) -> bool:
    """Return whether a token contains a block, including through nested inline styles."""
    for child in token.get('children', ()):
        if child['type'] in BLOCK_TOKEN_TYPES or _holds_blocks(child):
            return True
    return False


def _block_type(token: dict, text: str):
    """The token's type if it rendered as a block, which ends with a newline; else None."""
    if token['type'] in BLOCK_TOKEN_TYPES and text.endswith('\n'):
        return token['type']
    return None


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


def _github_bases(domain: str):
    """Return the link and image bases for a GitHub repository URL, or None for any other URL.

    Links open GitHub's file viewer (blob) and images need the file itself (raw):

        https://github.com/o/r                   the repo's home page
        https://github.com/o/r/tree/main/docs    a folder, as the address bar shows it
        https://github.com/o/r/blob/main/docs/   the file viewer
    """
    try:
        parsed = urlparse(domain)
    except ValueError:
        return None
    if parsed.scheme not in ('http', 'https') or parsed.netloc.lower() not in ('github.com', 'www.github.com'):
        return None

    # "/o/r/blob/main/docs/" -> "", "o", "r", "blob", "main/docs/"
    parts = parsed.path.split('/', 4)
    parts += [''] * (5 - len(parts))
    _, owner, repo, view, path = parts
    if not owner or not repo:
        return None
    if not view and not path:
        # The home page names no branch. HEAD is the default branch, whatever it is called.
        view, path = 'blob', 'HEAD/'
    if view not in ('blob', 'tree') or not path.split('/', 1)[0]:
        return None
    if not path.endswith('/') and (view == 'tree' or '/' not in path):
        # A folder, or a branch on its own such as blob/main. Without the slash the last
        # part would be replaced, not added to. blob/main/README.md is a file and needs none.
        path += '/'

    # GitHub sends a tree URL for a file to blob, and a blob URL for a folder to tree.
    links = parsed._replace(path=f'/{owner}/{repo}/blob/{path}').geturl()
    images = parsed._replace(netloc='raw.githubusercontent.com', path=f'/{owner}/{repo}/{path}').geturl()
    return links, images


def resolve_bases(link_base=None, image_base=None, domain=None):
    """Use ``domain`` for missing bases, then share either base if only one is set.

    A GitHub ``domain`` gives links and images a base each; see _github_bases.
    """
    links = link_base or domain or image_base or None
    images = image_base or domain or link_base or None
    github = _github_bases(domain) if domain else None
    if github:
        links = link_base or github[0]
        images = image_base or github[1]
    return links, images


class BBCodeRenderer(BaseRenderer):
    """Render parsed Markdown and HTML as BBCode."""
    NAME = 'bbcode'

    def __init__(self, domain=None, link_base=None, image_base=None, dialect=None):
        super().__init__()
        self.link_base, self.image_base = resolve_bases(link_base, image_base, domain)
        self.dialect = get_dialect(dialect)
        self.anchors = {}

    def tag(self, key: str, **values) -> str:
        """Fill in the dialect's template for a tag: tag('strong', text='x') -> '[B]x[/B]'."""
        return self.dialect.render(key, **values)

    def __call__(self, tokens, state):
        tokens = pair_html(list(tokens))
        # Mistune renders footnotes in a second call with the same state.env.
        # Cache the heading map there so both passes use the document's headings.
        if _ANCHORS not in state.env:
            if self.dialect.heading_anchors == 'xenforo':
                state.env[_ANCHORS] = heading_anchors(tokens)
            else:
                state.env[_ANCHORS] = {}
        # Render methods are not given state, so keep a handle where link_anchor can reach it.
        self.anchors = state.env[_ANCHORS]
        # Nothing follows the document, so its last block does not need a line of its own.
        return self.render_tokens(tokens, state).rstrip('\n')

    def render_tokens(self, tokens, state):
        """Render tokens with paragraph spacing and explicit line breaks.

        A token in BLOCK_TOKEN_TYPES counts as a block only if its output ends with
        a newline. Two prose blocks use paragraph_separator; other block boundaries
        use one newline because XenForo supplies the block layout.

        A paragraph or div containing only newlines adds explicit breaks to the next
        gap. For a div, trailing newlines after its block-ending newline do the same.
        Inline wrappers around blocks close before the final newline; see render_token.
        """
        parts = []
        previous_block = None  # the type of the block just added, if the last token was one
        pending_breaks = ''  # line breaks that were asked for, waiting for the next gap
        for token in tokens:
            text = self.render_token(token, state)
            if not text:
                continue
            block_type = _block_type(token, text)
            trailing_breaks = ''
            if block_type:
                body = text.rstrip('\n')
                if not body:
                    # Nothing but line breaks, e.g. <p><br></p> or a <div> around one.
                    if block_type in ('paragraph', 'div'):
                        pending_breaks += text
                    continue
                if block_type == 'div':
                    # Skip the div's own newline; the rest are breaks it ended with.
                    trailing_breaks = text[len(body) + 1:]
                text = body
            if parts and (block_type or previous_block):
                parts.append(self._gap_between(previous_block, block_type))
            parts.append(pending_breaks)
            parts.append(text)
            pending_breaks = trailing_breaks
            previous_block = block_type
        # Breaks that nothing followed still take up their space.
        parts.append(pending_breaks)
        joined = ''.join(parts)
        if previous_block:
            # Leave the last block on a line of its own, for whatever comes next.
            joined += '\n'
        return joined

    def _gap_between(self, previous_block, block_type) -> str:
        """paragraph_separator between two blocks of plain prose; one newline beside anything else."""
        if previous_block in _FLOW_BLOCKS and block_type in _FLOW_BLOCKS:
            return self.dialect.paragraph_separator
        return '\n'

    def render_token(self, token, state):
        # The calling convention of mistune's HTMLRenderer: a method gets the rendered
        # text and the token's attrs, never the token or the state.
        func = self._get_method(token['type'])
        attrs = token.get('attrs') or {}
        if token['type'] == 'block_spoiler' and 'title' in attrs:
            # The <summary> text is the spoiler title. XenForo shows a title as plain
            # text, so any markup in it is dropped rather than written as BBCode.
            title = unescape_references(plain_text(attrs['title']))
            attrs = {**attrs, 'title': _option(title)}

        if 'raw' in token:
            return func(token['raw'], **attrs)
        if 'children' in token:
            text = self.render_tokens(token['children'], state)
            if token['type'] not in BLOCK_TOKEN_TYPES and _holds_blocks(token):
                # An inline tag around blocks, e.g. the colour of <div style="color:red">.
                # The tag closes at the end of the last line and the newline follows it,
                # so the block it belongs to still ends with a newline.
                body = text.rstrip('\n')
                return func(body, **attrs) + text[len(body):]
            return func(text, **attrs)
        return func(**attrs)

    def text(self, text: str) -> str:
        # Decode HTML escapes and emoji shortcodes in text, not code.
        return emoji_shortcodes(unescape_references(text))

    def emphasis(self, text: str) -> str:
        return self.tag('emphasis', text=text)

    def strong(self, text: str) -> str:
        return self.tag('strong', text=text)

    def link(self, text: str, url: str, title=None) -> str:
        if not text:
            # Nothing to click, e.g. a link around a dark-mode image that was left out.
            return ''
        if url.startswith('#') and len(url) > 1:
            return self.link_anchor(text, url[1:])
        return self.tag('link', text=text, url=resolve_url(url, self.link_base))

    def image(self, text: str, url: str, title=None, width=None, height=None, align=None) -> str:
        url, theme = urldefrag(url)
        if theme == _DARK_ONLY:
            return ''
        if theme and theme != _LIGHT_ONLY:
            url += '#' + theme
        safe_url = resolve_url(url, self.image_base)
        rewritten_url = rewrite_svg_url(safe_url)
        if rewritten_url is None:
            # An SVG we cannot turn into a PNG: link to it instead.
            return self.tag('link', text=text or safe_url, url=safe_url)
        # width, height and align come from an HTML <img>; Markdown has no way to write them.
        options = {'alt': _option(text), 'width': width, 'height': height, 'align': align}
        options = ' '.join(f'{name}="{value}"' for name, value in options.items() if value)
        if options:
            img_tag = self.tag('image_options', url=rewritten_url, options=options)
        else:
            img_tag = self.tag('image', url=rewritten_url)
        # Alt text starting with 'pixel' opts into pixel-art rendering.
        if text and text.lower().startswith('pixel'):
            return self.tag('pixelate', text=img_tag)
        return img_tag

    def codespan(self, text: str) -> str:
        return self.tag('codespan', text=text)

    def kbd(self, text: str) -> str:
        return self.tag('kbd', text=text)

    def inline_quote(self, text: str) -> str:
        return self.tag('inline_quote', text=text)

    def linebreak(self) -> str:
        return self.tag('linebreak')

    def softbreak(self) -> str:
        # Keep soft line breaks as spaces; hard breaks still use linebreak().
        return ' '

    def inline_html(self, html: str) -> str:
        # Keep or strip leftover HTML.
        return html if self.dialect.unknown_html == 'keep' else ''

    def font(self, text: str, color=None, size=None, face=None) -> str:
        if face:
            text = self.tag('font_face', text=text, face=face)
        if size:
            text = self.tag('font_size', text=text, size=size)
        if color:
            text = self.tag('font_color', text=text, color=color)
        return text

    def email(self, text: str, address: str) -> str:
        return self.tag('email', text=text, address=address)

    def link_anchor(self, text: str, anchor: str) -> str:
        # Document fragment links use heading_link; the link_anchor template is reserved
        # for footnotes. Decode Mistune's percent-encoded target before looking up
        # its XenForo heading anchor. The lookup is case-sensitive, as on GitHub: a
        # "#Usage" link to a "## Usage" heading is broken there too, so it stays as written.
        return self.tag('heading_link', text=text, anchor=self.anchors.get(unquote(anchor), anchor))

    def anchor(self, text: str, name: str) -> str:
        return self.tag('anchor', text=text, name=name)

    def paragraph(self, text: str, align=None) -> str:
        body = text.rstrip('\n')
        if not body.strip():
            # Keep standalone line breaks; render_tokens adds them to the gap.
            return text
        # An image that was left out may leave the space beside it at either end.
        body = body.strip(' ')
        if align:
            body = self.tag('align_' + align, text=body)
        return body + '\n'

    def div(self, text: str, align=None) -> str:
        if align and text.strip():
            return self.tag('align_' + align, text=text.rstrip('\n')) + '\n'
        return text

    def heading(self, text: str, level: int, **attrs) -> str:
        return self.dialect.heading(level, text) + '\n'

    def blank_line(self) -> str:
        return ''

    def thematic_break(self) -> str:
        return self.tag('thematic_break') + '\n'

    def block_text(self, text: str) -> str:
        return text + '\n'

    def caption(self, text: str) -> str:
        return self.tag('caption', text=text.rstrip('\n')) + '\n'

    def block_code(self, code: str, **attrs) -> str:
        # Code is left as written. The first word after the fence is the language.
        words = safe_entity(attrs.get('info', '')).split(None, 1)
        lang = words[0].lower() if words else None

        # "plaintext" is what a plain [CODE] tag already is.
        if lang and lang != 'plaintext':
            return self.tag('block_code', text=code, lang=lang) + '\n'
        return self.tag('block_code_nolang', text=code) + '\n'

    def block_quote(self, text: str, author=None) -> str:
        # HTML quotes may contain inline text; give it a block's final newline.
        if not text.endswith('\n'):
            text += '\n'
        if author:
            return self.tag('block_quote_author', text=text, author=_option(author)) + '\n'

        # GitHub alerts are block quotes beginning with markers such as [!NOTE].
        alert = _ALERT_MARKER_RE.match(text)
        if alert:
            kind = alert.group(1).lower()
            body = text[alert.end():].strip()
            return self.tag('admonition', text=body, kind=kind, label=kind.capitalize()) + '\n'

        return self.tag('block_quote', text=text) + '\n'

    def list(self, text: str, ordered: bool, **attrs) -> str:
        # Let the forum number ordered items instead of copying source numbers.
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

    def block_spoiler(self, text: str, title=None) -> str:
        blocks = text.endswith('\n')
        if blocks:
            # Put block content on its own lines.
            text = '\n' + text
        if title:
            spoiler = self.tag('block_spoiler', text=text, title=title)
        else:
            spoiler = self.tag('block_spoiler_notitle', text=text)
        # A spoiler holding nothing but inline content stays in the line it came from.
        if blocks:
            spoiler += '\n'
        return spoiler

    def footnote_ref(self, key: str, index: int):
        # Use footnote links and superscript where supported.
        link = str(index)
        if self.dialect.has_anchors:
            link = self.tag('link_anchor', text=link, anchor=_footnote_anchor(index))
        return self.tag('superscript', text=self.tag('footnote_ref', index=index, link=link))

    def footnotes(self, text: str):
        # Mistune adds this section to the finished document, so it brings its own line.
        return '\n' + self.tag('footnotes', text=text)

    def footnote_item(self, text: str, key: str, index: int):
        # Define the footnote with an anchor at the end of the document
        target = self.tag('anchor', text=str(index), name=_footnote_anchor(index))
        return self.tag('footnote_item', text=text.rstrip('\n'), index=index, target=target) + '\n'

    def table(self, children, **attrs):
        return self.tag('table', text=children) + '\n'

    def table_head(self, children, **attrs):
        return self.tag('table_row', text=children) + '\n'

    def table_body(self, children, **attrs):
        return children

    def table_row(self, children, **attrs):
        return self.tag('table_row', text=children) + '\n'

    def table_cell(self, text, align=None, head=False, **attrs):
        # XenForo aligns cell content with wrapper tags, not cell options.
        if align in ('left', 'center', 'right'):
            text = self.tag('align_' + align, text=text)

        return self.tag('table_head_cell' if head else 'table_cell', text=text) + '\n'

    def task_list_item(self, text: str, checked: bool = False) -> str:
        # Using emojis to represent the checkbox
        return self.tag('task_checked' if checked else 'task_unchecked', text=text) + '\n'

    def def_list(self, text: str) -> str:
        # No specific BBCode tag for <dl>, so we just use the plain text grouping
        return self.tag('def_list', text=text) + '\n'

    def def_list_head(self, text: str) -> str:
        return self.tag('def_list_head', text=text) + '\n'

    def def_list_item(self, text: str) -> str:
        # A definition is one line, so its tag closes on that line.
        return self.tag('def_list_item', text=text.rstrip('\n')) + '\n'

    def abbr(self, text: str, title: str) -> str:
        if title:
            return self.tag('abbr', text=text, title=_option(title))
        return text
