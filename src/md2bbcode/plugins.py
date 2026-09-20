"""Token passes: join split lists, match HTML tags, and map heading anchors."""

import re
import string
import unicodedata
from collections.abc import Iterator
from urllib.parse import quote_plus

import emoji

from md2bbcode.html_tokens import (
    BLOCK_TOKEN_TYPES,
    CONVERTED_TAGS,
    LIST_TAGS,
    PREFORMATTED_TAGS,
    TABLE_SECTION_TAGS,
    VOID_TAGS,
    Element,
    finish_element,
    html_events,
    plain_text,
    start_element,
    unescape_references,
    void_token,
)


def _is_top_level_ordered_list(token: dict) -> bool:
    attrs = token.get("attrs", {})
    return token["type"] == "list" and attrs.get("ordered", False) and attrs.get("depth", 0) == 0


def merge_ordered_lists(md):
    """Merge top-level ordered lists separated only by code blocks or blank lines.

    Put intervening and trailing code blocks or blank lines in the last list item
    to keep numbered steps together; any other token ends the list.
    """

    def rewrite_tokens(md, state):
        merged = []
        open_list = None  # the merged list we are still adding to, if any
        for token in state.tokens:
            if _is_top_level_ordered_list(token):
                if open_list is None:
                    # Start a new merged list.
                    open_list = {
                        "type": "list",
                        "children": list(token["children"]),
                        "attrs": {"ordered": True, "depth": 0},
                    }
                    merged.append(open_list)
                else:
                    # Another ordered list straight after: its items join the open one.
                    open_list["children"].extend(token["children"])
            elif open_list is not None and token["type"] in ("block_code", "blank_line"):
                # A code block or blank line between lists belongs to the last item.
                if open_list["children"]:
                    open_list["children"][-1]["children"].append(token)
            else:
                # Anything else ends the merged list.
                open_list = None
                merged.append(token)

        # Replace the old tokens with the merged version
        state.tokens = merged

    md.before_render_hooks.append(rewrite_tokens)
    return md


# Mistune splits HTML tags apart; pair_html groups them with their content.
# Reading the HTML itself (html_events) is in html_tokens.py.

_WHITESPACE = " \t\n\r\f"
_WHITESPACE_RE = re.compile(f"[{_WHITESPACE}]+")

# These tokens contain blocks, not inline text.
_BLOCK_PARENTS = {"list", "list_item", "task_list_item", "block_quote", "block_spoiler", "footnotes", "footnote_item"}

_TABLE = {"table"}
_CELLS = {"td", "th"}
_ROW_AND_CELLS = {"tr", "td", "th"}
_INSIDE_A_TABLE = TABLE_SECTION_TAGS | _ROW_AND_CELLS
_DEFINITION_LIST = {"dl"}
_TERMS_AND_DEFINITIONS = {"dt", "dd"}

# When one of these tags starts, it closes any open tag in the first set, but never looks
# past a tag in the second: a new <li> cannot close an item outside its own list.
_CLOSED_BY_START = {
    "li": ({"li"}, LIST_TAGS),
    "tr": (_ROW_AND_CELLS, _TABLE),
    "td": (_CELLS, _TABLE),
    "th": (_CELLS, _TABLE),
    "thead": (_INSIDE_A_TABLE, _TABLE),
    "tbody": (_INSIDE_A_TABLE, _TABLE),
    "tfoot": (_INSIDE_A_TABLE, _TABLE),
    "dt": (_TERMS_AND_DEFINITIONS, _DEFINITION_LIST),
    "dd": (_TERMS_AND_DEFINITIONS, _DEFINITION_LIST),
}
# A new block ends the current paragraph.
_CLOSES_P = {
    "address", "article", "aside", "blockquote", "center", "details", "div", "dl", "fieldset", "figcaption",
    "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "main", "menu", "nav",
    "ol", "p", "pre", "section", "summary", "table", "ul",
}
_P_BOUNDARY = {"blockquote", "dd", "details", "div", "figure", "li", "ol", "summary", "table", "td", "th", "ul"}
# A closing tag looks for its opening tag, but never outside its list or table.
_END_BOUNDARY = {
    "li": LIST_TAGS,
    "tr": _TABLE,
    "td": _TABLE,
    "th": _TABLE,
    "thead": _TABLE,
    "tbody": _TABLE,
    "tfoot": _TABLE,
    "dt": _DEFINITION_LIST,
    "dd": _DEFINITION_LIST,
}
# These tags can end when their parent ends.
_OPTIONAL_END = TABLE_SECTION_TAGS | {"p", "li", "tr", "td", "th", "dt", "dd"}

# Skip document wrappers and hidden content.
_DROPPED_TAGS = {"html", "body"}
_DROPPED_WITH_CONTENT = {"head", "script", "style"}
_ALL_DROPPED = _DROPPED_TAGS | _DROPPED_WITH_CONTENT

# Loose text is wrapped in a block of this type: always inside a <div> or <figure>, and
# inside the others only when it sits beside blocks.
_BOX_ALWAYS = {"div": "paragraph", "figure": "paragraph"}
_BOX_BESIDE_BLOCKS = {
    "li": "block_text",
    "dd": "block_text",
    "td": "paragraph",
    "th": "paragraph",
    "blockquote": "paragraph",
    "details": "paragraph",
}
_TRIM_BESIDE = BLOCK_TOKEN_TYPES | {"linebreak"}
# Whitespace inside these is tidied when their tag closes.
_TIDIED_TYPES = BLOCK_TOKEN_TYPES | {"summary"}


def _raw_html(raw: str) -> dict:
    return {"type": "inline_html", "raw": raw}


def _tidy(children: list, box: str | None = None) -> None:
    """Trim extra whitespace and optionally wrap loose text in blocks."""
    tidied = []
    for position, token in enumerate(children):
        if token["type"] == "text":
            raw = token["raw"]
            if position == 0 or children[position - 1]["type"] in _TRIM_BESIDE:
                raw = raw.lstrip(_WHITESPACE)
            if position == len(children) - 1 or children[position + 1]["type"] in _TRIM_BESIDE:
                raw = raw.rstrip(_WHITESPACE)
            if not raw:
                continue
            token["raw"] = raw
        tidied.append(token)

    if box:
        boxed = []
        run = None  # the children of the box being filled, while the tokens are inline
        for token in tidied:
            if token["type"] in BLOCK_TOKEN_TYPES:
                boxed.append(token)
                run = None
            elif run is None:
                # Inline content after a block, or at the start: open a new box for it.
                run = [token]
                boxed.append({"type": box, "children": run})
            else:
                run.append(token)
        tidied = boxed

    children[:] = tidied


class _Pairer:
    """Match HTML tags within one list of sibling tokens.

    Tokens are fed in order. ``stack`` holds the HTML tags that are open, innermost last.
    Whatever arrives goes into the innermost open tag, or into ``out`` when none is open.

    - A start tag first closes what it implies: a new <li> ends the one before it, and a
      block ends an open <p>. Then it becomes a token (html_tokens.start_element) and is
      pushed on the stack. Void tags such as <br> are complete at once.
    - An end tag pops the stack down to its start tag, closing anything left open inside
      it, which is what browsers do with <b><i>x</b></i>.
    - Text becomes a text token, with whitespace collapsed as a browser would.
    - A Markdown token goes in as it is.
        - At the end, close tags whose end tag is optional; restore other unclosed tags
            as HTML without dropping their content (except discarded content such as scripts).
    """

    def __init__(self, inline: bool):
        self.inline = inline
        self.out: list[dict] = []
        self.stack: list[Element] = []

    def _target(self) -> list:
        return self.stack[-1].children if self.stack else self.out

    def add(self, token: dict) -> None:
        self._target().append(token)

    def feed(self, html: str) -> None:
        for event in html_events(html):
            if event[0] == "start":
                self._start(*event[1:])
            elif event[0] == "end":
                self._end(event[1])
            else:
                self._text(event[1])

    def _text(self, data: str) -> None:
        target = self._target()
        if not any(element.tag in PREFORMATTED_TAGS for element in self.stack):
            # Among blocks every text token came from HTML, so a run split across two
            # HTML tokens is joined before its whitespace collapses. Inline, the token
            # before may be Markdown text, which keeps its spacing.
            if not self.inline and target and target[-1]["type"] == "text":
                data = target.pop()["raw"] + data
            data = _WHITESPACE_RE.sub(" ", data)
        target.append({"type": "text", "raw": data})

    def _push(self, element: Element) -> None:
        target = self._target()
        element.parent_list = target
        element.index = len(target)
        if element.token is not None:
            target.append(element.token)
        elif element.children is None:
            element.children = target
        self.stack.append(element)

    def _start(self, tag: str, attrs: dict, raw: str) -> None:
        self._close_implied(tag)
        if tag in _DROPPED_TAGS:
            return
        if tag in _DROPPED_WITH_CONTENT:
            self._push(Element(tag, attrs, raw, None, children=[]))
            return
        if tag in VOID_TAGS:
            if tag == "wbr" or (tag == "source" and any(parent.tag == "picture" for parent in self.stack)):
                # A hint for line wrapping, or another version of a <picture>'s <img>: nothing to show.
                return
            self.add(void_token(tag, attrs) or _raw_html(raw))
            return
        if tag not in CONVERTED_TAGS:
            # Not a tag we convert: it stays as written, and its content is still converted.
            self.add(_raw_html(raw))
            return

        element = start_element(tag, attrs, raw, self.stack)
        if element is None:
            # A tag we convert but cannot use, e.g. <a> without href: keep both tags as HTML.
            self.add(_raw_html(raw))
            element = Element(tag, attrs, raw, None)
            element.keep_end_tag = True
        self._push(element)

    def _close_implied(self, tag: str) -> None:
        if tag in _CLOSED_BY_START:
            closes, boundary = _CLOSED_BY_START[tag]
        elif tag in _CLOSES_P:
            closes, boundary = {"p"}, _P_BOUNDARY
        else:
            return
        lowest = None
        for position in range(len(self.stack) - 1, -1, -1):
            if self.stack[position].tag in boundary:
                break
            if self.stack[position].tag in closes:
                lowest = position
        if lowest is not None:
            while len(self.stack) > lowest:
                self._close(self.stack.pop())

    def _end(self, tag: str) -> None:
        boundary = _END_BOUNDARY.get(tag, ())
        for position in range(len(self.stack) - 1, -1, -1):
            if self.stack[position].tag == tag:
                # Close inner tags too, e.g. <b><i>x</b></i>.
                while len(self.stack) > position + 1:
                    self._close(self.stack.pop())
                element = self.stack.pop()
                if element.keep_end_tag:
                    self.add(_raw_html(f"</{tag}>"))
                else:
                    self._close(element)
                return
            if self.stack[position].tag in boundary:
                break
        # Drop unmatched closing tags we handle; keep unknown ones.
        if tag not in CONVERTED_TAGS and tag not in _ALL_DROPPED:
            self.add(_raw_html(f"</{tag}>"))

    def _close(self, element: Element) -> None:
        if element.token is None:
            return
        if element.tag in _BOX_ALWAYS:
            _tidy(element.children, box=_BOX_ALWAYS[element.tag])
        elif element.tag in _BOX_BESIDE_BLOCKS:
            beside_blocks = any(token["type"] in BLOCK_TOKEN_TYPES for token in element.children)
            _tidy(element.children, box=_BOX_BESIDE_BLOCKS[element.tag] if beside_blocks else None)
        elif element.tag not in PREFORMATTED_TAGS and element.token["type"] in _TIDIED_TYPES:
            _tidy(element.children)

        if element.tag == "summary":
            self._lift_title(element)
        elif element.tag == "caption":
            self._lift_caption(element)
        else:
            finish_element(element, self.stack[-1] if self.stack else None)

    def _lift_title(self, summary: Element) -> None:
        """Move a closed <summary> out of the spoiler's content and into its title."""
        del summary.parent_list[summary.index]
        if summary.token["children"]:
            details = self.stack[-1]
            details.token["attrs"] = {"title": summary.token["children"]}

    def _lift_caption(self, caption: Element) -> None:
        """Move a closed <caption> out of the table, which has no tag for it, to the line above."""
        del caption.parent_list[caption.index]
        table = self.stack[-1]
        # Boxed as a <figure>'s caption is, so text before it keeps a paragraph's distance.
        table.parent_list.insert(table.index, {"type": "div", "children": [caption.token]})
        table.index += 1

    def _put_back(self, element: Element) -> None:
        """Restore an unclosed tag as HTML, keeping its content."""
        if element.keep_end_tag or element.tag in _DROPPED_WITH_CONTENT:
            return
        if element.token is None:
            element.parent_list.insert(element.index, _raw_html(element.raw))
            return
        # An unclosed <details> gives back the title _lift_title took.
        title = element.token.get("attrs", {}).get("title", []) if element.tag == "details" else []
        element.parent_list[element.index:element.index + 1] = [_raw_html(element.raw), *title, *element.children]

    def finish(self) -> list[dict]:
        while self.stack:
            element = self.stack.pop()
            if element.tag in _OPTIONAL_END:
                self._close(element)
            else:
                self._put_back(element)
        if not self.inline:
            _tidy(self.out, box="paragraph")
        return self.out


def pair_html(tokens: list[dict], inline: bool = False) -> list[dict]:
    """Match HTML tags and group their content after Markdown parsing."""
    pairer = _Pairer(inline)
    for token in tokens:
        if token["type"] in ("inline_html", "block_html"):
            pairer.feed(token["raw"])
            continue
        if "children" in token:
            token["children"] = pair_html(token["children"], inline=token["type"] not in _BLOCK_PARENTS)
        pairer.add(token)
    return pairer.finish()


# A README links to "#github-slug"; XenForo's [HEADING] anchors itself under another name.

# XenForo\Mvc\Router::prepareStringForUrl turns these into spaces, and drops apostrophes.
_XF_SPACERS = '`!"$%^&*()-+={}[]<>;:@#~,./?|' + "\r\n\t\\"
_XF_TO_SPACE = {ord(char): " " for char in _XF_SPACERS}
_XF_TO_SPACE[ord("'")] = None
# strtolower only touches ASCII.
_ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)


# Characters Unicode normalization (NFKD) cannot simplify.
# This is a subset of XenForo's XF\Data\Str::latinToAscii table.
_XF_LATIN_TO_ASCII = str.maketrans({
    "Æ": "AE", "Ð": "D", "Ø": "O", "Þ": "TH", "ß": "ss", "æ": "ae", "ð": "d", "ø": "o", "þ": "th",
    "Đ": "D", "đ": "d", "Ħ": "H", "ħ": "h", "ı": "i", "ĸ": "q", "Ŀ": "L", "ŀ": "l", "Ł": "L", "ł": "l",
    "ŉ": "'n", "Ŋ": "N", "ŋ": "n", "Œ": "OE", "œ": "oe", "Ŧ": "T", "ŧ": "t", "ƒ": "f", "ẞ": "SS",
    "©": "(C)", "®": "(R)", "×": "*", "÷": "/", "−": "-",
    "‘": "'", "’": "'", "‚": ",", "‛": "'", "“": '"', "”": '"', "„": ",,", "‟": '"', "′": "'", "″": '"',
    "«": "<<", "»": ">>", "‹": "<", "›": ">",
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-",
})


# An emoji shortcode such as :rocket:, but not the middle of 10:30:45 or a:b:c.
_SHORTCODE_RE = re.compile(r"(?<!\w):[a-z0-9_+-]+:(?!\w)")


def emoji_shortcodes(text: str) -> str:
    """Turn GitHub's emoji shortcodes into the emoji: ":rocket:" -> "🚀". Unknown names stay as written."""
    if ":" not in text:
        return text
    return _SHORTCODE_RE.sub(lambda match: emoji.emojize(match.group(0), language="alias"), text)


def _emoji_name(chars: str, data: dict) -> str:
    """Adapt emoji names for XenForo heading anchors, e.g. "flag United States".

    The package uses underscores and omits the board's "flag" prefix; names may
    still differ for emoji renamed since the board's Unicode data was built.
    """
    name = data["en"].strip(":").replace("_", " ")
    if len(chars) == 2 and all("\U0001F1E6" <= char <= "\U0001F1FF" for char in chars):
        # Two regional indicator letters make a country's flag; the board says "Flag: ...".
        name = "flag " + name
    return name


def _romanize(text: str) -> str:
    """Approximate XenForo's conversion of emoji and accented letters to ASCII.

    Emoji names and rare Latin characters may differ from the board's data.
    Other scripts stay untranslated and are percent-encoded, so their heading
    links may not match.
    """
    if text.isascii():
        return text
    # The board's order: emoji first, then its Latin table, then accents.
    text = emoji.replace_emoji(text, replace=_emoji_name)
    text = unicodedata.normalize("NFKD", text.translate(_XF_LATIN_TO_ASCII))
    return "".join(char for char in text if unicodedata.category(char) != "Mn")


def xenforo_anchor(text: str) -> str:
    """The anchor XenForo gives a heading, e.g. "Getting started" -> "-getting-started"."""
    text = _romanize(text).translate(_XF_TO_SPACE)
    text = re.sub(" +", "-", text.strip())
    return "-" + quote_plus(text.translate(_ASCII_LOWER))


def github_slug(text: str) -> str:
    """The anchor GitHub gives a heading, e.g. "Getting started" -> "getting-started"."""
    slug = []
    for char in text.lower():
        if char == " ":
            slug.append("-")
        elif char in "-_":
            slug.append(char)
        elif unicodedata.category(char)[0] in "CPSZ":
            # Punctuation, symbols (emoji included) and control characters go.
            continue
        else:
            slug.append(char)
    return "".join(slug)


def _walk(tokens: list[dict]) -> Iterator[dict]:
    for token in tokens:
        yield token
        children = token.get("children")
        if children:
            yield from _walk(children)


def _numbered(anchor: str, seen: dict[str, int], first_suffix: int) -> str:
    """Number repeated anchors starting at ``first_suffix``."""
    count = seen.get(anchor, 0)
    seen[anchor] = count + 1
    if count == 0:
        return anchor
    return f"{anchor}-{count + first_suffix - 1}"


def heading_anchors(tokens: list[dict]) -> dict[str, str]:
    """Map each heading's GitHub slug to the anchor XenForo writes for it."""
    anchors: dict[str, str] = {}
    github_counts: dict[str, int] = {}
    xenforo_counts: dict[str, int] = {}
    for token in _walk(tokens):
        if token["type"] != "heading":
            continue
        text = unescape_references(plain_text(token.get("children", [])))
        # GitHub's first repeat is "slug-1"; XenForo's is "anchor-2".
        slug = _numbered(github_slug(text), github_counts, 1)
        # The board sees the emoji, not the shortcode it was written as.
        anchors.setdefault(slug, _numbered(xenforo_anchor(emoji_shortcodes(text)), xenforo_counts, 2))
    return anchors
