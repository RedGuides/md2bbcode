"""Test forum presets, custom tags, and config errors."""

import tomllib

import pytest

from md2bbcode import Dialect, process_readme
from md2bbcode.dialect import TAGS, DialectError


def _dialect(toml_text: str, **kwargs) -> Dialect:
    return Dialect.from_dict(tomllib.loads(toml_text), source="board.toml", **kwargs)


def test_xenforo_is_the_default_and_defines_every_tag():
    xenforo = Dialect.preset()
    assert xenforo.name == "xenforo"
    assert set(xenforo.tags) | {"heading"} == set(TAGS)
    assert "xenforo" in Dialect.presets()


def test_issue_2_override_changes_markdown_and_html_code_spans():
    board = _dialect('extends = "xenforo"\n[tags]\ncodespan = "[code]{text}[/code]"\n')
    result = process_readme("Run `pip` then <code>hatch</code> or <kbd>Ctrl</kbd>.", dialect=board)
    assert result == "Run [code]pip[/code] then [code]hatch[/code] or [code]Ctrl[/code].\n\n"


def test_extends_defaults_to_xenforo_and_keeps_every_other_tag():
    board = _dialect('[tags]\nstrong = "[bold]{text}[/bold]"\n')
    assert process_readme("**a** *b*", dialect=board) == "[bold]a[/bold] [i]b[/i]\n\n"


def test_text_alone_drops_the_tag_and_keeps_the_content():
    board = _dialect('[tags]\nmark = "{text}"\nabbr = "{text}"\n')
    markdown = "==marked== and HTML\n\n*[HTML]: HyperText Markup Language\n"
    assert process_readme(markdown, dialect=board) == "marked and HTML\n\n"


def test_heading_levels_merge_and_deeper_levels_use_the_last_one_defined():
    board = _dialect('[tags]\nheading = { 1 = "[h1]{text}[/h1]" }\n')
    result = process_readme("# one\n\n## two\n\n##### five\n", dialect=board)
    assert result == "[h1]one[/h1]\n[HEADING=2]two[/HEADING]\n[HEADING=3]five[/HEADING]\n"


@pytest.mark.parametrize("tag", ["tt", "code_inline", "inline-code", "1code", "iCode"])
def test_renamed_code_tag_still_protects_html_inside_code(tag):
    # Renaming a code tag must not change the HTML inside it.
    board = _dialect(f'[tags]\ncodespan = "[{tag}]{{text}}[/{tag}]"\n')
    assert board.code_tag_names() == {"code", tag.lower()}
    assert process_readme("`<b>not bold</b>`", dialect=board) == f"[{tag}]<b>not bold</b>[/{tag}]\n\n"


def test_renamed_block_code_tag_still_protects_html_inside_a_fenced_block():
    board = _dialect('[tags]\nblock_code_nolang = "[code_block]{text}[/code_block]"\n')
    markdown = "```\n<font color=\"red\">danger</font>\n<!-- keep me -->\n```\n"
    assert process_readme(markdown, dialect=board) == (
        "[code_block]<font color=\"red\">danger</font>\n<!-- keep me -->\n[/code_block]\n"
    )


def test_a_wrapped_code_template_protects_the_inner_tag_not_the_wrapper():
    # Protect [icode], not [b], so HTML in bold text still gets converted.
    board = _dialect('[tags]\ncodespan = "[b][icode]{text}[/icode][/b]"\n')
    assert board.code_tag_names() == {"code", "icode"}
    assert process_readme("**bold with <i>italic</i> inside**", dialect=board) == (
        "[b]bold with [I]italic[/I] inside[/b]\n\n"
    )


def test_a_dropped_code_tag_contributes_no_plain_tag():
    board = _dialect('[tags]\ncodespan = "{text}"\n')
    assert board.code_tag_names() == {"code"}


def test_spoiler_and_paragraph_settings_reach_the_html_pass():
    board = _dialect(
        'paragraph_separator = "\\n"\n'
        '[tags]\nblock_spoiler = "[hide={title}]{text}[/hide]"\n'
    )
    html = "<details><summary>More</summary><p>one</p><p>two</p></details>"
    assert process_readme(html, dialect=board).strip() == "[hide=More]one\ntwo\n[/hide]"


def test_dumped_config_loads_back_to_the_same_dialect():
    board = _dialect('name = "board"\n[tags]\nimage_alt = "[img=\\"{alt}\\"]{url}[/img]"\nheading = { 4 = "[h4]{text}[/h4]" }\n')
    again = Dialect.from_dict(tomllib.loads(board.to_toml()), source="dump")
    assert (again.name, again.tags, again.headings, again.paragraph_separator) == (
        board.name, board.tags, board.headings, board.paragraph_separator,
    )


def test_literal_braces_are_written_doubled():
    board = _dialect('[tags]\nstrong = "{{b}}{text}{{/b}}"\n')
    assert process_readme("**x**", dialect=board) == "{b}x{/b}\n\n"


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
        ('extends = "phpbb9"\n', "unknown preset: 'phpbb9' (available: "),
        ('extends = "../secrets"\n', "unknown preset"),
    ],
)
def test_bad_config_names_the_file_and_the_key(toml_text, expected):
    with pytest.raises(DialectError) as excinfo:
        _dialect(toml_text)
    message = str(excinfo.value)
    assert expected in message
    assert "\n" not in message
    if "preset" not in expected:
        assert message.startswith("board.toml: ")


def test_load_reads_a_file_and_preset_argument_replaces_extends(tmp_path):
    path = tmp_path / "myboard.toml"
    path.write_text('extends = "nope"\n[tags]\ncodespan = "[c]{text}[/c]"\n', encoding="utf-8")
    board = Dialect.load(path, preset="xenforo")
    assert board.name == "myboard"
    assert board.render("codespan", text="x") == "[c]x[/c]"


def test_load_explains_missing_and_broken_files(tmp_path):
    with pytest.raises(DialectError, match="config file not found"):
        Dialect.load(tmp_path / "missing.toml")
    broken = tmp_path / "broken.toml"
    broken.write_text("[tags\n", encoding="utf-8")
    with pytest.raises(DialectError, match="not valid TOML"):
        Dialect.load(broken)
