"""HTML becomes tokens: pairing start and end tags across mistune's tokens."""

import time

import pytest

from md2bbcode import process_readme
from md2bbcode.html2bbcode import html_to_bbcode
from md2bbcode.main import convert_markdown_to_ast
from md2bbcode.plugins import html_events


def _types(tokens):
    """The shape of a token tree: (type, children) for parents, the type alone otherwise."""
    return [(t["type"], _types(t["children"])) if "children" in t else t["type"] for t in tokens]


# events

def test_events_list_tags_and_text_in_order_and_leave_comments_out():
    events = html_events('<p class="a">one<br/><!-- note -->two</p>')
    assert events == [
        ("start", "p", {"class": "a"}, '<p class="a">'),
        ("text", "one"),
        ("start", "br", {}, "<br/>"),
        ("text", "two"),
        ("end", "p"),
    ]


def test_events_keep_character_references_in_text_as_written():
    # The renderer decodes text once, so nothing may be decoded or "repaired" here.
    text = "AT&T &copy; &amp;lt; &#169; &foo bar &region=1"
    assert html_events(text) == [("text", text)]


def test_events_decode_attributes_but_only_references_that_end_in_a_semicolon():
    (_, _, attrs, raw), *_ = html_events('<a href="?a=1&region=US&amp;x=2&copy=3" title="&lt;T&gt;">')
    assert attrs == {"href": "?a=1&region=US&x=2&copy=3", "title": "<T>"}
    assert raw == '<a href="?a=1&region=US&amp;x=2&copy=3" title="&lt;T&gt;">'


@pytest.mark.parametrize("cut_off", ["<unclosed tag and more", "<b", "</b", '<a href="x>y <b>z</b>'])
def test_events_keep_a_tag_cut_off_by_the_end_of_the_input(cut_off):
    # html.parser drops these silently.
    assert html_events("before " + cut_off) == [("text", "before " + cut_off)]


def test_events_treat_a_self_closed_element_as_empty():
    assert [event[:2] for event in html_events('<a name="x"/>')] == [("start", "a"), ("end", "a")]


# pairing

def test_inline_pair_wraps_the_tokens_between_the_tags():
    assert _types(convert_markdown_to_ast("E=mc<sup>2</sup> and <b>bold with *emphasis* inside</b>.")) == [
        ("paragraph", [
            "text", ("superscript", ["text"]), "text",
            ("strong", ["text", ("emphasis", ["text"]), "text"]), "text",
        ]),
    ]
    assert process_readme("**bold with <i>html italic</i> inside**") == "[B]bold with [I]html italic[/I] inside[/B]\n\n"


def test_details_around_markdown_is_one_spoiler_with_the_summary_as_its_title():
    markdown = "<details>\n<summary>Title</summary>\n\nSome **markdown** inside.\n\n```\ncode\n```\n\n</details>\n"
    (spoiler,) = convert_markdown_to_ast(markdown)
    assert spoiler["type"] == "block_spoiler"
    assert spoiler["attrs"]["title"] == [{"type": "text", "raw": "Title"}]
    assert [t["type"] for t in spoiler["children"] if t["type"] != "blank_line"] == ["paragraph", "block_code"]
    assert process_readme(markdown) == "[SPOILER=Title]\nSome [B]markdown[/B] inside.\n\n[CODE]code\n[/CODE]\n[/SPOILER]\n"


def test_details_inside_a_list_item_stays_inside_it():
    markdown = "1. Step\n\n   <details>\n   <summary>More</summary>\n\n   Hidden.\n\n   </details>\n\n2. Next\n"
    (steps,) = convert_markdown_to_ast(markdown)
    first = [t["type"] for t in steps["children"][0]["children"] if t["type"] != "blank_line"]
    assert first == ["paragraph", "block_spoiler"]


def test_nested_details_nest():
    markdown = (
        "<details>\n<summary>Outer</summary>\n\nOuter body.\n\n"
        "<details>\n<summary>Inner</summary>\n\nInner body.\n\n</details>\n\nBack in outer.\n\n</details>\n"
    )
    assert process_readme(markdown) == (
        "[SPOILER=Outer]\nOuter body.\n\n[SPOILER=Inner]\nInner body.\n[/SPOILER]\nBack in outer.\n[/SPOILER]\n"
    )


def test_two_spoilers_back_to_back_share_a_token_and_are_still_two():
    # Mistune hands over '</details>\n<details>\n<summary>Two</summary>\n' as one block.
    markdown = "<details>\n<summary>One</summary>\n\nFirst.\n\n</details>\n<details>\n<summary>Two</summary>\n\nSecond.\n\n</details>\n"
    assert process_readme(markdown) == "[SPOILER=One]\nFirst.\n[/SPOILER]\n[SPOILER=Two]\nSecond.\n[/SPOILER]\n"


def test_summary_may_hold_markup_and_may_be_missing():
    assert html_to_bbcode("<details><summary><b>Bold</b> title</summary>Body.</details>") == (
        "[SPOILER=[B]Bold[/B] title]Body.[/SPOILER]"
    )
    assert html_to_bbcode("<details>Body.</details>") == "[SPOILER]Body.[/SPOILER]"


def test_an_unclosed_tag_loses_only_itself():
    markdown = "Before.\n\nA <b>bold that never closes and *emphasis*.\n\nA later paragraph.\n"
    assert process_readme(markdown) == "Before.\n\nA <b>bold that never closes and [I]emphasis[/I].\n\nA later paragraph.\n\n"


def test_an_unclosed_tag_in_prose_does_not_swallow_the_document():
    markdown = "Text with <unclosed tag and more.\n\nA later paragraph with <b>bold</b>.\n"
    assert process_readme(markdown) == "Text with <unclosed tag and more.\n\nA later paragraph with [B]bold[/B].\n\n"
    # The html2bbcode command has no Markdown paragraphs to contain the damage, only the parser's rules.
    assert html_to_bbcode("<p>Fine.</p><p>5 < 6 and a <b>bold</b> word</p>") == "Fine.\n\n5 < 6 and a [B]bold[/B] word"


def test_an_unclosed_details_gives_its_summary_back():
    assert process_readme("<details>\n<summary>Title</summary>\n\nBody.\n") == "<details>Title\n\nBody.\n\n"


def test_a_stray_end_tag_vanishes_if_we_know_the_tag_and_stays_if_we_do_not():
    assert process_readme("before </b> after, before </custom> after") == "before  after, before </custom> after\n\n"


def test_mis_nested_tags_close_cleanly():
    assert process_readme("<b><i>bold italic</b></i> end") == "[B][I]bold italic[/I][/B] end\n\n"


@pytest.mark.parametrize(
    "html, expected",
    [
        ("<ul><li>a<li>b</ul>", "[LIST][*]a\n[*]b\n[/LIST]"),
        ("<ul><li>a<ul><li>nested</ul><li>b</ul>", "[LIST][*]a[LIST][*]nested\n[/LIST]\n\n[*]b\n[/LIST]"),
        ("<table><tr><td>a<td>b<tr><th>c</table>", "[TABLE]\n[TR]\n[TD]a[/TD]\n[TD]b[/TD]\n[/TR]\n[TR]\n[TH]c[/TH]\n[/TR]\n[/TABLE]"),
        ("<table><thead><tr><th>h<tbody><tr><td>d</table>", "[TABLE]\n[TR]\n[TH]h[/TH]\n[/TR]\n[TR]\n[TD]d[/TD]\n[/TR]\n[/TABLE]"),
        ("<p>one<p>two", "one\n\ntwo"),
        ("<p>text<ul><li>item</ul>", "text\n\n[LIST][*]item\n[/LIST]"),
        ("<div><p>one</div>after", "one\n\nafter"),
    ],
)
def test_omitted_end_tags_give_siblings_not_nesting(html, expected):
    assert html_to_bbcode(html) == expected


def test_html_lists_match_markdown_lists():
    assert html_to_bbcode("<ul><li>a<ul><li>nested</ul><li>b</ul>") + "\n" == process_readme("- a\n  - nested\n- b\n")
    assert html_to_bbcode("<ol><li>a</li><li>b</li></ol>") + "\n" == process_readme("1. a\n2. b\n")


def test_an_end_tag_does_not_reach_outside_its_table_or_list():
    # The stray </td> inside the inner table must not close the outer cell.
    assert html_to_bbcode("<table><tr><td><table><tr><td>in</td></tr></td></table></td><td>b</td></tr></table>") == (
        "[TABLE]\n[TR]\n[TD][TABLE]\n[TR]\n[TD]in[/TD]\n[/TR]\n[/TABLE]\n[/TD]\n[TD]b[/TD]\n[/TR]\n[/TABLE]"
    )


def test_a_tag_we_cannot_use_stays_html_with_its_end_tag():
    assert process_readme('<abbr>no title</abbr>, <a>no href</a>, <img alt="no src">') == (
        '<abbr>no title</abbr>, <a>no href</a>, <img alt="no src">\n\n'
    )


def test_an_empty_anchor_is_an_anchor_not_an_unclosed_tag():
    assert process_readme('<a name="install"/>Install it.') == "[ANAME=install][/ANAME]Install it.\n\n"


def test_br_in_every_spelling():
    assert process_readme("one<br>two<br/>three<br />four") == "one\ntwo\nthree\nfour\n\n"


def test_html_in_a_footnote_is_paired_too():
    # Mistune renders footnotes separately, after the document.
    assert "1[/ANAME]. Water is H[SUB]2[/SUB]O" in process_readme("Water.[^1]\n\n[^1]: Water is H<sub>2</sub>O\n")


def test_document_wrappers_are_dropped_and_head_content_with_them():
    page = "<!DOCTYPE html><html><head><title>T</title><style>p{}</style></head><body><p>Hello</p><script>x()</script></body></html>"
    assert html_to_bbcode(page) == "Hello"


# whitespace

def test_whitespace_only_text_between_block_children_emits_nothing():
    html = '<p align="center">\n  <img src="https://example.com/logo.png" alt="logo">\n  <b>Title</b>\n</p>\n'
    assert process_readme(html) == '[CENTER][IMG alt="logo"]https://example.com/logo.png[/IMG] [B]Title[/B][/CENTER]\n\n'
    assert html_to_bbcode("<ul>\n  <li>One</li>\n  <li>Two</li>\n</ul>\n") == "[LIST][*]One\n[*]Two\n[/LIST]"


def test_other_whitespace_collapses_to_one_space_except_in_pre_and_code():
    assert html_to_bbcode("<p>one\n   two\t three</p>") == "one two three"
    assert html_to_bbcode("<pre>\none\n   two</pre>") == "[CODE]one\n   two[/CODE]"
    assert html_to_bbcode("<p><code>a   b</code></p>") == "[ICODE]a   b[/ICODE]"


def test_loose_inline_content_beside_blocks_gets_a_paragraph_of_its_own():
    assert html_to_bbcode("<div>loose text<p>a paragraph</p>more loose text</div>") == (
        "loose text\n\na paragraph\n\nmore loose text"
    )
    assert html_to_bbcode("<details><summary>T</summary>Intro.<pre>code</pre></details>") == (
        "[SPOILER=T]\nIntro.\n\n[CODE]code[/CODE]\n[/SPOILER]"
    )


def test_a_br_on_a_line_of_its_own_is_still_a_blank_line():
    assert process_readme("Above.\n\n<br>\n\nBelow.\n") == "Above.\n\n\nBelow.\n\n"


# entities

def test_entities_decode_once_in_prose_and_not_at_all_in_code():
    assert process_readme("&copy; 5 &lt; 6 &amp; AT&T, `&copy;`") == "© 5 < 6 & AT&T, [ICODE]&copy;[/ICODE]\n\n"
    assert process_readme("```\n&copy; in a code block\n```\n") == "[CODE]&copy; in a code block\n[/CODE]\n"


def test_entities_inside_html_decode_once_too():
    assert process_readme("<span>&amp;lt; and &copy;</span>") == "&lt; and ©\n\n"
    assert html_to_bbcode("<p>&amp;lt; and &copy;</p>") == "&lt; and ©"
    assert html_to_bbcode('<img src="a.png" alt="R&amp;D &amp;lt;">') == '[IMG alt="R&D &lt;"]a.png[/IMG]'


def test_html_code_holds_text_so_its_entities_are_decoded():
    assert html_to_bbcode("<code>&lt;b&gt;</code> and <pre>&lt;i&gt; &amp;amp;</pre>") == (
        "[ICODE]<b>[/ICODE] and\n\n[CODE]<i> &amp;[/CODE]"
    )


def test_a_query_string_is_not_read_as_an_entity():
    url = "https://example.com/?lang=en&region=US&copy=1"
    assert process_readme(f"<{url}>") == f"[URL={url}]{url}[/URL]\n\n"
    assert html_to_bbcode(f'<a href="{url}">{url}</a>') == f"[URL={url}]{url}[/URL]"


# scale

def test_pairing_time_scales_linearly():
    unit = (
        "<details>\n<summary>Title</summary>\n\nText with <b>bold</b>, <sup>sup</sup> and an <unclosed.\n\n</details>\n\n"
        '<p align="center"><img src="a.png"> <b>Title</b></p>\n\n<ul><li>one<li>two</ul>\n\n'
    )

    def timed(repeats):
        best = float("inf")
        for _ in range(3):
            started = time.perf_counter()
            process_readme(unit * repeats)
            best = min(best, time.perf_counter() - started)
        return best

    ratio = timed(800) / timed(200)
    assert ratio < 10.0, f"4x input took {ratio:.1f}x as long"
