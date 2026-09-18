"""BBCode tag settings: XenForo's own tags, plus the board's custom BB codes."""

import functools
import os
import re
import string
import tomllib
from importlib import resources

from md2bbcode.bb_codes import tags_from_bb_codes

# The built-in tags, and the BB code export that ships with them.
DEFAULTS_FILE = "xenforo.toml"

# Tags and their allowed placeholders; "text" is required where listed.
TAGS = {
    # inline
    "strong": ("text",),
    "emphasis": ("text",),
    "insert": ("text",),
    "strikethrough": ("text",),
    "mark": ("text",),
    "superscript": ("text",),
    "subscript": ("text",),
    "codespan": ("text",),
    "inline_spoiler": ("text",),
    "abbr": ("text", "title"),
    "link": ("text", "url"),
    "link_anchor": ("text", "anchor"),
    "anchor": ("text", "name"),
    "email": ("text", "address"),
    "font_color": ("text", "color"),
    "font_size": ("text", "size"),
    "font_face": ("text", "face"),
    "image": ("url",),
    "image_alt": ("url", "alt"),
    "pixelate": ("text",),
    "linebreak": (),
    # blocks
    "heading": ("text",),
    "thematic_break": (),
    "block_code": ("text", "lang"),
    "block_code_nolang": ("text",),
    "block_quote": ("text",),
    "block_quote_author": ("text", "author"),
    # {kind} is "tip" and {label} is "Tip".
    "admonition": ("text", "kind", "label"),
    "block_spoiler": ("text", "title"),
    "block_spoiler_notitle": ("text",),
    "block_error": ("text",),
    # lists
    "list_ordered": ("text",),
    "list_unordered": ("text",),
    "list_item": ("text",),
    "task_checked": ("text",),
    "task_unchecked": ("text",),
    "def_list": ("text",),
    "def_list_head": ("text",),
    "def_list_item": ("text",),
    # tables
    "table": ("text",),
    "table_row": ("text",),
    "table_head_cell": ("text",),
    "table_cell": ("text",),
    "align_left": ("text",),
    "align_center": ("text",),
    "align_right": ("text",),
    # footnotes: {link} and {target} are linked numbers, or plain numbers without anchors.
    "footnote_ref": ("index", "link"),
    "footnotes": ("text",),
    "footnote_item": ("text", "index", "target"),
}

HEADING_LEVELS = range(1, 7)

# Email can use the address as its link text.
_TEXT_OPTIONAL = {"email"}

# What happens to HTML we do not convert.
UNKNOWN_HTML = ("keep", "strip")

# Letter case for imported custom tags.
TAG_CASES = ("upper", "lower")

_TOP_LEVEL_KEYS = {"name", "paragraph_separator", "unknown_html", "tag_case", "bb_codes", "tags"}


class DialectError(ValueError):
    """A config error that names the bad setting."""


def _check_template(key: str, template, source: str) -> None:
    allowed = TAGS[key.split(".", 1)[0]]
    if not isinstance(template, str):
        raise DialectError(f"{source}: tags.{key} must be text, not {type(template).__name__}")

    try:
        fields = list(string.Formatter().parse(template))
    except ValueError as exc:
        raise DialectError(f"{source}: tags.{key}: {exc} (write {{{{ and }}}} for literal braces)") from exc

    used = set()
    for _, field, spec, conversion in fields:
        if field is None:
            continue
        if field not in allowed or spec or conversion:
            full = "{" + field + ("!" + conversion if conversion else "") + (":" + spec if spec else "") + "}"
            choices = ", ".join("{" + name + "}" for name in allowed) or "none"
            raise DialectError(f"{source}: tags.{key}: unknown placeholder {full} (allowed: {choices})")
        used.add(field)

    if "text" in allowed and "text" not in used and key not in _TEXT_OPTIONAL:
        raise DialectError(f"{source}: tags.{key} must contain {{text}} to keep the content")


def _toml_string(value: str) -> str:
    escapes = {"\\": "\\\\", '"': '\\"', "\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f", "\r": "\\r"}
    out = []
    for char in value:
        if char in escapes:
            out.append(escapes[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04X}")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


class Dialect:
    def __init__(
        self,
        name: str,
        tags: dict,
        paragraph_separator: str = "\n\n",
        unknown_html: str = "keep",
        tag_case: str = "upper",
        source: str = "dialect",
    ) -> None:
        if not isinstance(name, str) or not name:
            raise DialectError(f"{source}: name must be non-empty text")
        if not isinstance(paragraph_separator, str):
            raise DialectError(f"{source}: paragraph_separator must be text")
        if unknown_html not in UNKNOWN_HTML:
            choices = " or ".join(f'"{choice}"' for choice in UNKNOWN_HTML)
            raise DialectError(f"{source}: unknown_html must be {choices}")
        if tag_case not in TAG_CASES:
            choices = " or ".join(f'"{choice}"' for choice in TAG_CASES)
            raise DialectError(f"{source}: tag_case must be {choices}")

        unknown = sorted(set(tags) - set(TAGS))
        if unknown:
            raise DialectError(f"{source}: unknown tag: tags.{unknown[0]}")
        missing = [key for key in TAGS if key not in tags]
        if missing:
            raise DialectError(f"{source}: missing tag: tags.{missing[0]}")

        for key, template in tags.items():
            if key != "heading":
                _check_template(key, template, source)

        self.name = name
        self.paragraph_separator = paragraph_separator
        self.unknown_html = unknown_html
        self.tag_case = tag_case
        self.tags = {key: tags[key] for key in TAGS if key != "heading"}
        self.headings = self._check_headings(tags["heading"], source)
        # Footnote links need matching anchors.
        self.has_anchors = any(field == "name" for _, field, _, _ in string.Formatter().parse(self.tags["anchor"]))

    @staticmethod
    def _check_headings(headings, source: str) -> dict:
        if not isinstance(headings, dict) or not headings:
            raise DialectError(f"{source}: tags.heading must list levels, like {{ 1 = \"[h1]{{text}}[/h1]\" }}")
        checked = {}
        for level, template in headings.items():
            if str(level) not in {str(n) for n in HEADING_LEVELS}:
                raise DialectError(f"{source}: tags.heading.{level}: level must be 1 to 6")
            _check_template(f"heading.{level}", template, source)
            checked[int(level)] = template
        if 1 not in checked:
            raise DialectError(f"{source}: tags.heading.1 is missing")
        return dict(sorted(checked.items()))

    def render(self, key: str, **values) -> str:
        return self.tags[key].format(**values)

    def heading(self, level: int, text: str) -> str:
        # Missing levels use the nearest lower number, e.g. level 4 uses 3.
        level = max(n for n in self.headings if n <= max(level, 1))
        return self.headings[level].format(text=text)

    def to_toml(self) -> str:
        lines = [
            "# Custom BBCode tags; use this file with --config.",
            "# Use \"{text}\" to drop a tag but keep its content.",
            f"name = {_toml_string(self.name)}",
            f"paragraph_separator = {_toml_string(self.paragraph_separator)}",
            "# HTML that has no BBCode: \"keep\" it as written or \"strip\" the tags.",
            f"unknown_html = {_toml_string(self.unknown_html)}",
            f"tag_case = {_toml_string(self.tag_case)}",
            "",
            "[tags]",
        ]
        for key in TAGS:
            if key == "heading":
                levels = ", ".join(f"{level} = {_toml_string(template)}" for level, template in self.headings.items())
                lines.append(f"heading = {{ {levels} }}")
            else:
                lines.append(f"{key} = {_toml_string(self.tags[key])}")
        return "\n".join(lines) + "\n"

    # loading

    @classmethod
    def defaults(cls, bb_codes=None, default_bb_codes=None) -> "Dialect":
        """The built-in tags. ``bb_codes`` is an export to read custom tags from, False for none."""
        if default_bb_codes is None and (bb_codes is None or bb_codes is False):
            return _default_dialect(bb_codes)
        return cls.from_dict(
            {}, source="settings", default_name=None,
            bb_codes=bb_codes, default_bb_codes=default_bb_codes,
        )

    @classmethod
    def load(cls, path, bb_codes=None, default_bb_codes=None) -> "Dialect":
        """Load a config, allowing bb_codes overrides."""
        path = os.fspath(path)
        try:
            with open(path, "rb") as handle:
                data = tomllib.load(handle)
        except FileNotFoundError as exc:
            raise DialectError(f"config file not found: {path}") from exc
        except OSError as exc:
            raise DialectError(f"cannot read config {path}: {exc.strerror or exc}") from exc
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
            raise DialectError(f"{path}: not valid TOML: {exc}") from exc

        default_name = os.path.splitext(os.path.basename(path))[0]
        return cls.from_dict(
            data, source=path, default_name=default_name,
            bb_codes=bb_codes, default_bb_codes=default_bb_codes, base_dir=os.path.dirname(path),
        )

    @classmethod
    def from_dict(
        cls,
        data: dict,
        source: str = "dialect",
        default_name: str = "custom",
        bb_codes=None,
        default_bb_codes=None,
        base_dir: str = None,
    ) -> "Dialect":
        """Merge tags in order: the built-in ones, the board's BB codes, then config overrides."""
        unknown = sorted(set(data) - _TOP_LEVEL_KEYS)
        if unknown:
            raise DialectError(f"{source}: unknown setting: {unknown[0]}")
        tags = data.get("tags", {})
        if not isinstance(tags, dict):
            raise DialectError(f"{source}: tags must be a [tags] section")

        base, bundled_codes = _load_defaults()
        tag_case = data.get("tag_case", base.tag_case)

        if bb_codes is None and "bb_codes" in data:
            bb_codes = data["bb_codes"]
            if bb_codes is not False and not isinstance(bb_codes, str):
                raise DialectError(f"{source}: bb_codes must be the path of a bb_codes.xml, or false for no custom tags")
            if bb_codes and base_dir:
                # Resolve export paths relative to the config file.
                bb_codes = os.path.join(base_dir, bb_codes)
        if bb_codes is None:
            # Nobody chose one: an export the caller came across, else the one we ship.
            bb_codes = default_bb_codes
        if bb_codes is None:
            custom = _bundled_custom_tags(bundled_codes, tag_case == "upper") if bundled_codes else {}
        else:
            custom = _custom_tags(os.fspath(bb_codes), tag_case == "upper") if bb_codes else {}

        merged = {**base.tags, "heading": dict(base.headings), **custom, **tags}
        if isinstance(tags.get("heading"), dict):
            # Keep heading levels not changed by the config.
            merged["heading"] = {**{str(level): t for level, t in base.headings.items()}, **tags["heading"]}

        return cls(
            name=data.get("name") or default_name or base.name,
            tags=merged,
            paragraph_separator=data.get("paragraph_separator", base.paragraph_separator),
            unknown_html=data.get("unknown_html", base.unknown_html),
            tag_case=tag_case,
            source=source,
        )


@functools.cache
def _load_defaults():
    """Read the built-in tags and the name of the export shipped with them."""
    data = tomllib.loads((resources.files("md2bbcode") / "dialects" / DEFAULTS_FILE).read_text(encoding="utf-8"))
    # The built-in file must define every tag.
    dialect = Dialect(
        name=data.get("name", "xenforo"),
        tags=data.get("tags", {}),
        paragraph_separator=data.get("paragraph_separator", "\n\n"),
        unknown_html=data.get("unknown_html", "keep"),
        tag_case=data.get("tag_case", "upper"),
        source=DEFAULTS_FILE,
    )
    return dialect, data.get("bb_codes") or None


@functools.cache
def _default_dialect(bb_codes) -> Dialect:
    return Dialect.from_dict({}, source="settings", default_name=None, bb_codes=bb_codes)


@functools.cache
def _bundled_custom_tags(file_name: str, upper: bool) -> dict:
    export = resources.files("md2bbcode") / "dialects" / file_name
    return tags_from_bb_codes(export.read_bytes(), upper)


def _custom_tags(path: str, upper: bool) -> dict:
    try:
        with open(path, "rb") as handle:
            return tags_from_bb_codes(handle.read(), upper)
    except FileNotFoundError as exc:
        raise DialectError(f"BB code export not found: {path}") from exc
    except OSError as exc:
        raise DialectError(f"cannot read BB code export {path}: {exc.strerror or exc}") from exc
    except ValueError as exc:
        raise DialectError(f"{path}: {exc}") from exc


def get_dialect(dialect=None) -> Dialect:
    """Accept a Dialect, or None for the built-in tags."""
    if dialect is None:
        return Dialect.defaults()
    if not isinstance(dialect, Dialect):
        raise DialectError(f"dialect must be a Dialect or None, not {type(dialect).__name__}; see Dialect.load()")
    return dialect
