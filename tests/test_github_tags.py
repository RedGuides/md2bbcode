"""HTML that GitHub allows in a README should reach the forum as BBCode, not as raw tags."""

import pytest

from md2bbcode import Dialect, convert, html_to_bbcode

# GitHub does not publish its list of allowed tags. This is the closest public one: the
# html-pipeline gem, which GitHub's sanitizer grew out of. To update it, copy "elements" from
# https://github.com/gjtorikian/html-pipeline/blob/main/lib/html_pipeline/sanitization_filter.rb
# and the test below names any tag that still needs converting.
GITHUB_TAGS = [
    "h1", "h2", "h3", "h4", "h5", "h6", "br", "b", "i", "strong", "em", "a", "pre", "code", "img", "tt",
    "div", "ins", "del", "sup", "sub", "p", "picture", "ol", "ul", "table", "thead", "tbody", "tfoot",
    "blockquote", "dl", "dt", "dd", "kbd", "q", "samp", "var", "hr", "ruby", "rt", "rp", "li", "tr", "td",
    "th", "s", "strike", "summary", "details", "caption", "figure", "figcaption", "abbr", "bdo", "cite",
    "dfn", "mark", "small", "source", "span", "time", "wbr",
]

# Tags that need an attribute or a parent to mean anything. The rest are tried as <tag>x</tag>.
SAMPLES = {
    "a": '<a href="https://example.com/">x</a>',
    "abbr": '<abbr title="extra">x</abbr>',
    "br": "x<br>",
    "hr": "x<hr>",
    "wbr": "x<wbr>",
    "img": '<img src="x.png">',
    "source": '<picture><source srcset="dark.png"><img src="x.png"></picture>',
    "li": "<ul><li>x</li></ul>",
    "dt": "<dl><dt>x</dt></dl>",
    "dd": "<dl><dd>x</dd></dl>",
    "rt": "<ruby><rt>x</rt></ruby>",
    "rp": "<ruby><rp>x</rp></ruby>",
    "summary": "<details><summary>x</summary>body</details>",
    "figcaption": "<figure><figcaption>x</figcaption></figure>",
    "caption": "<table><caption>x</caption><tr><td>cell</td></tr></table>",
    "thead": "<table><thead><tr><th>x</th></tr></thead></table>",
    "tbody": "<table><tbody><tr><td>x</td></tr></tbody></table>",
    "tfoot": "<table><tfoot><tr><td>x</td></tr></tfoot></table>",
    "tr": "<table><tr><td>x</td></tr></table>",
    "td": "<table><tr><td>x</td></tr></table>",
    "th": "<table><tr><th>x</th></tr></table>",
}


@pytest.mark.parametrize("tag", GITHUB_TAGS)
def test_every_tag_github_allows_is_converted(tag):
    result = html_to_bbcode(SAMPLES.get(tag, f"<{tag}>x</{tag}>"))
    assert "<" not in result, f"<{tag}> is left in the post as HTML"
    assert "x" in result, f"<{tag}> lost its content"


def test_a_picture_keeps_only_its_img():
    html = (
        "<picture>\n"
        '  <source media="(prefers-color-scheme: dark)" srcset="dark.png">\n'
        '  <source media="(prefers-color-scheme: light)" srcset="light.png">\n'
        '  <img alt="Logo" src="light.png">\n'
        "</picture>\n"
    )
    assert convert(html) == '[IMG alt="Logo"]light.png[/IMG]\n'
    assert convert(f'<p align="center">{html}</p>\n') == '[CENTER][IMG alt="Logo"]light.png[/IMG][/CENTER]\n'


def test_a_source_outside_a_picture_stays_as_written():
    html = '<video controls><source src="a.mp4" type="video/mp4">Fallback.</video>'
    assert html_to_bbcode(html) == html


@pytest.mark.parametrize(
    "markdown",
    [
        "![Logo](light.png#gh-light-mode-only)\n![Logo](dark.png#gh-dark-mode-only)\n",
        "![Logo](dark.png#gh-dark-mode-only)\n![Logo](light.png#gh-light-mode-only)\n",
        '<img alt="Logo" src="dark.png#gh-dark-mode-only"><img alt="Logo" src="light.png#gh-light-mode-only">\n',
    ],
)
def test_of_a_light_and_dark_pair_only_the_light_image_is_posted(markdown):
    assert convert(markdown) == '[IMG alt="Logo"]light.png[/IMG]\n'


def test_a_link_around_a_dark_mode_image_goes_with_it():
    markdown = (
        "[![Logo](light.png#gh-light-mode-only)](https://example.com/)\n"
        "[![Logo](dark.png#gh-dark-mode-only)](https://example.com/)\n"
    )
    assert convert(markdown) == '[URL=https://example.com/][IMG alt="Logo"]light.png[/IMG][/URL]\n'


def test_any_other_fragment_stays_on_an_image_url():
    assert convert("![](chart.png#zoom)\n") == "[IMG]chart.png#zoom[/IMG]\n"


@pytest.mark.parametrize(
    "img, expected",
    [
        ('<img src="x.png" width="200">', '[IMG width="200px"]x.png[/IMG]'),
        ('<img src="x.png" width="200px" height="50">', '[IMG width="200px" height="50px"]x.png[/IMG]'),
        ('<img src="x.png" width="50%">', '[IMG width="50%"]x.png[/IMG]'),
        ('<img src="x.png" style="width: 120px; height: auto">', '[IMG width="120px"]x.png[/IMG]'),
        ('<img src="x.png" align="right" alt="Logo">', '[IMG alt="Logo" align="right"]x.png[/IMG]'),
        ('<img src="x.png" style="float: left">', '[IMG align="left"]x.png[/IMG]'),
        # XenForo takes px and % only, and floats an image left or right only.
        ('<img src="x.png" width="10em" height="auto" align="middle">', "[IMG]x.png[/IMG]"),
        ('<img src="x.png" width="200]">', "[IMG]x.png[/IMG]"),
    ],
)
def test_an_image_keeps_its_size_and_alignment(img, expected):
    assert html_to_bbcode(img) == expected


def test_a_config_can_leave_image_options_out():
    board = Dialect.from_dict({"tags": {"image_options": "[img]{url}[/img]"}})
    assert html_to_bbcode('<img src="x.png" alt="Logo" width="200">', dialect=board) == "[img]x.png[/img]"


def test_simple_inline_tags():
    assert html_to_bbcode("<tt>a</tt> <samp>b</samp>") == "[ICODE]a[/ICODE] [ICODE]b[/ICODE]"
    assert html_to_bbcode("<var>x</var> <cite>Book</cite> <dfn>term</dfn>") == "[I]x[/I] [I]Book[/I] [I]term[/I]"
    assert html_to_bbcode("She said <q>hello <b>there</b></q>.") == "She said “hello [B]there[/B]”."
    assert html_to_bbcode("<small>fine print</small>") == "[SIZE=3]fine print[/SIZE]"


def test_tags_without_a_bbcode_keep_their_text():
    html = 'On <time datetime="2024-01-01">New Year</time> super<wbr>long <bdo dir="rtl">text</bdo>'
    assert html_to_bbcode(html) == "On New Year superlong text"
    assert html_to_bbcode("<ruby>漢<rp>(</rp><rt>kan</rt><rp>)</rp></ruby>") == "漢(kan)"


def test_an_html_definition_list_matches_the_markdown_one():
    html = "<dl>\n<dt>Term</dt>\n<dd>First</dd>\n<dd>Second <b>bold</b></dd>\n<dt>Other\n<dd>More\n</dl>\n"
    markdown = "Term\n: First\n: Second **bold**\n\nOther\n: More\n"
    assert convert(html) == convert(markdown) == (
        "[B]Term[/B] :\n"
        "[INDENT]First[/INDENT]\n"
        "[INDENT]Second [B]bold[/B][/INDENT]\n"
        "[B]Other[/B] :\n"
        "[INDENT]More[/INDENT]\n"
    )


def test_a_figure_caption_goes_under_the_image():
    html = '<figure>\n<img src="a.png" alt="A">\n<figcaption>The <i>caption</i></figcaption>\n</figure>\n\nNext.\n'
    assert convert(html) == '[IMG alt="A"]a.png[/IMG]\nThe [I]caption[/I]\n\nNext.\n'


def test_a_table_caption_goes_above_the_table():
    html = "<table>\n<caption>Table 1</caption>\n<tr><th>A</th></tr>\n<tr><td>1</td></tr>\n</table>\n"
    assert convert(html) == "Table 1\n[TABLE]\n[TR]\n[TH]A[/TH]\n[/TR]\n[TR]\n[TD]1[/TD]\n[/TR]\n[/TABLE]\n"


def test_a_caption_outside_a_table_and_an_unclosed_table_stay_as_written():
    assert html_to_bbcode("<caption>x</caption>") == "<caption>x</caption>"
    unclosed = "<table><caption>Table 1</caption><tr><td>1</td></tr>"
    assert html_to_bbcode(unclosed) == "Table 1\n\n<table>\n[TR]\n[TD]1[/TD]\n[/TR]"


def test_emoji_shortcodes_become_emoji_outside_code():
    assert convert(":rocket: Launch :+1: `:rocket:`\n") == "🚀 Launch 👍 [ICODE]:rocket:[/ICODE]\n"
    assert html_to_bbcode("<b>:tada:</b> <code>:tada:</code>") == "[B]🎉[/B] [ICODE]:tada:[/ICODE]"
    # Colons that are not shortcodes, and names that are not emoji.
    unchanged = "At 10:30:45, a:b:c, :not_an_emoji: and C::std\n"
    assert convert(unchanged) == unchanged


def test_a_heading_with_a_shortcode_is_linked_by_the_name_the_board_gives_the_emoji():
    # GitHub's slug keeps the shortcode's name; XenForo names the emoji it is shown.
    result = convert("[go](#1-done)\n\n## :+1: Done\n")
    assert result == "[JUMPTO=-thumbs-up-done]go[/JUMPTO]\n[HEADING=2]👍 Done[/HEADING]\n"

