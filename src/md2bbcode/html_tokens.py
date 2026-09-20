"""Read HTML into tag events, and turn the tags into tokens for the BBCode renderer."""

import html
import re
from html.parser import HTMLParser

# Allowed XenForo 2.3 options; see XF\BbCode\RuleSet::addDefaultTags().
_XF_COLOR_OPTION_RE = re.compile(
    r"^(rgb\(\s*\d+%?\s*,\s*\d+%?\s*,\s*\d+%?\s*\)|#[a-f0-9]{6}|#[a-f0-9]{3}|[a-z]+)$",
    re.IGNORECASE,
)
_XF_FONT_OPTION_RE = re.compile(r"^[a-z0-9 \-]+$", re.IGNORECASE)
_XF_SIZE_OPTION_RE = re.compile(r"^[0-9]+(px)?$", re.IGNORECASE)

# Anything in a font name other than letters, numbers, spaces and hyphens.
_FONT_UNSAFE_RE = re.compile(r"[^a-z0-9 \-]+", re.IGNORECASE)
_SPACES_RE = re.compile(r"\s+")

# Require a semicolon so URL text like &region=US stays intact.
_REFERENCE_RE = re.compile(r"&(#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")

# XenForo 2.3 image sizes; see XF\BbCode\Renderer\Html::processImageDisplayModifiers().
_XF_IMAGE_SIZE_RE = re.compile(r"^[0-9.]+(px|%)$", re.IGNORECASE)

# Tags with no content and no closing tag.
VOID_TAGS = {"br", "hr", "img", "source", "wbr"}
LIST_TAGS = {"ul", "ol"}

_INLINE_TAGS = {
    "b": "strong",
    "strong": "strong",
    "i": "emphasis",
    "em": "emphasis",
    "var": "emphasis",
    "cite": "emphasis",
    "dfn": "emphasis",
    "q": "inline_quote",
    "u": "insert",
    "ins": "insert",
    "s": "strikethrough",
    "del": "strikethrough",
    "strike": "strikethrough",
    "sup": "superscript",
    "sub": "subscript",
    "mark": "mark",
}

# Headings and their levels, the same ones Markdown's # to ###### give.
_HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

# Table sections. Keep the contents of these tags, not the tags themselves.
TABLE_SECTION_TAGS = {"thead", "tbody", "tfoot"}

# Tags BBCode has nothing for. Keep the contents of these too: <picture> leaves its <img>,
# and <ruby> leaves its text with the reading in brackets, e.g. 漢(kan).
_TRANSPARENT_TAGS = TABLE_SECTION_TAGS | {"picture", "time", "bdo", "ruby", "rt", "rp"}

# Link media files rather than guessing an attachment or media-site ID.
_MEDIA_TAGS = {"audio", "video"}

# Inline code. <kbd> has a tag setting of its own, for boards with a [KBD] BB code.
_CODE_SPAN_TAGS = {"code": "codespan", "tt": "codespan", "samp": "codespan", "kbd": "kbd"}

# Definition lists, as the tokens Markdown's "Term" and ": Definition" lines give.
_DEFINITION_TAGS = {"dl": "def_list", "dt": "def_list_head", "dd": "def_list_item"}

# <figcaption> inside <figure>, and <caption> inside <table>.
_CAPTION_PARENTS = {"figcaption": "figure", "caption": "table"}

CONVERTED_TAGS = (
    set(_INLINE_TAGS) | set(_HEADING_TAGS) | VOID_TAGS | _TRANSPARENT_TAGS | _MEDIA_TAGS
    | set(_CODE_SPAN_TAGS) | set(_DEFINITION_TAGS) | set(_CAPTION_PARENTS)
    | {"a", "abbr", "blockquote", "details", "div", "figure", "font", "li", "ol",
       "p", "pre", "small", "span", "summary", "table", "td", "th", "tr", "ul"}
)

# Text inside these keeps its whitespace.
PREFORMATTED_TAGS = {"pre", "code", "kbd"}

BLOCK_TOKEN_TYPES = {
    "paragraph", "block_text", "heading", "thematic_break", "blank_line", "block_code",
    "block_quote", "block_html", "block_error", "block_spoiler", "div", "caption",
    "list", "list_item", "task_list_item", "def_list", "def_list_head", "def_list_item",
    "table", "table_head", "table_body", "table_row", "table_cell", "footnotes", "footnote_item",
}

_BLOCKQUOTE_AUTHOR_ATTRS = ("data-quote", "data-attribution", "data-author", "data-username", "data-cite", "cite")


def _strip_important(value: str) -> str:
    # XenForo options don't accept !important.
    return value.replace("!important", "").strip()


def _sanitize_option(value: str, allowed: re.Pattern) -> str | None:
    """Clean up a colour or size, and return it only if XenForo accepts it."""
    value = _strip_important(value.strip().strip('"').strip("'"))
    return value if value and allowed.match(value) else None


def _sanitize_color(value: str) -> str | None:
    return _sanitize_option(value, _XF_COLOR_OPTION_RE)


def _sanitize_size(value: str) -> str | None:
    return _sanitize_option(value, _XF_SIZE_OPTION_RE)


def _sanitize_font(value: str) -> str | None:
    value = _strip_important(value.strip())
    # Use the first font, e.g. Arial from "Arial", sans-serif.
    if "," in value:
        value = value.split(",", 1)[0]
    value = value.strip().strip('"').strip("'")
    # Keep only letters, numbers, spaces and hyphens.
    value = _FONT_UNSAFE_RE.sub(" ", value)
    value = _SPACES_RE.sub(" ", value).strip()
    return value if value and _XF_FONT_OPTION_RE.match(value) else None


# Reading HTML
#
# HTMLParser decodes references without semicolons, changing "&region=US" to "®ion=US".
# Disabling convert_charrefs loses whether a reference had a semicolon.
# Escape every "&" before parsing to preserve the original text:
#
# - html_events adds "&amp;"; HTMLParser removes this layer from text and attributes.
# - _as_written removes it from raw opening tags.
# - text_token protects decoded attribute values when reused as text.
# - unescape_references decodes only semicolon-terminated references.
# The renderer decodes text; attributes and HTML code content are decoded here.

def unescape_references(value: str) -> str:
    """Decode only HTML references that end with a semicolon, such as &copy; and &#169;."""
    return _REFERENCE_RE.sub(lambda match: html.unescape(match.group(0)), value)


def text_token(text: str) -> dict:
    """Keep decoded text from being decoded again by the renderer."""
    return {"type": "text", "raw": text.replace("&", "&amp;")}


def _as_written(text: str) -> str:
    """Restore the original opening tag after html_events escapes ampersands."""
    return text.replace("&amp;", "&")


class _EventCollector(HTMLParser):
    """Collect HTML tags and text in order, as plain tuples:

        ("start", tag, attrs, raw)    attrs is a dict; raw is the tag as written
        ("end", tag)
        ("text", data)

    Comments, doctypes and processing instructions are left out.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events = []

    def handle_starttag(self, tag, attrs):
        values = {}
        for name, value in attrs:
            # A repeated attribute keeps its first value.
            if name not in values:
                values[name] = unescape_references(value or "")
        self.events.append(("start", tag, values, _as_written(self.get_starttag_text())))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            # Close self-closing tags like <a name="x"/>.
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        self.events.append(("end", tag))

    def handle_data(self, data):
        # Rejoin text split by a stray "<", including incomplete tags recovered by html_events.
        if self.events and self.events[-1][0] == "text":
            data = self.events.pop()[1] + data
        self.events.append(("text", data))


def html_events(source: str) -> list:
    """Collect tags and text, leaving &amp; and similar escapes for the renderer."""
    parser = _EventCollector()
    parser.feed(source.replace("&", "&amp;"))

    # close() can drop an incomplete tag, e.g. "text <unclosed tag".
    # Save the unparsed input first; rawdata is an undocumented HTMLParser buffer.
    unparsed = parser.rawdata
    events_before_close = len(parser.events)
    parser.close()

    tag_start = unparsed.find("<")
    if tag_start == -1:
        return parser.events
    looks_like_a_tag = unparsed[tag_start + 1:tag_start + 2].isalpha() or unparsed.startswith("</", tag_start)
    came_out_as_text = any(event[0] == "text" and "<" in event[1] for event in parser.events[events_before_close:])
    if looks_like_a_tag and not came_out_as_text:
        # Keep the cut-off tag as text instead of losing it.
        parser.handle_data(_as_written(unparsed[tag_start:]))
    return parser.events


# Turning tags into tokens

def _parse_style(style: str) -> dict[str, str]:
    css_properties: dict[str, str] = {}
    for item in style.split(";"):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        key = key.strip().lower()
        if key:
            css_properties[key] = value.strip()
    return css_properties


def _alignment(attrs: dict, css: dict) -> str | None:
    align = (attrs.get("align") or css.get("text-align") or "").strip().lower()
    return align if align in ("left", "center", "right") else None


def _style_wrappers(attrs: dict, css: dict, core: str | None = None) -> list[dict]:
    """Turn font and CSS styles into tokens, without repeating the tag's own style."""
    font = {
        "color": _sanitize_color(attrs.get("color") or "") or _sanitize_color(css.get("color", "")),
        "size": _sanitize_size(attrs.get("size") or "") or _sanitize_size(css.get("font-size", "")),
        "face": _sanitize_font(attrs.get("face") or "") or _sanitize_font(css.get("font-family", "")),
    }
    font = {key: value for key, value in font.items() if value}

    wanted = []
    decoration = css.get("text-decoration", "").lower()
    if "line-through" in decoration:
        wanted.append("strikethrough")
    if "underline" in decoration:
        wanted.append("insert")
    weight = css.get("font-weight", "").lower()
    if weight == "bold" or (weight.isdigit() and int(weight) >= 700):
        wanted.append("strong")
    if css.get("font-style", "").lower() in ("italic", "oblique"):
        wanted.append("emphasis")

    wrappers = [{"type": "font", "children": [], "attrs": font}] if font else []
    wrappers.extend({"type": kind, "children": []} for kind in wanted if kind != core)
    return wrappers


def _code_language(attrs: dict) -> str | None:
    for cls in (attrs.get("class") or "").split():
        for prefix in ("language-", "lang-"):
            if cls.startswith(prefix) and cls != prefix:
                return cls[len(prefix):]
    return None


def plain_text(tokens: list[dict]) -> str:
    """Get token text without markup, for code blocks and heading anchors."""
    parts = []
    for token in tokens:
        if token["type"] in ("softbreak", "linebreak"):
            parts.append("\n")
        elif "raw" in token:
            parts.append(token["raw"])
        elif "children" in token:
            parts.append(plain_text(token["children"]))
    return "".join(parts)


class Element:
    """Track an open HTML tag and where its content goes.

    Converted tags put content in the token's ``children`` or its innermost style wrapper.
    With no token, ``children`` is either the parent's list (e.g. an unstyled <span>)
    or a discarded list (e.g. <script>).

    ``keep_end_tag`` preserves both HTML tags when conversion fails, e.g. <a> with no href.
    Its content still goes into the parent's list.
    """

    def __init__(self, tag: str, attrs: dict, raw: str, token: dict | None, children: list | None = None):
        self.tag = tag
        self.attrs = attrs
        self.raw = raw  # restored if the tag never closes
        self.token = token  # None for tags that pass through or discard their content
        self.children = children
        self.keep_end_tag = False  # keep the closing tag as HTML too
        self.language = None  # from <pre> or its inner <code>
        self.parent_list = None  # where the tag stands; set by _Pairer._push in plugins.py
        self.index = 0


def _chain(element: Element, tokens: list[dict]) -> Element:
    """Nest tokens, with the content inside the last one."""
    for outer, inner in zip(tokens, tokens[1:]):
        outer["children"].append(inner)
    element.token = tokens[0]
    element.children = tokens[-1]["children"]
    return element


def _link_token(attrs: dict) -> dict | None:
    href = (attrs.get("href") or "").strip()
    if href:
        if href.lower().startswith("mailto:"):
            address = href[7:].split("?", 1)[0].strip()
            if address:
                return {"type": "email", "children": [], "attrs": {"address": address}}
        if href.startswith("#") and len(href) > 1:
            return {"type": "link_anchor", "children": [], "attrs": {"anchor": href[1:]}}
        return {"type": "link", "children": [], "attrs": {"url": href}}
    name = attrs.get("name") or attrs.get("id")
    if name:
        return {"type": "anchor", "children": [], "attrs": {"name": name}}
    return None


def _image_size(value: str) -> str | None:
    """Return a width or height XenForo accepts: "200" and "200px" give "200px", "50%" stays."""
    value = _strip_important(value.strip()).lower()
    if value.replace(".", "", 1).isdigit():
        value += "px"
    return value if _XF_IMAGE_SIZE_RE.match(value) else None


def _image_token(attrs: dict) -> dict | None:
    src = attrs.get("src")
    if not src:
        return None
    css = _parse_style(attrs.get("style") or "")
    alt = attrs.get("alt") or ""
    align = (attrs.get("align") or css.get("float") or "").strip().lower()
    image = {
        "url": src,
        "width": _image_size(attrs.get("width") or css.get("width", "")),
        "height": _image_size(attrs.get("height") or css.get("height", "")),
        # XenForo floats an image left or right; it has no other alignment.
        "align": align if align in ("left", "right") else None,
    }
    return {"type": "image", "children": [text_token(alt)] if alt else [], "attrs": image}


def void_token(tag: str, attrs: dict) -> dict | None:
    """Convert <br>, <hr> or <img>, returning None to keep the HTML."""
    if tag == "br":
        return {"type": "linebreak"}
    if tag == "hr":
        return {"type": "thematic_break"}
    if tag == "img":
        return _image_token(attrs)
    return None


def start_element(tag: str, attrs: dict, raw: str, stack: list[Element]) -> Element | None:
    """Convert an opening tag, returning None to keep the HTML."""
    element = Element(tag, attrs, raw, None)
    css = _parse_style(attrs.get("style") or "")

    if tag in _TRANSPARENT_TAGS:
        return element

    if tag in _INLINE_TAGS:
        core = _INLINE_TAGS[tag]
        return _chain(element, _style_wrappers(attrs, css, core) + [{"type": core, "children": []}])

    if tag in ("span", "font"):
        wrappers = _style_wrappers(attrs, css)
        return _chain(element, wrappers) if wrappers else element

    if tag == "small":
        # [SIZE=3] is 12px on XenForo, where normal text is 15px.
        return _chain(element, [{"type": "font", "children": [], "attrs": {"size": "3"}}] + _style_wrappers(attrs, css))

    if tag in _CODE_SPAN_TAGS:
        return _chain(element, [{"type": _CODE_SPAN_TAGS[tag], "children": []}])

    if tag == "pre":
        element.language = _code_language(attrs)
        return _chain(element, [{"type": "block_code", "children": []}])

    if tag == "a":
        token = _link_token(attrs)
        return _chain(element, [token]) if token else None

    if tag in _MEDIA_TAGS:
        src = (attrs.get("src") or "").strip()
        if not src:
            # The player is built from <source> children; leave it as written.
            return None
        element.token = {"type": "link", "children": [text_token(src)], "attrs": {"url": src}}
        # Omit the player's fallback message; the file link replaces the player.
        element.children = []
        return element

    if tag == "abbr":
        title = attrs.get("title")
        return _chain(element, [{"type": "abbr", "children": [], "attrs": {"title": title}}]) if title else None

    if tag in _HEADING_TAGS:
        # The token Markdown's "# Title" makes, so the two render and anchor alike.
        token = {"type": "heading", "children": [], "attrs": {"level": _HEADING_TAGS[tag]}, "style": "atx"}
        tokens = [token] + _style_wrappers(attrs, css)
        align = _alignment(attrs, css)
        if align:
            # [CENTER] goes around the whole heading, as in <h1 align="center">.
            tokens.insert(0, {"type": "div", "children": [], "attrs": {"align": align}})
        return _chain(element, tokens)

    if tag in ("p", "div", "figure"):
        # A <figure> is a box around an image and its caption, which is what a <div> is.
        token = {"type": "paragraph" if tag == "p" else "div", "children": []}
        align = _alignment(attrs, css)
        if align:
            token["attrs"] = {"align": align}
        return _chain(element, [token] + _style_wrappers(attrs, css))

    if tag in _CAPTION_PARENTS:
        if not stack or stack[-1].tag != _CAPTION_PARENTS[tag]:
            return None
        # A table's caption moves above the table when </caption> closes it; see _Pairer._lift_caption.
        return _chain(element, [{"type": "caption", "children": []}])

    if tag in _DEFINITION_TAGS:
        return _chain(element, [{"type": _DEFINITION_TAGS[tag], "children": []}])

    if tag == "blockquote":
        token = {"type": "block_quote", "children": []}
        for key in _BLOCKQUOTE_AUTHOR_ATTRS:
            author = (attrs.get(key) or "").strip()
            if author:
                token["attrs"] = {"author": author}
                break
        tokens = [token]
        align = _alignment(attrs, css)
        if align:
            tokens.append({"type": "div", "children": [], "attrs": {"align": align}})
        return _chain(element, tokens + _style_wrappers(attrs, css))

    if tag in LIST_TAGS:
        depth = sum(1 for parent in stack if parent.tag in LIST_TAGS)
        token = {"type": "list", "children": [], "tight": True, "attrs": {"depth": depth, "ordered": tag == "ol"}}
        return _chain(element, [token])

    if tag == "li":
        return _chain(element, [{"type": "list_item", "children": []}])

    if tag == "table":
        return _chain(element, [{"type": "table", "children": []}])

    if tag == "tr":
        return _chain(element, [{"type": "table_row", "children": []}])

    if tag in ("td", "th"):
        token = {"type": "table_cell", "children": [], "attrs": {"align": _alignment(attrs, css), "head": tag == "th"}}
        return _chain(element, [token] + _style_wrappers(attrs, css))

    if tag == "details":
        return _chain(element, [{"type": "block_spoiler", "children": []}])

    if tag == "summary" and stack and stack[-1].tag == "details":
        # Becomes the spoiler title when </summary> closes it; see _Pairer._lift_title.
        return _chain(element, [{"type": "summary", "children": []}])

    return None


def finish_element(element: Element, parent: Element | None) -> None:
    """Finish code spans and code blocks once their content is ready."""
    token = element.token
    if element.tag in _CODE_SPAN_TAGS:
        token["raw"] = unescape_references(plain_text(token.pop("children")))
        if element.tag == "code" and parent is not None and parent.tag == "pre" and not parent.language:
            parent.language = _code_language(element.attrs)

    elif element.tag == "pre":
        code = unescape_references(plain_text(token.pop("children")))
        # Browsers ignore a line break straight after <pre>.
        token["raw"] = code[1:] if code.startswith("\n") else code
        token["style"] = "fenced"
        if element.language:
            token["attrs"] = {"info": element.language}
