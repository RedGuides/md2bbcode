"""Test the built-in tag settings, config overrides, and config errors."""

import re
import tomllib

import pytest

from md2bbcode import Dialect, convert
from md2bbcode.dialect import TAGS, DialectError

_TAG_NAME_RE = re.compile(r"\[/?([A-Za-z][A-Za-z0-9_-]*)")


def _dialect(toml_text: str, **kwargs) -> Dialect:
    return Dialect.from_dict(tomllib.loads(toml_text), source="board.toml", **kwargs)


def test_the_built_in_settings_define_every_tag():
    xenforo = Dialect.defaults()
    assert set(xenforo.tags) | {"heading"} == set(TAGS)


def test_every_tag_name_is_written_in_one_case():
    # Boards read BBCode case-insensitively, so either case would work, but mixing
    # them makes the output look accidental. Upper case matches XenForo's own
    # HTML-to-BBCode renderer and what its editor rewrites a post to on the first save.
    board = Dialect.defaults()
    templates = list(board.tags.values()) + list(board.headings.values())
    names = [name for template in templates for name in _TAG_NAME_RE.findall(template)]
    assert names, "no tags found, the regex is wrong"

    mixed = sorted({name for name in names if not name.isupper()} if names[0].isupper()
                   else {name for name in names if not name.islower()})
    assert not mixed, f"tag names are mixed case: {', '.join(mixed)}"


def test_issue_2_override_changes_markdown_and_html_code_spans():
    source = "Run `pip` then <code>hatch</code> or <kbd>Ctrl</kbd>."
    config = '[tags]\ncodespan = "[code]{text}[/code]"\n'
    # A key follows inline code, unless the board has a BB code for keys.
    stock = _dialect(config, bb_codes=False)
    assert convert(source, dialect=stock) == "Run [code]pip[/code] then [code]hatch[/code] or [code]Ctrl[/code].\n"
    assert convert(source, dialect=_dialect(config)) == "Run [code]pip[/code] then [code]hatch[/code] or [KBD]Ctrl[/KBD].\n"


def test_a_config_keeps_every_tag_it_does_not_name():
    board = _dialect('[tags]\nstrong = "[bold]{text}[/bold]"\n')
    assert convert("**a** *b*", dialect=board) == "[bold]a[/bold] [I]b[/I]\n"


def test_text_alone_drops_the_tag_and_keeps_the_content():
    board = _dialect('[tags]\nmark = "{text}"\nabbr = "{text}"\n')
    markdown = "==marked== and HTML\n\n*[HTML]: HyperText Markup Language\n"
    assert convert(markdown, dialect=board) == "marked and HTML\n"


def test_heading_levels_merge_and_deeper_levels_use_the_last_one_defined():
    board = _dialect('[tags]\nheading = { 1 = "[h1]{text}[/h1]" }\n')
    result = convert("# one\n\n## two\n\n##### five\n", dialect=board)
    assert result == "[h1]one[/h1]\n[HEADING=2]two[/HEADING]\n[HEADING=3]five[/HEADING]\n"


@pytest.mark.parametrize("tag", ["tt", "code_inline", "inline-code", "1code", "iCode"])
def test_renamed_code_tag_does_not_change_html_inside_code(tag):
    board = _dialect(f'[tags]\ncodespan = "[{tag}]{{text}}[/{tag}]"\n')
    assert convert("`<b>not bold</b>`", dialect=board) == f"[{tag}]<b>not bold</b>[/{tag}]\n"


def test_renamed_block_code_tag_does_not_change_html_inside_a_fenced_block():
    board = _dialect('[tags]\nblock_code_nolang = "[code_block]{text}[/code_block]"\n')
    markdown = "```\n<font color=\"red\">danger</font>\n<!-- keep me -->\n```\n"
    assert convert(markdown, dialect=board) == (
        "[code_block]<font color=\"red\">danger</font>\n<!-- keep me -->\n[/code_block]\n"
    )


def test_html_is_converted_inside_a_tag_that_shares_its_name_with_a_code_template():
    board = _dialect('[tags]\ncodespan = "[b][icode]{text}[/icode][/b]"\n')
    assert convert("**bold with <i>italic</i> inside** `<i>code</i>`", dialect=board) == (
        "[B]bold with [I]italic[/I] inside[/B] [b][icode]<i>code</i>[/icode][/b]\n"
    )


def test_html_inside_code_stays_as_written_even_with_the_code_tag_dropped():
    board = _dialect('[tags]\ncodespan = "{text}"\n')
    assert convert("`<b>not bold</b>` and <code>&lt;i&gt;</code>", dialect=board) == "<b>not bold</b> and <i>\n"


def test_every_html_tag_comes_from_the_dialect():
    board = _dialect(
        'paragraph_separator = "\\n"\n'
        "[tags]\n"
        'block_spoiler = "[hide={title}]{text}[/hide]"\n'
        'strong = "[bold]{text}[/bold]"\n'
        'font_color = "[c={color}]{text}[/c]"\n'
        'heading_link = "{text}"\n'
        'email = "[url=mailto:{address}]{text}[/url]"\n'
        'block_quote_author = "[quote={author}]{text}[/quote]"\n'
        'table_cell = "[cell]{text}[/cell]"\n'
    )
    html = "<details><summary>More</summary><p>one</p><p>two</p></details>"
    assert convert(html, dialect=board) == "[hide=More]\none\ntwo\n[/hide]\n"

    inline = '<b>b</b> <font color="red">r</font> <a href="#top">up</a> <a href="mailto:a@b.c">mail</a>'
    assert convert(inline, dialect=board) == "[bold]b[/bold] [c=red]r[/c] up [url=mailto:a@b.c]mail[/url]\n"

    blocks = '<blockquote data-author="Al">q</blockquote><table><tr><td>x</td></tr></table>'
    assert convert(blocks, dialect=board) == "[quote=Al]q\n[/quote]\n[TABLE]\n[TR]\n[cell]x[/cell]\n[/TR]\n[/TABLE]\n"


def test_unknown_html_is_kept_or_stripped():
    markdown = 'A <custom-tag data-x="1"><b>bold</b></custom-tag> and <b>never closed.\n\n<section>\n\nInside.\n\n</section>\n'
    assert convert(markdown) == (
        'A <custom-tag data-x="1">[B]bold[/B]</custom-tag> and <b>never closed.\n\n<section>\n\nInside.\n\n</section>\n'
    )

    board = _dialect('unknown_html = "strip"\n')
    assert convert(markdown, dialect=board) == "A [B]bold[/B] and never closed.\n\nInside.\n"
    assert 'unknown_html = "strip"' in board.to_toml()


def test_dumped_config_loads_back_to_the_same_dialect():
    board = _dialect('unknown_html = "strip"\n[tags]\nimage_options = "[img {options}]{url}[/img]"\nheading = { 4 = "[h4]{text}[/h4]" }\n')
    again = Dialect.from_dict(tomllib.loads(board.to_toml()), source="dump")
    assert (again.unknown_html, again.tags, again.headings, again.paragraph_separator) == (
        board.unknown_html, board.tags, board.headings, board.paragraph_separator,
    )


def test_literal_braces_are_written_doubled():
    board = _dialect('[tags]\nstrong = "{{b}}{text}{{/b}}"\n')
    assert convert("**x**", dialect=board) == "{b}x{/b}\n"


@pytest.mark.parametrize(
    "toml_text, expected",
    [
        ('[tags]\ncodspan = "[c]{text}[/c]"\n', "tags.codspan"),
        ('[tags]\ncodespan = "[c][/c]"\n', "tags.codespan must contain {text}"),
        ('[tags]\nlink = "[url={href}]{text}[/url]"\n', "tags.link: unknown placeholder {href}"),
        ('[tags]\nstrong = "{text.__class__}"\n', "tags.strong: unknown placeholder"),
        ('[tags]\nstrong = "{text!r}"\n', "tags.strong: unknown placeholder"),
        ('[tags]\nstrong = "{0}{text}"\n', "tags.strong: unknown placeholder"),
        ('[tags]\nstrong = "{text"\n', "tags.strong:"),
        ('[tags]\nstrong = 5\n', "tags.strong must be text"),
        ('[tags]\nheading = "[h]{text}[/h]"\n', "tags.heading must list levels"),
        ('[tags]\nheading = { 7 = "[h7]{text}[/h7]" }\n', "tags.heading.7"),
        ('[tags]\nheading = { 2 = "[h2][/h2]" }\n', "tags.heading.2 must contain {text}"),
        ('paragraph_seperator = "\\n"\n', "unknown setting: paragraph_seperator"),
        ('unknown_html = "drop"\n', 'unknown_html must be "keep" or "strip"'),
        ('[tags]\nemail = "[email]{addres}[/email]"\n', "tags.email: unknown placeholder {addres}"),
        ('extends = "xenforo"\n', "unknown setting: extends"),
        # Nothing ever read a dialect's name, so the setting went before it shipped.
        ('name = "board"\n', "unknown setting: name"),
    ],
)
def test_bad_config_names_the_file_and_the_key(toml_text, expected):
    with pytest.raises(DialectError) as excinfo:
        _dialect(toml_text)
    message = str(excinfo.value)
    assert expected in message
    assert "\n" not in message
    assert message.startswith("board.toml: ")


def test_load_reads_a_file(tmp_path):
    path = tmp_path / "myboard.toml"
    path.write_text('[tags]\ncodespan = "[c]{text}[/c]"\n', encoding="utf-8")
    board = Dialect.load(path)
    assert board.render("codespan", text="x") == "[c]x[/c]"


def test_load_explains_missing_and_broken_files(tmp_path):
    with pytest.raises(DialectError, match="config file not found"):
        Dialect.load(tmp_path / "missing.toml")
    broken = tmp_path / "broken.toml"
    broken.write_text("[tags\n", encoding="utf-8")
    with pytest.raises(DialectError, match="not valid TOML"):
        Dialect.load(broken)
