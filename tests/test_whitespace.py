"""The renderer owns the space between blocks; no render method guesses what follows it."""

import pytest

from md2bbcode import Dialect
from md2bbcode import html_to_bbcode
from md2bbcode.main import convert


def test_two_paragraphs_are_separated_by_a_blank_line():
    assert convert("One.\n\nTwo.\n") == "One.\n\nTwo.\n"


@pytest.mark.parametrize(
    "markdown, expected",
    [
        ("Text.\n\n# Heading\n", "Text.\n[HEADING=1]Heading[/HEADING]\n"),
        ("# One\n\n# Two\n", "[HEADING=1]One[/HEADING]\n[HEADING=1]Two[/HEADING]\n"),
        ("Text.\n\n> Quoted.\n", "Text.\n[QUOTE]\nQuoted.\n[/QUOTE]\n"),
        ("> Quoted.\n\nText.\n", "[QUOTE]\nQuoted.\n[/QUOTE]\nText.\n"),
        ("Text.\n\n- a\n- b\n", "Text.\n[LIST][*]a\n[*]b\n[/LIST]\n"),
        ("Text.\n\n---\n\nText.\n", "Text.\n[HR][/HR]\nText.\n"),
    ],
)
def test_a_block_with_a_tag_of_its_own_only_takes_a_line(markdown, expected):
    # XenForo draws these as blocks already, so a blank line would only add a gap.
    assert convert(markdown) == expected


def test_a_nested_list_starts_on_its_own_line():
    assert convert("- a\n  - nested\n- b\n") == "[LIST][*]a\n[LIST][*]nested\n[/LIST]\n[*]b\n[/LIST]\n"


def test_blank_lines_inside_a_code_block_survive():
    assert convert("```\none\n\nthree\n```\n") == "[CODE]one\n\nthree\n[/CODE]\n"


def test_the_document_ends_with_one_newline():
    assert convert("Text.\n\n\n") == "Text.\n"
    assert convert("- a\n") == "[LIST][*]a\n[/LIST]\n"
    assert convert("") == ""


def test_the_separator_comes_from_the_dialect():
    tight = Dialect.from_dict({"paragraph_separator": "\n"})
    assert convert("One.\n\nTwo.\n", dialect=tight) == "One.\nTwo.\n"

    airy = Dialect.from_dict({"paragraph_separator": "\n\n\n"})
    assert convert("One.\n\nTwo.\n", dialect=airy) == "One.\n\n\nTwo.\n"


@pytest.mark.parametrize(
    "html",
    ["<p>a</p><p><br></p><p>b</p>", "<p>a</p><div><br></div><p>b</p>", "<div><p>a</p><br></div><p>b</p>"],
)
def test_a_standalone_break_takes_its_space_wherever_it_sits(html):
    assert html_to_bbcode(html) == "a\n\n\nb"


def test_only_newlines_are_trimmed_from_the_end_of_a_fragment():
    assert html_to_bbcode("<p>x&nbsp;</p>") == "x\xa0"


@pytest.mark.parametrize(
    "markdown, expected",
    [
        ('a\n\n<div style="color:red">x</div>\n\nb\n', "a\n\n[COLOR=red]x[/COLOR]\n\nb\n"),
        ('<div style="color:red"><p>one</p><p>two</p></div>\n\nafter\n', "[COLOR=red]one\n\ntwo[/COLOR]\n\nafter\n"),
        # Two tags from one style attribute: both close before the block's newline.
        (
            '<div align="center" style="color:red; font-weight:bold">x</div>\n',
            "[CENTER][COLOR=red][B]x[/B][/COLOR][/CENTER]\n",
        ),
    ],
)
def test_a_styled_block_is_spaced_like_a_plain_one(markdown, expected):
    # The colour is an inline tag around the block's content. v1.1.2 got this right.
    assert convert(markdown) == expected
    assert html_to_bbcode('<p>a</p><div style="color:red">x</div><p>b</p>') == "a\n\n[COLOR=red]x[/COLOR]\n\nb"


def test_a_break_at_the_end_of_an_inline_tag_stays_inside_it():
    # Only a tag around blocks is closed early; this one holds text and a break.
    assert convert("<b>bold<br></b> after\n") == "[B]bold\n[/B] after\n"


def test_html_and_markdown_blocks_are_spaced_the_same_way():
    assert html_to_bbcode("<p>One.</p><p>Two.</p>") == "One.\n\nTwo."
    assert html_to_bbcode("<p>Text.</p><blockquote>Quoted.</blockquote>") == "Text.\n[QUOTE]\nQuoted.\n[/QUOTE]"
