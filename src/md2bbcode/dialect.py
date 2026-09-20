"""BBCode tag settings: XenForo's own tags, plus the board's custom BB codes."""

import functools
import os
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
    "kbd": ("text",),
    "inline_quote": ("text",),
    "inline_spoiler": ("text",),
    "abbr": ("text", "title"),
    "link": ("text", "url"),
    # link_anchor and anchor are a matching pair, used for footnotes.
    "link_anchor": ("text", "anchor"),
    "anchor": ("text", "name"),
    # Links to a heading, which the forum software anchors itself.
    "heading_link": ("text", "anchor"),
    "email": ("text", "address"),
    "font_color": ("text", "color"),
    "font_size": ("text", "size"),
    "font_face": ("text", "face"),
    "image": ("url",),
    # {options} lists what the image has, from alt, width, height and align: alt="Logo" width="200px"
    "image_options": ("url", "options"),
    "pixelate": ("text",),
    "linebreak": (),
    # blocks
    "heading": ("text",),
    "thematic_break": (),
    "block_code": ("text", "lang"),
    "block_code_nolang": ("text",),
    "block_quote": ("text",),
    "block_quote_author": ("text", "author"),
    # For `> [!WARNING]`, {kind} is "warning" and {label} is "Warning".
    "admonition": ("text", "kind", "label"),
    "block_spoiler": ("text", "title"),
    "block_spoiler_notitle": ("text",),
    "caption": ("text",),
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

# How a "#section" link finds its heading.
HEADING_ANCHORS = ("xenforo", "none")

_TOP_LEVEL_KEYS = {"paragraph_separator", "unknown_html", "tag_case", "heading_anchors", "bb_codes", "tags"}


class DialectError(ValueError):
    """A config error that names the bad setting."""


def _check_choice(setting: str, value, choices, source: str) -> None:
    if value not in choices:
        listed = " or ".join(f'"{choice}"' for choice in choices)
        raise DialectError(f"{source}: {setting} must be {listed}")


def _placeholders(template: str) -> set:
    """Return the placeholder names used by a template."""
    names = set()
    for _literal, field, _spec, _conversion in string.Formatter().parse(template):
        if field is not None:
            names.add(field)
    return names


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
    """BBCode templates and settings, checked at construction so config errors fail before rendering."""

    def __init__(
        self,
        tags: dict,
        paragraph_separator: str = "\n\n",
        unknown_html: str = "keep",
        tag_case: str = "upper",
        heading_anchors: str = "xenforo",
        source: str = "dialect",
    ) -> None:
        if not isinstance(paragraph_separator, str):
            raise DialectError(f"{source}: paragraph_separator must be text")
        _check_choice("unknown_html", unknown_html, UNKNOWN_HTML, source)
        _check_choice("tag_case", tag_case, TAG_CASES, source)
        _check_choice("heading_anchors", heading_anchors, HEADING_ANCHORS, source)

        unknown = sorted(set(tags) - set(TAGS))
        if unknown:
            raise DialectError(f"{source}: unknown tag: tags.{unknown[0]}")
        missing = [key for key in TAGS if key not in tags]
        if missing:
            raise DialectError(f"{source}: missing tag: tags.{missing[0]}")

        for key, template in tags.items():
            if key != "heading":
                _check_template(key, template, source)

        self.paragraph_separator = paragraph_separator
        self.unknown_html = unknown_html
        self.tag_case = tag_case
        self.heading_anchors = heading_anchors
        self.tags = {key: tags[key] for key in TAGS if key != "heading"}
        self.headings = self._check_headings(tags["heading"], source)
        # Footnote links need matching anchors.
        self.has_anchors = "name" in _placeholders(self.tags["anchor"])

    @staticmethod
    def _check_headings(headings, source: str) -> dict:
        if not isinstance(headings, dict) or not headings:
            raise DialectError(f"{source}: tags.heading must list levels, like {{ 1 = \"[h1]{{text}}[/h1]\" }}")
        # TOML gives the levels as text ("1"); a dict built in Python may use numbers.
        allowed_levels = {str(number) for number in HEADING_LEVELS}
        checked = {}
        for level, template in headings.items():
            if str(level) not in allowed_levels:
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
        # Level 1 is always defined, so there is always one to fall back to.
        available = [number for number in self.headings if number <= level]
        return self.headings[max(available)].format(text=text)

    def to_toml(self) -> str:
        lines = [
            "# Custom BBCode tags; use this file with --config.",
            "# Use \"{text}\" to drop a tag but keep its content.",
            f"paragraph_separator = {_toml_string(self.paragraph_separator)}",
            "# HTML that has no BBCode: \"keep\" it as written or \"strip\" the tags.",
            f"unknown_html = {_toml_string(self.unknown_html)}",
            f"tag_case = {_toml_string(self.tag_case)}",
            '# Point "#section" links at the forum\'s own heading anchors, or "none" to leave them alone.',
            f"heading_anchors = {_toml_string(self.heading_anchors)}",
            "",
            "[tags]",
        ]
        for key in TAGS:
            if key == "heading":
                levels = ", ".join(f"{level} = {_toml_string(template)}" for level, template in self.headings.items())
                lines.append(f"heading = {{ {levels} }}")
            else:
                template = self.tags[key]
                unused = [f"{{{name}}}" for name in TAGS[key] if f"{{{name}}}" not in template]
                if unused:
                    lines.append(f"# {key} can also use {', '.join(unused)}")
                lines.append(f"{key} = {_toml_string(template)}")
        return "\n".join(lines) + "\n"

    # loading

    @classmethod
    def defaults(cls, bb_codes=None, default_bb_codes=None) -> "Dialect":
        """Load built-in tags, using ``bb_codes`` for a custom export or False to disable custom tags."""
        if default_bb_codes is None and (bb_codes is None or bb_codes is False):
            # Only bundled files are used here, so these defaults can be cached.
            return _default_dialect(bb_codes)
        return cls.from_dict({}, source="settings", bb_codes=bb_codes, default_bb_codes=default_bb_codes)

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

        return cls.from_dict(
            data, source=path,
            bb_codes=bb_codes, default_bb_codes=default_bb_codes, base_dir=os.path.dirname(path),
        )

    @classmethod
    def from_dict(
        cls,
        data: dict,
        source: str = "dialect",
        bb_codes=None,
        default_bb_codes=None,
        base_dir: str | None = None,
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

        # bb_codes is a path, False for no custom tags, or None for "not chosen yet".
        # Precedence: caller, config, default_bb_codes, then the bundled export.
        if bb_codes is None:
            bb_codes = _config_bb_codes(data, source, base_dir)
        if bb_codes is None:
            bb_codes = default_bb_codes

        upper = tag_case == "upper"
        if bb_codes is None:
            custom = _bundled_custom_tags(bundled_codes, upper) if bundled_codes else {}
        elif bb_codes:
            custom = _custom_tags(os.fspath(bb_codes), upper)
        else:
            # False, or an empty path: no custom tags.
            custom = {}

        merged = {**base.tags, "heading": dict(base.headings), **custom, **tags}
        if "kbd" not in custom and "kbd" not in tags:
            # Without a [KBD] BB code a key is shown as inline code, whatever the config makes of that.
            merged["kbd"] = merged["codespan"]
        if isinstance(tags.get("heading"), dict):
            # Keep heading levels not changed by the config. TOML keys are text, so ours become text too.
            levels = {}
            for level, template in base.headings.items():
                levels[str(level)] = template
            levels.update(tags["heading"])
            merged["heading"] = levels

        return cls(
            tags=merged,
            paragraph_separator=data.get("paragraph_separator", base.paragraph_separator),
            unknown_html=data.get("unknown_html", base.unknown_html),
            tag_case=tag_case,
            heading_anchors=data.get("heading_anchors", base.heading_anchors),
            source=source,
        )


@functools.cache
def _load_defaults():
    """Read the built-in tags, and which BB code export ships with them."""
    data = tomllib.loads((resources.files("md2bbcode") / "dialects" / DEFAULTS_FILE).read_text(encoding="utf-8"))
    # The built-in file must define every setting and every tag.
    dialect = Dialect(
        tags=data["tags"],
        paragraph_separator=data["paragraph_separator"],
        unknown_html=data["unknown_html"],
        tag_case=data["tag_case"],
        heading_anchors=data["heading_anchors"],
        source=DEFAULTS_FILE,
    )
    return dialect, data.get("bb_codes") or None


@functools.cache
def _default_dialect(bb_codes) -> Dialect:
    return Dialect.from_dict({}, source="settings", bb_codes=bb_codes)


def _config_bb_codes(data: dict, source: str, base_dir: str | None):
    """The export a config names: a path, False for none, or None if it does not say."""
    if "bb_codes" not in data:
        return None
    value = data["bb_codes"]
    if value is False:
        return False
    if not isinstance(value, str):
        raise DialectError(f"{source}: bb_codes must be the path of a bb_codes.xml, or false for no custom tags")
    if value and base_dir:
        # Resolve export paths relative to the config file.
        return os.path.join(base_dir, value)
    return value


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
    """Return a Dialect, using default tags and bundled custom BB codes for None."""
    if dialect is None:
        return Dialect.defaults()
    if not isinstance(dialect, Dialect):
        raise DialectError(f"dialect must be a Dialect or None, not {type(dialect).__name__}; see Dialect.load()")
    return dialect
