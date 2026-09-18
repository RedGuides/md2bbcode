"""Read custom tags from a XenForo BB code export, matching by HTML or name."""

import re
import xml.etree.ElementTree as ET

from md2bbcode.html_tokens import start_element
from md2bbcode.plugins import html_events

# HTML matches: tag setting -> option placeholder, if needed.
_BY_HTML = {
    "mark": None,
    "superscript": None,
    "subscript": None,
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
    "abbr": ("abbr", "title"),
}

_NAME_RE = re.compile(r"^[a-z0-9_]+$")
_IGNORED_CONTENT = ("style", "script")


def _wrapper(replace_html: str):
    """Find a single tag pair around {text}."""
    events, skipping = [], None
    for event in html_events(replace_html):
        if skipping:
            skipping = None if event[:2] == ("end", skipping) else skipping
        elif event[0] == "start" and event[1] in _IGNORED_CONTENT:
            skipping = event[1]
        elif event[0] != "text" or event[1].strip():
            events.append(event)

    if len(events) != 3 or events[0][0] != "start":
        return None
    if (events[1][0], events[1][1].strip()) != ("text", "{text}") or events[2] != ("end", events[0][1]):
        return None
    return events[0]


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
        # Skip tags with incompatible option requirements.
        if code.get("has_option", "no") == ("no" if placeholder else "yes"):
            continue
        name = name.upper() if upper else name
        option = f"={{{placeholder}}}" if placeholder else ""
        tags.setdefault(key, f"[{name}{option}]{{text}}[/{name}]")
    return tags
