"""Heading anchors: a README's "#section" link has to find XenForo's own anchor."""

import pytest

from md2bbcode import Dialect
from md2bbcode.main import Converter, convert, convert_markdown_to_ast
from md2bbcode.plugins import github_slug, heading_anchors, xenforo_anchor


@pytest.mark.parametrize(
    "text, slug, anchor",
    [
        ("Getting Started", "getting-started", "-getting-started"),
        ("FAQ & Troubleshooting", "faq--troubleshooting", "-faq-troubleshooting"),
        ("Don't Panic", "dont-panic", "-dont-panic"),
        ("Hyphens-and_underscores 2.0", "hyphens-and_underscores-20", "-hyphens-and_underscores-2-0"),
        ("  Spaces  around  ", "--spaces--around--", "-spaces-around"),
        ("Café Münster", "café-münster", "-cafe-munster"),
        # Letters with nothing to decompose into; the board spells these from a table.
        ("Løsning", "løsning", "-losning"),
        ("Straße", "straße", "-strasse"),
        ("Æther", "æther", "-aether"),
        ("Łódź", "łódź", "-lodz"),
        # Curly quotes and dashes fold to ASCII first, then go the way ASCII ones do.
        ("Don’t Panic", "dont-panic", "-dont-panic"),
        ("Foo — Bar", "foo--bar", "-foo-bar"),
        ("“Quoted”", "quoted", "-quoted"),
        # GitHub drops an emoji; the board spells it out by its Unicode name (the emoji package).
        ("🚀 Getting Started", "-getting-started", "-rocket-getting-started"),
        ("Made with ❤ by us", "made-with--by-us", "-made-with-red-heart-by-us"),
        ("🇺🇸 Flags", "-flags", "-flag-united-states-flags"),
        ("", "", "-"),
    ],
)
def test_the_two_anchor_styles(text, slug, anchor):
    assert github_slug(text) == slug
    assert xenforo_anchor(text) == anchor


def test_a_repeated_heading_is_numbered_the_way_each_side_numbers_it():
    # GitHub starts at 1, XenForo at 2.
    tokens = convert_markdown_to_ast("# Repeat\n\n# Repeat\n\n# Repeat\n")
    assert heading_anchors(tokens) == {
        "repeat": "-repeat",
        "repeat-1": "-repeat-2",
        "repeat-2": "-repeat-3",
    }


def test_a_heading_inside_html_is_still_in_the_map():
    tokens = convert_markdown_to_ast("<div>\n\n## Inside a div\n\n</div>\n")
    assert heading_anchors(tokens) == {"inside-a-div": "-inside-a-div"}


def test_markdown_and_html_links_both_land_on_the_heading():
    markdown = '# Getting Started\n\n[md](#getting-started) <a href="#getting-started">html</a>\n'
    assert "[JUMPTO=-getting-started]md[/JUMPTO] [JUMPTO=-getting-started]html[/JUMPTO]" in convert(markdown)


def test_a_link_to_an_html_heading_lands_on_it():
    markdown = '<h2 align="center">Getting Started</h2>\n\n[go](#getting-started)\n'
    assert "[JUMPTO=-getting-started]go[/JUMPTO]" in convert(markdown)


def test_a_link_to_a_heading_with_an_emoji_lands_on_it():
    assert "[JUMPTO=-rocket-ship-it]x[/JUMPTO]" in convert("## 🚀 Ship It\n\n[x](#-ship-it)\n")


def test_a_link_to_a_heading_with_a_curly_apostrophe_lands_on_it():
    assert "[JUMPTO=-dont-panic]x[/JUMPTO]" in convert("## Don’t Panic\n\n[x](#dont-panic)\n")


def test_a_fragment_that_matches_no_heading_is_left_as_written():
    assert "[JUMPTO=nowhere]x[/JUMPTO]" in convert("# A heading\n\n[x](#nowhere)\n")


def test_a_stock_board_keeps_the_text_of_a_heading_link_and_drops_the_link():
    # XenForo has no tag for a link within a post: Url::getValidUrl turns down a target
    # that starts with "#", so [URL=#-one] would show as plain text anyway.
    stock = Dialect.defaults(bb_codes=False)
    assert convert("# One\n\n[a](#one)\n", dialect=stock) == "[HEADING=1]One[/HEADING]\na\n"


def test_footnotes_use_the_board_s_anchor_pair():
    # [JUMPTO] and [ANAME] are the board's own pair. Headings anchor themselves, so a
    # heading link needs only [JUMPTO]; a footnote needs both.
    result = convert("# Heading\n\nnote[^1]\n\n[^1]: Foot.\n")
    assert "[JUMPTO=fn-1]1[/JUMPTO]" in result
    assert "[ANAME=fn-1]1[/ANAME]" in result


def test_a_heading_link_inside_a_footnote_lands_on_the_heading():
    # Mistune renders footnotes in a second call, which has to see the same heading map.
    result = convert("# Getting Started\n\nnote[^1]\n\n[^1]: See [start](#getting-started).\n")
    assert "See [JUMPTO=-getting-started]start[/JUMPTO]." in result


def test_heading_anchors_none_leaves_every_fragment_alone():
    board = Dialect.from_dict({"heading_anchors": "none"})
    markdown = "# Getting Started\n\n[md](#getting-started)\n"
    assert "[JUMPTO=getting-started]md[/JUMPTO]" in convert(markdown, dialect=board)


def test_heading_anchors_is_a_setting_with_two_values():
    assert 'heading_anchors = "xenforo"' in Dialect.defaults().to_toml()
    with pytest.raises(Exception, match='heading_anchors must be "xenforo" or "none"'):
        Dialect.from_dict({"heading_anchors": "github"}, source="board.toml")


def test_a_reused_converter_does_not_keep_the_last_document_s_headings():
    converter = Converter()
    assert "[JUMPTO=-one]" in converter.markdown("# One\n\n[a](#one)\n")
    # No headings here, so the fragment has nothing to land on and stays as written.
    assert converter.markdown("[a](#one)\n") == "[JUMPTO=one]a[/JUMPTO]\n"
