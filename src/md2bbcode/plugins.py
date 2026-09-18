"""Join split lists and match HTML tags."""

import re
from html.parser import HTMLParser
from typing import List, Optional

from md2bbcode.html_tokens import (
    BLOCK_TOKEN_TYPES,
    CONVERTED_TAGS,
    PREFORMATTED_TAGS,
    VOID_TAGS,
    Element,
    finish_element,
    start_element,
    unescape_references,
    void_token,
)


def merge_ordered_lists(md):
    """
    A plugin to merge consecutive "top-level" ordered lists into one,
    and also attach any intervening code blocks or blank lines to the
    last list item so that the final BBCode appears as a single list
    with multiple steps.

    This relies on a few assumptions:
      1) The only tokens between two ordered lists that should be merged
         are code blocks or blank lines (not normal paragraphs).
      2) We want any code block(s) right after a list item to appear in
         that same bullet item.
    """

    def rewrite_tokens(md, state):
        tokens = state.tokens
        merged = []
        i = 0

        while i < len(tokens):
            token = tokens[i]

            # Check if this token is a top-level ordered list
            if (
                token["type"] == "list"
                and token.get("attrs", {}).get("ordered", False)
                and token.get("attrs", {}).get("depth", 0) == 0
            ):
                # Start new merged list
                current_depth = token["attrs"]["depth"]
                list_items = list(token["children"])  # bullet items in the first list
                i += 1

                # Continue until we run into something that's not:
                #   another top-level ordered list,
                #   or code blocks / blank lines (which we'll attach to the last bullet).
                while i < len(tokens):
                    nxt = tokens[i]

                    # If there's another ordered list at the same depth, merge its bullet items
                    if (
                        nxt["type"] == "list"
                        and nxt.get("attrs", {}).get("ordered", False)
                        and nxt.get("attrs", {}).get("depth", 0) == current_depth
                    ):
                        list_items.extend(nxt["children"])
                        i += 1

                    # If there's a code block or blank line, attach it to the *last* bullet item.
                    elif nxt["type"] in ["block_code", "blank_line"]:
                        if list_items:  # attach to last bullet item, if any
                            list_items[-1]["children"].append(nxt)
                        i += 1

                    else:
                        # Not a same-depth list or code block—stop merging
                        break

                # Create single merged list token
                merged.append(
                    {
                        "type": "list",
                        "children": list_items,
                        "attrs": {
                            "ordered": True,
                            "depth": current_depth,
                        },
                    }
                )

            else:
                # If not a top-level ordered list, just keep it as-is
                merged.append(token)
                i += 1

        # Replace the old tokens with the merged version
        state.tokens = merged

    # Attach to before_render_hooks so we can manipulate tokens before rendering
    md.before_render_hooks.append(rewrite_tokens)
    return md


# Mistune splits HTML tags apart; pair_html groups them with their content.

_WHITESPACE = " \t\n\r\f"
_WHITESPACE_RE = re.compile(f"[{_WHITESPACE}]+")

# These tokens contain blocks, not inline text.
_BLOCK_PARENTS = {"list", "list_item", "task_list_item", "block_quote", "block_spoiler", "footnotes", "footnote_item"}

_LISTS = {"ul", "ol"}
_TABLE = {"table"}
_TABLE_SECTIONS = {"thead", "tbody", "tfoot"}

# New tags can close earlier items, but not outside their list or table.
_CLOSED_BY_START = {
    "li": ({"li"}, _LISTS),
    "tr": ({"tr", "td", "th"}, _TABLE),
    "td": ({"td", "th"}, _TABLE),
    "th": ({"td", "th"}, _TABLE),
    **{tag: (_TABLE_SECTIONS | {"tr", "td", "th"}, _TABLE) for tag in _TABLE_SECTIONS},
}
# A new block ends the current paragraph.
_CLOSES_P = {
    "address", "article", "aside", "blockquote", "center", "details", "div", "dl", "fieldset", "figcaption",
    "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "main", "menu", "nav",
    "ol", "p", "pre", "section", "summary", "table", "ul",
}
_P_BOUNDARY = {"blockquote", "details", "div", "li", "ol", "summary", "table", "td", "th", "ul"}
# Closing tags stay within their list or table.
_END_BOUNDARY = {"li": _LISTS, **{tag: _TABLE for tag in _TABLE_SECTIONS | {"tr", "td", "th"}}}
# These tags can end when their parent ends.
_OPTIONAL_END = _TABLE_SECTIONS | {"p", "li", "tr", "td", "th"}

# Skip document wrappers and hidden content.
_DROPPED_TAGS = {"html", "body"}
_DROPPED_WITH_CONTENT = {"head", "script", "style"}

# Wrap loose text in paragraphs where needed.
_BOX_ALWAYS = {"div"}
_BOX_BESIDE_BLOCKS = {"li", "td", "th", "blockquote", "details"}
_TRIM_BESIDE = BLOCK_TOKEN_TYPES | {"linebreak"}


class _EventCollector(HTMLParser):
    """Collect HTML tags and text in order."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events = []

    def handle_starttag(self, tag, attrs):
        # Keep the first value of a repeated attribute.
        attrs = {name: unescape_references(value or "") for name, value in reversed(attrs)}
        self.events.append(("start", tag, attrs, _as_written(self.get_starttag_text())))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            # Close self-closing tags like <a name="x"/>.
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        self.events.append(("end", tag))

    def handle_data(self, data):
        if self.events and self.events[-1][0] == "text":
            data = self.events.pop()[1] + data
        self.events.append(("text", data))


def _as_written(text: str) -> str:
    return text.replace("&amp;", "&")


def html_events(source: str) -> list:
    """Collect tags and text, leaving &amp; and similar escapes for the renderer."""
    parser = _EventCollector()
    parser.feed(source.replace("&", "&amp;"))
    tail = parser.rawdata
    fed = len(parser.events)
    parser.close()

    # Keep a cut-off tag as text instead of losing it.
    cut = tail.find("<")
    if cut != -1 and (tail[cut + 1:cut + 2].isalpha() or tail.startswith("</", cut)):
        if not any(event[0] == "text" and "<" in event[1] for event in parser.events[fed:]):
            parser.handle_data(_as_written(tail[cut:]))
    return parser.events


def _raw_html(raw: str) -> dict:
    return {"type": "inline_html", "raw": raw}


def _tidy(children: list, box: Optional[str] = None) -> None:
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
        run = None
        for token in tidied:
            if token["type"] in BLOCK_TOKEN_TYPES:
                boxed.append(token)
                run = None
            elif run is None:
                run = [token]
                boxed.append({"type": box, "children": run})
            else:
                run.append(token)
        tidied = boxed

    children[:] = tidied


class _Pairer:
    """Match HTML tags within a list of tokens."""

    def __init__(self, inline: bool):
        self.inline = inline
        self.out: List[dict] = []
        self.stack: List[Element] = []

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
            self.add(void_token(tag, attrs) or _raw_html(raw))
            return

        element = start_element(tag, attrs, raw, self.stack) if tag in CONVERTED_TAGS else None
        if element is None:
            self.add(_raw_html(raw))
            if tag in CONVERTED_TAGS:
                # Keep both tags when conversion fails, e.g. <a> without href.
                element = Element(tag, attrs, raw, None)
                element.keep_end_tag = True
                self._push(element)
            return
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
        if tag not in CONVERTED_TAGS and tag not in _DROPPED_TAGS | _DROPPED_WITH_CONTENT:
            self.add(_raw_html(f"</{tag}>"))

    def _close(self, element: Element) -> None:
        if element.token is None:
            return
        if element.tag in _BOX_ALWAYS:
            _tidy(element.children, box="paragraph")
        elif element.tag in _BOX_BESIDE_BLOCKS:
            beside_blocks = any(token["type"] in BLOCK_TOKEN_TYPES for token in element.children)
            box = "block_text" if element.tag == "li" else "paragraph"
            _tidy(element.children, box=box if beside_blocks else None)
        elif element.tag not in PREFORMATTED_TAGS and element.token["type"] in BLOCK_TOKEN_TYPES | {"summary"}:
            _tidy(element.children)
        finish_element(element, self.stack[-1] if self.stack else None)

    def _put_back(self, element: Element) -> None:
        """Restore an unclosed tag as HTML, keeping its content."""
        if element.keep_end_tag or element.tag in _DROPPED_WITH_CONTENT:
            return
        if element.token is None:
            element.parent_list.insert(element.index, _raw_html(element.raw))
            return
        title = element.token.get("attrs", {}).get("title", []) if element.tag == "details" else []
        element.parent_list[element.index:element.index + 1] = [_raw_html(element.raw), *title, *element.children]

    def finish(self) -> List[dict]:
        while self.stack:
            element = self.stack.pop()
            if element.tag in _OPTIONAL_END:
                self._close(element)
            else:
                self._put_back(element)
        if not self.inline:
            _tidy(self.out, box="paragraph")
        return self.out


def pair_html(tokens: List[dict], inline: bool = False) -> List[dict]:
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