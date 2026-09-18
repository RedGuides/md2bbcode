"""Custom tags come from a board's XenForo BB code export (bb_codes.xml), and from nowhere else."""

import re
from pathlib import Path

import pytest

from md2bbcode import Dialect, process_readme
from md2bbcode import main as md2bbcode_main
from md2bbcode.bb_codes import tags_from_bb_codes
from md2bbcode.dialect import DialectError

FIXTURES = Path(__file__).parent / "fixtures"

# The addTag list in XF\BbCode\RuleSet, plus [*].
XENFORO_BUILT_IN = set(
    "b i u s color font size url email embed left center right justify indent heading hr img quote code "
    "icode php html list plain media spoiler ispoiler attach user table tr td th *".split()
)
_TAG_RE = re.compile(r"\[/?([A-Za-z*][A-Za-z0-9_]*)")

MARKDOWN = """
==marked== H<sub>2</sub>O E=mc<sup>2</sup> HTML <a href="#top">up</a> <a name="top">here</a> note[^1]

![pixel art](https://example.com/p.png)

> [!WARNING]
> Careful.

*[HTML]: HyperText Markup Language

[^1]: The footnote.
""".lstrip()


def _bb_code(name, replace_html="", has_option="no", mode="replace"):
    return (
        f'<bb_code bb_code_id="{name}" bb_code_mode="{mode}" has_option="{has_option}" title="{name}">'
        f"<replace_html><![CDATA[{replace_html}]]></replace_html></bb_code>"
    )


def _export(*bb_codes):
    return '<?xml version="1.0" encoding="utf-8"?>\n<bb_codes>' + "".join(bb_codes) + "</bb_codes>"


# A board that has some of the same tags as RedGuides under other names, and lacks the rest.
OTHER_BOARD = _export(
    _bb_code("highlight", "<mark>{text}</mark>"),
    _bb_code("goto", '<a href="#{option}" class="jump">{text}</a>', has_option="yes"),
    _bb_code("target", '<style>.t{color:red}</style>\n<a id="{option}">{text}</a>', has_option="yes"),
    _bb_code("tooltip", '<abbr title="{option}">{text}</abbr>', has_option="optional"),
    _bb_code("gallery", '<div class="gallery">{text}</div>'),
)


@pytest.fixture
def other_board(tmp_path):
    path = tmp_path / "bb_codes.xml"
    path.write_text(OTHER_BOARD, encoding="utf-8")
    return path


def test_the_redguides_export_supplies_every_custom_tag_of_the_default_output():
    assert tags_from_bb_codes((Path(md2bbcode_main.__file__).parent / "dialects" / "bb_codes.xml").read_bytes()) == {
        "admonition": "[ADMONITION={kind}]{text}[/ADMONITION]",
        "abbr": "[ABBR={title}]{text}[/ABBR]",
        "anchor": "[ANAME={name}]{text}[/ANAME]",
        "link_anchor": "[JUMPTO={anchor}]{text}[/JUMPTO]",
        "mark": "[MARK]{text}[/MARK]",
        "pixelate": "[PIXELATE]{text}[/PIXELATE]",
        "subscript": "[SUB]{text}[/SUB]",
        "superscript": "[SUP]{text}[/SUP]",
    }


def test_a_bb_code_is_recognised_by_its_html_whatever_it_is_called(other_board):
    board = Dialect.defaults(bb_codes=other_board)
    assert process_readme(MARKDOWN, dialect=board) == (
        "[HIGHLIGHT]marked[/HIGHLIGHT] H2O E=mc2 [TOOLTIP=HyperText Markup Language]HTML[/TOOLTIP] "
        "[GOTO=top]up[/GOTO] [TARGET=top]here[/TARGET] note[U][GOTO=fn-1]1[/GOTO][/U]\n\n"
        '[IMG alt="pixel art"]https://example.com/p.png[/IMG]\n\n'
        "[QUOTE][B]Warning:[/B] Careful.[/QUOTE]\n"
        "[B]Footnotes:[/B]\n[TARGET=fn-1]1[/TARGET]. The footnote.\n\n"
    )


def test_a_stock_board_gets_built_in_tags_only():
    stock = Dialect.defaults(bb_codes=False)
    assert process_readme(MARKDOWN, dialect=stock) == (
        "marked H2O E=mc2 HTML [URL=#top]up[/URL] here note[U]1[/U]\n\n"
        '[IMG alt="pixel art"]https://example.com/p.png[/IMG]\n\n'
        "[QUOTE][B]Warning:[/B] Careful.[/QUOTE]\n"
        "[B]Footnotes:[/B]\n1. The footnote.\n\n"
    )

    templates = list(stock.tags.values()) + list(stock.headings.values())
    custom = {name.lower() for template in templates for name in _TAG_RE.findall(template)} - XENFORO_BUILT_IN
    assert not custom, f"xenforo.toml names custom tags, which belong in bb_codes.xml: {sorted(custom)}"

    redguides = {"mark", "sub", "sup", "abbr", "aname", "jumpto", "admonition", "pixelate"}
    for fixture in FIXTURES.glob("*.md"):
        output = process_readme(fixture.read_text(encoding="utf-8"), dialect=stock)
        found = {name.lower() for name in _TAG_RE.findall(output)} & redguides
        assert not found, f"{fixture.name}: {sorted(found)}"


@pytest.mark.parametrize(
    "bb_codes, expected",
    [
        # It is the anchor, the thing a link lands on, that decides whether a footnote
        # number is linked. The link tag alone would only make a link that goes nowhere.
        ([], "note[U]1[/U]\n\n[B]Footnotes:[/B]\n1. Foot.\n\n"),
        (["link"], "note[U]1[/U]\n\n[B]Footnotes:[/B]\n1. Foot.\n\n"),
        (["anchor"], "note[U][URL=#fn-1]1[/URL][/U]\n\n[B]Footnotes:[/B]\n[TARGET=fn-1]1[/TARGET]. Foot.\n\n"),
        (["link", "anchor"], "note[U][GOTO=fn-1]1[/GOTO][/U]\n\n[B]Footnotes:[/B]\n[TARGET=fn-1]1[/TARGET]. Foot.\n\n"),
    ],
    ids=["neither", "link only", "anchor only", "both"],
)
def test_a_footnote_number_links_only_when_the_board_has_an_anchor(bb_codes, expected, tmp_path):
    available = {
        "link": _bb_code("goto", '<a href="#{option}">{text}</a>', has_option="yes"),
        "anchor": _bb_code("target", '<a name="{option}">{text}</a>', has_option="yes"),
    }
    path = tmp_path / "bb_codes.xml"
    path.write_text(_export(*(available[name] for name in bb_codes)), encoding="utf-8")
    # No [SUP] either, so the numbers below are bare and the links are easy to see.
    assert process_readme("note[^1]\n\n[^1]: Foot.\n", dialect=Dialect.defaults(bb_codes=path)) == expected


def test_tag_names_follow_the_case_of_the_settings(other_board):
    board = Dialect.from_dict({"tag_case": "lower"}, bb_codes=other_board)
    assert process_readme("==x==", dialect=board) == "[highlight]x[/highlight]\n\n"
    assert 'tag_case = "lower"' in board.to_toml()


@pytest.mark.parametrize(
    "bb_code",
    [
        # overrides of built-in tags, and tags md2bbcode has no use for
        _bb_code("hr", '<hr class="memberHeader-separator">'),
        _bb_code("b", "<b>{text}</b>"),
        _bb_code("gallery", '<div class="gallery">{text}</div>'),
        # more than a wrapper around {text}
        _bb_code("fancy", "<mark>{text}</mark><hr>"),
        _bb_code("fancy", "<mark>&raquo; {text}</mark>"),
        # we cannot give a highlight a colour, or an abbreviation no title
        _bb_code("highlight", "<mark>{text}</mark>", has_option="yes"),
        _bb_code("abbr", '<abbr title="{option}">{text}</abbr>', has_option="no"),
        _bb_code("tooltip", '<abbr title="Note: {option}">{text}</abbr>', has_option="yes"),
        # never a name we could not write safely
        _bb_code("ma{rk}", "<mark>{text}</mark>"),
    ],
)
def test_bb_codes_we_cannot_use_are_ignored(bb_code):
    assert tags_from_bb_codes(_export(bb_code)) == {}


def test_a_bb_code_with_html_that_says_nothing_is_recognised_by_name():
    export = _export(
        _bb_code("mark", '<span style="background: yellow">{text}</span>'),
        _bb_code("pixelate", mode="callback"),
        _bb_code("admonition", '<aside class="a--{option}">{text}</aside>', has_option="yes"),
    )
    assert tags_from_bb_codes(export, upper=False) == {
        "mark": "[mark]{text}[/mark]",
        "pixelate": "[pixelate]{text}[/pixelate]",
        "admonition": "[admonition={kind}]{text}[/admonition]",
    }


def test_the_first_bb_code_to_match_keeps_the_tag():
    export = _export(_bb_code("hl", "<mark>{text}</mark>"), _bb_code("mark", "<mark>{text}</mark>"))
    assert tags_from_bb_codes(export) == {"mark": "[HL]{text}[/HL]"}


def test_a_config_names_its_export_relative_to_itself_and_its_own_tags_win(other_board):
    config = other_board.parent / "board.toml"
    config.write_text('bb_codes = "bb_codes.xml"\n[tags]\nabbr = "{text} ({title})"\n', encoding="utf-8")
    markdown = "==x== HTML\n\n*[HTML]: HyperText Markup Language\n"
    assert process_readme(markdown, dialect=Dialect.load(config)) == (
        "[HIGHLIGHT]x[/HIGHLIGHT] HTML (HyperText Markup Language)\n\n"
    )
    # The caller's choice replaces the config's.
    assert process_readme(markdown, dialect=Dialect.load(config, bb_codes=False)) == (
        "x HTML (HyperText Markup Language)\n\n"
    )

    config.write_text("bb_codes = false\n", encoding="utf-8")
    assert process_readme("==x==", dialect=Dialect.load(config)) == "x\n\n"


def test_a_config_without_bb_codes_keeps_the_export_we_ship(tmp_path):
    config = tmp_path / "board.toml"
    config.write_text('[tags]\ncodespan = "[code]{text}[/code]"\n', encoding="utf-8")
    assert process_readme("==x== `y`", dialect=Dialect.load(config)) == "[MARK]x[/MARK] [code]y[/code]\n\n"


@pytest.mark.parametrize(
    "content, expected",
    [
        (None, "BB code export not found: "),
        ("<bb_codes><bb_code", "not valid XML"),
        ("<smilies></smilies>", "not a XenForo BB code export: expected <bb_codes>, found <smilies>"),
    ],
)
def test_a_bad_export_is_a_one_line_error(content, expected, tmp_path):
    path = tmp_path / "export.xml"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    with pytest.raises(DialectError) as excinfo:
        Dialect.defaults(bb_codes=path)
    assert expected in str(excinfo.value) and str(path) in str(excinfo.value)
    assert "\n" not in str(excinfo.value)


def test_bb_codes_setting_must_be_a_path_or_false():
    with pytest.raises(DialectError, match="board.toml: bb_codes must be the path"):
        Dialect.from_dict({"bb_codes": True}, source="board.toml")
    with pytest.raises(DialectError, match='tag_case must be "upper" or "lower"'):
        Dialect.from_dict({"tag_case": "title"}, source="board.toml")


# command line

@pytest.fixture
def readme(tmp_path):
    path = tmp_path / "in.md"
    path.write_text("==x== H<sub>2</sub>O\n", encoding="utf-8")
    return str(path)


@pytest.mark.parametrize("entry", [md2bbcode_main.main, md2bbcode_main.html2bbcode_main], ids=["md2bbcode", "html2bbcode"])
def test_bb_codes_options(entry, other_board, tmp_path, monkeypatch, capsys):
    page = tmp_path / "in.html"
    page.write_text("<mark>x</mark> H<sub>2</sub>O", encoding="utf-8")

    entry([str(page)])
    entry([str(page), "--bb-codes", str(other_board)])
    entry([str(page), "--no-custom-bbcode"])
    monkeypatch.setenv("MD2BBCODE_BB_CODES", str(other_board))
    entry([str(page)])
    entry([str(page), "--no-custom-bbcode"])

    out, _ = capsys.readouterr()
    assert out.split() == [
        "[MARK]x[/MARK]", "H[SUB]2[/SUB]O",
        "[HIGHLIGHT]x[/HIGHLIGHT]", "H2O",
        "x", "H2O",
        "[HIGHLIGHT]x[/HIGHLIGHT]", "H2O",
        "x", "H2O",
    ]


def test_an_export_in_the_current_folder_is_picked_up_unless_something_was_chosen(other_board, readme, tmp_path, monkeypatch, capsys):
    redguides = Path(md2bbcode_main.__file__).parent / "dialects" / "bb_codes.xml"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    chosen = elsewhere / "redguides.xml"
    chosen.write_bytes(redguides.read_bytes())
    config = elsewhere / "board.toml"
    config.write_text('bb_codes = "redguides.xml"\n', encoding="utf-8")
    plain_config = elsewhere / "plain.toml"
    plain_config.write_text('name = "plain"\n', encoding="utf-8")

    monkeypatch.chdir(other_board.parent)
    md2bbcode_main.main([readme])
    md2bbcode_main.main([readme, "--config", str(plain_config)])
    md2bbcode_main.main([readme, "--config", str(config)])
    md2bbcode_main.main([readme, "--bb-codes", str(chosen)])
    md2bbcode_main.main([readme, "--no-custom-bbcode"])

    out, _ = capsys.readouterr()
    assert out.split() == [
        "[HIGHLIGHT]x[/HIGHLIGHT]", "H2O",
        "[HIGHLIGHT]x[/HIGHLIGHT]", "H2O",
        "[MARK]x[/MARK]", "H[SUB]2[/SUB]O",
        "[MARK]x[/MARK]", "H[SUB]2[/SUB]O",
        "x", "H2O",
    ]


def test_the_python_api_never_looks_in_the_current_folder(other_board, monkeypatch):
    monkeypatch.chdir(other_board.parent)
    assert process_readme("==x==") == "[MARK]x[/MARK]\n\n"


def test_dump_config_shows_what_an_export_gave(other_board, capsys):
    md2bbcode_main.main(["--dump-config", "--bb-codes", str(other_board)])
    out, _ = capsys.readouterr()
    assert 'mark = "[HIGHLIGHT]{text}[/HIGHLIGHT]"' in out
    assert 'link_anchor = "[GOTO={anchor}]{text}[/GOTO]"' in out
    assert 'superscript = "{text}"' in out


def test_bad_bb_codes_options(readme, capsys):
    with pytest.raises(SystemExit) as excinfo:
        md2bbcode_main.main([readme, "--bb-codes", "no-such-export.xml"])
    assert excinfo.value.code == 1
    out, err = capsys.readouterr()
    assert out == "" and err == "BB code export not found: no-such-export.xml\n"

    with pytest.raises(SystemExit) as excinfo:
        md2bbcode_main.main([readme, "--bb-codes", "x.xml", "--no-custom-bbcode"])
    assert excinfo.value.code == 2
