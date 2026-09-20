"""Read custom tags from a XenForo BB code export, matching by HTML or name."""

import re
import xml.etree.ElementTree as ET

from md2bbcode.html_tokens import html_events, start_element

# HTML matches: tag setting -> option placeholder, if needed.
_BY_HTML = {
    "mark": None,
    "superscript": None,
    "subscript": None,
    "kbd": None,
    "abbr": "title",
    "anchor": "name",
    "link_anchor": "anchor",
}

# Name matches: BB code name -> tag setting and option placeholder.
_BY_NAME = {
    "admonition": ("admonition", "kind"),
    "pixelate": ("pixelate", None),
    "mark": ("mark", None),
    "sup": ("superscript", None),
    "sub": ("subscript", None),
    "kbd": ("kbd", None),
    "abbr": ("abbr", "title"),
}

_NAME_RE = re.compile(r"^[a-z0-9_]+$")
# Options that hold free text are written in quotes, so a ] inside them does not end the tag.
_QUOTED_OPTIONS = {"title"}
_IGNORED_CONTENT = ("style", "script")


def _wrapper(replace_html: str):
    """Find a single tag pair around {text}, returning its start event or None."""
    events = []
    skipping = None  # the <style> or <script> tag we are inside, if any
    for event in html_events(replace_html):
        kind = event[0]
        if skipping:
            if kind == "end" and event[1] == skipping:
                skipping = None
            continue
        if kind == "start" and event[1] in _IGNORED_CONTENT:
            skipping = event[1]
            continue
        if kind == "text" and not event[1].strip():
            # Whitespace between tags.
            continue
        events.append(event)

    # Only infer a BB code from a single HTML wrapper around {text}.
    if len(events) != 3:
        return None
    start, middle, end = events
    if start[0] != "start" or middle[0] != "text" or middle[1].strip() != "{text}":
        return None
    if end != ("end", start[1]):
        return None
    return start


def _match_html(replace_html: str):
    """Match a BB code's HTML to a tag setting and option placeholder."""
    start = _wrapper(replace_html)
    if start is None:
        return None
    _, tag, attrs, raw = start
    element = start_element(tag, attrs, raw, [])
    if element is None or element.token is None or element.token["type"] not in _BY_HTML:
        return None

    key = element.token["type"]
    placeholder = _BY_HTML[key]
    if placeholder and element.token["attrs"].get(placeholder) != "{option}":
        return None
    return key, placeholder


def tags_from_bb_codes(xml_text, upper: bool = True) -> dict:
    """Read tag templates from an export, keeping the first match for each setting."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"not valid XML: {exc}") from exc
    if root.tag != "bb_codes":
        raise ValueError(f"not a XenForo BB code export: expected <bb_codes>, found <{root.tag}>")

    tags = {}
    for code in root.iter("bb_code"):
        name = code.get("bb_code_id", "").strip().lower()
        if not _NAME_RE.match(name):
            continue
        match = None
        if code.get("bb_code_mode", "replace") == "replace":
            match = _match_html(code.findtext("replace_html") or "")
        match = match or _BY_NAME.get(name)
        if match is None:
            continue

        key, placeholder = match
        has_option = code.get("has_option", "no")  # "yes", "no" or "optional"
        if placeholder and has_option == "no":
            # We would write an option the BB code does not take.
            continue
        if not placeholder and has_option == "yes":
            # The BB code demands an option we do not have.
            continue
        name = name.upper() if upper else name
        option = ""
        if placeholder in _QUOTED_OPTIONS:
            option = f'="{{{placeholder}}}"'
        elif placeholder:
            option = f"={{{placeholder}}}"
        tags.setdefault(key, f"[{name}{option}]{{text}}[/{name}]")

    # A board's anchor-link BB code serves "#section" links as well as footnotes.
    # XenForo shows [URL=#x] as plain text, so it has no tag of its own for either.
    if "link_anchor" in tags:
        tags["heading_link"] = tags["link_anchor"]
    return tags
