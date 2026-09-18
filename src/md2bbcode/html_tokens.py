"""Turn HTML tags into tokens for the BBCode renderer."""

import html
import re
from typing import Dict, List, Optional

# Allowed XenForo 2.3 options; see XF\BbCode\RuleSet::addDefaultTags().
_XF_COLOR_OPTION_RE = re.compile(
    r"^(rgb\(\s*\d+%?\s*,\s*\d+%?\s*,\s*\d+%?\s*\)|#[a-f0-9]{6}|#[a-f0-9]{3}|[a-z]+)$",
    re.IGNORECASE,
)
_XF_FONT_OPTION_RE = re.compile(r"^[a-z0-9 \-]+$", re.IGNORECASE)
_XF_SIZE_OPTION_RE = re.compile(r"^[0-9]+(px)?$", re.IGNORECASE)

# Require a semicolon so URL text like &region=US stays intact.
_REFERENCE_RE = re.compile(r"&(#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")

VOID_TAGS = {"br", "hr", "img"}

_INLINE_TAGS = {
    "b": "strong",
    "strong": "strong",
    "i": "emphasis",
    "em": "emphasis",
    "u": "insert",
    "ins": "insert",
    "s": "strikethrough",
    "del": "strikethrough",
    "strike": "strikethrough",
    "sup": "superscript",
    "sub": "subscript",
    "mark": "mark",
}

# Keep the contents of these tags, not the tags themselves.
_TRANSPARENT_TAGS = {"thead", "tbody", "tfoot"}

# No BBCode plays a file, so these become a link to it.
_MEDIA_TAGS = {"audio", "video"}

CONVERTED_TAGS = (
    set(_INLINE_TAGS) | VOID_TAGS | _TRANSPARENT_TAGS | _MEDIA_TAGS
    | {"a", "abbr", "blockquote", "code", "details", "div", "font", "kbd", "li", "ol",
       "p", "pre", "span", "summary", "table", "td", "th", "tr", "ul"}
)

# Text inside these keeps its whitespace.
PREFORMATTED_TAGS = {"pre", "code", "kbd"}

BLOCK_TOKEN_TYPES = {
    "paragraph", "block_text", "heading", "thematic_break", "blank_line", "block_code",
    "block_quote", "block_html", "block_error", "block_spoiler", "div",
    "list", "list_item", "task_list_item", "def_list", "def_list_head", "def_list_item",
    "table", "table_head", "table_body", "table_row", "table_cell", "footnotes", "footnote_item",
}

_BLOCKQUOTE_AUTHOR_ATTRS = ("data-quote", "data-attribution", "data-author", "data-username", "data-cite", "cite")


def _strip_important(value: str) -> str:
    # XenForo options don't accept !important.
    return value.replace("!important", "").strip()


def _sanitize_color(value: str) -> Optional[str]:
    value = _strip_important(value.strip().strip('"').strip("'"))
    return value if value and _XF_COLOR_OPTION_RE.match(value) else None


def _sanitize_size(value: str) -> Optional[str]:
    value = _strip_important(value.strip().strip('"').strip("'"))
    return value if value and _XF_SIZE_OPTION_RE.match(value) else None


def _sanitize_font(value: str) -> Optional[str]:
    value = _strip_important(value.strip())
    # Use the first font, e.g. Arial from "Arial", sans-serif.
    if "," in value:
        value = value.split(",", 1)[0]
    value = value.strip().strip('"').strip("'")
    # Keep only letters, numbers, spaces and hyphens.
    value = re.sub(r"[^a-z0-9 \-]+", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip()
    return value if value and _XF_FONT_OPTION_RE.match(value) else None


def unescape_references(value: str) -> str:
    """Decode HTML escapes like &copy; and &#169;."""
    return _REFERENCE_RE.sub(lambda match: html.unescape(match.group(0)), value)


def _parse_style(style: str) -> Dict[str, str]:
    css_properties: Dict[str, str] = {}
    for item in style.split(";"):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        key = key.strip().lower()
        if key:
            css_properties[key] = value.strip()
    return css_properties


def _alignment(attrs: dict, css: dict) -> Optional[str]:
    align = (attrs.get("align") or css.get("text-align") or "").strip().lower()
    return align if align in ("left", "center", "right") else None


def _style_wrappers(attrs: dict, css: dict, core: Optional[str] = None) -> List[dict]:
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


def _code_language(attrs: dict) -> Optional[str]:
    for cls in (attrs.get("class") or "").split():
        for prefix in ("language-", "lang-"):
            if cls.startswith(prefix) and cls != prefix:
                return cls[len(prefix):]
    return None


def text_token(text: str) -> dict:
    """Keep decoded text from being decoded again by the renderer."""
    return {"type": "text", "raw": text.replace("&", "&amp;")}


def plain_text(tokens: List[dict]) -> str:
    """Get token text without markup, for code blocks."""
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
    """Track an open HTML tag and its content."""

    def __init__(self, tag: str, attrs: dict, raw: str, token: Optional[dict], children: Optional[list] = None):
        self.tag = tag
        self.attrs = attrs
        self.raw = raw  # restored if the tag never closes
        self.token = token  # None means content goes into the parent
        self.children = children
        self.keep_end_tag = False  # keep the closing tag as HTML too
        self.language = None  # from <pre> or its inner <code>
        self.parent_list = None  # set by pair_html
        self.index = 0


def _chain(element: Element, tokens: List[dict]) -> Element:
    """Nest tokens, with the content inside the last one."""
    for outer, inner in zip(tokens, tokens[1:]):
        outer["children"].append(inner)
    element.token = tokens[0]
    element.children = tokens[-1]["children"]
    return element


def _link_token(attrs: dict) -> Optional[dict]:
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


def void_token(tag: str, attrs: dict) -> Optional[dict]:
    """Convert <br>, <hr> or <img>, returning None to keep the HTML."""
    if tag == "br":
        return {"type": "linebreak"}
    if tag == "hr":
        return {"type": "thematic_break"}
    src = attrs.get("src")
    if not src:
        return None
    alt = attrs.get("alt") or ""
    return {"type": "image", "children": [text_token(alt)] if alt else [], "attrs": {"url": src}}


def start_element(tag: str, attrs: dict, raw: str, stack: List[Element]) -> Optional[Element]:
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

    if tag in ("code", "kbd"):
        return _chain(element, [{"type": "codespan", "children": []}])

    if tag == "pre":
        element.language = _code_language(attrs)
        return _chain(element, [{"type": "block_code", "children": []}])

    if tag == "a":
        token = _link_token(attrs)
        return _chain(element, [token]) if token else None

    if tag in _MEDIA_TAGS:
        # XenForo plays a video through its attachment or media-site tags, neither of
        # which we can address from a README, so link to the file instead.
        src = (attrs.get("src") or "").strip()
        if not src:
            # The player is built from <source> children; leave it as written.
            return None
        element.token = {"type": "link", "children": [text_token(src)], "attrs": {"url": src}}
        # Whatever is inside is a message for browsers that cannot play it, not for readers.
        element.children = []
        return element

    if tag == "abbr":
        title = attrs.get("title")
        return _chain(element, [{"type": "abbr", "children": [], "attrs": {"title": title}}]) if title else None

    if tag in ("p", "div"):
        token = {"type": "paragraph" if tag == "p" else "div", "children": []}
        align = _alignment(attrs, css)
        if align:
            token["attrs"] = {"align": align}
        return _chain(element, [token] + _style_wrappers(attrs, css))

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

    if tag in ("ul", "ol"):
        depth = sum(1 for parent in stack if parent.tag in ("ul", "ol"))
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
        # Becomes the spoiler title when </summary> closes it.
        return _chain(element, [{"type": "summary", "children": []}])

    return None


def finish_element(element: Element, parent: Optional[Element]) -> None:
    """Finish code blocks and spoiler titles once their content is ready."""
    token = element.token
    if element.tag in ("code", "kbd"):
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

    elif element.tag == "summary":
        del element.parent_list[element.index]
        if token["children"]:
            parent.token["attrs"] = {"title": token["children"]}
