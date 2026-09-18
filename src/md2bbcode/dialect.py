"""BBCode tag settings for each forum."""

import functools
import os
import re
import string
import tomllib
from importlib import resources

DEFAULT_PRESET = "xenforo"

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
    "admonition": ("text", "kind"),
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
    # footnotes
    "footnote_ref": ("index",),
    "footnotes": ("text",),
    "footnote_item": ("text", "index"),
}

HEADING_LEVELS = range(1, 7)

_TOP_LEVEL_KEYS = {"name", "extends", "paragraph_separator", "tags"}
_PRESET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
# Custom tag names can include digits, underscores and hyphens.
_OPENING_TAG_RE = re.compile(r"\[([a-z0-9][a-z0-9_-]*)", re.IGNORECASE)


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

    if "text" in allowed and "text" not in used:
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
    def __init__(self, name: str, tags: dict, paragraph_separator: str = "\n\n", source: str = "dialect") -> None:
        if not isinstance(name, str) or not name:
            raise DialectError(f"{source}: name must be non-empty text")
        if not isinstance(paragraph_separator, str):
            raise DialectError(f"{source}: paragraph_separator must be text")

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
        self.tags = {key: tags[key] for key in TAGS if key != "heading"}
        self.headings = self._check_headings(tags["heading"], source)

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

    def code_tag_names(self) -> set:
        """Find the innermost code tag in each code template."""
        names = set()
        for key in ("codespan", "block_code", "block_code_nolang"):
            before_content = self.tags[key].split("{text}", 1)[0]
            open_tags = _OPENING_TAG_RE.findall(before_content)
            if open_tags:
                names.add(open_tags[-1].lower())
        return names

    def to_toml(self) -> str:
        lines = [
            "# Custom BBCode tags; use this file with --config.",
            "# Use \"{text}\" to drop a tag but keep its content.",
            f"name = {_toml_string(self.name)}",
            f"paragraph_separator = {_toml_string(self.paragraph_separator)}",
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
    def presets(cls) -> list:
        folder = resources.files("md2bbcode") / "dialects"
        return sorted(entry.name.removesuffix(".toml") for entry in folder.iterdir() if entry.name.endswith(".toml"))

    @classmethod
    def preset(cls, name: str = DEFAULT_PRESET) -> "Dialect":
        """Load a built-in forum preset."""
        return _load_preset(name)

    @classmethod
    def load(cls, path, preset: str = None) -> "Dialect":
        """Load a config file, using ``preset`` instead of its ``extends`` if given."""
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
        return cls.from_dict(data, source=path, preset=preset, default_name=default_name)

    @classmethod
    def from_dict(cls, data: dict, source: str = "dialect", preset: str = None, default_name: str = "custom") -> "Dialect":
        """Fill missing config settings from a preset."""
        unknown = sorted(set(data) - _TOP_LEVEL_KEYS)
        if unknown:
            raise DialectError(f"{source}: unknown setting: {unknown[0]}")
        tags = data.get("tags", {})
        if not isinstance(tags, dict):
            raise DialectError(f"{source}: tags must be a [tags] section")
        extends = preset or data.get("extends", DEFAULT_PRESET)
        if not isinstance(extends, str):
            raise DialectError(f"{source}: extends must name a preset")

        base = _load_preset(extends)
        merged = {**base.tags, "heading": dict(base.headings), **tags}
        if isinstance(tags.get("heading"), dict):
            # Keep heading levels not changed by the config.
            merged["heading"] = {**{str(level): t for level, t in base.headings.items()}, **tags["heading"]}

        return cls(
            name=data.get("name", default_name),
            tags=merged,
            paragraph_separator=data.get("paragraph_separator", base.paragraph_separator),
            source=source,
        )


@functools.cache
def _load_preset(name: str) -> Dialect:
    if not isinstance(name, str) or not _PRESET_NAME_RE.match(name):
        raise DialectError(f"unknown preset: {name!r} (available: {', '.join(Dialect.presets())})")
    preset_file = resources.files("md2bbcode") / "dialects" / f"{name}.toml"
    if not preset_file.is_file():
        raise DialectError(f"unknown preset: {name!r} (available: {', '.join(Dialect.presets())})")

    source = f"preset {name}"
    data = tomllib.loads(preset_file.read_text(encoding="utf-8"))
    # Presets must define every tag.
    return Dialect(
        name=data.get("name", name),
        tags=data.get("tags", {}),
        paragraph_separator=data.get("paragraph_separator", "\n\n"),
        source=source,
    )


def get_dialect(dialect=None) -> Dialect:
    """Accept a Dialect, the name of a preset, or None for the default."""
    if isinstance(dialect, Dialect):
        return dialect
    return Dialect.preset(dialect or DEFAULT_PRESET)
