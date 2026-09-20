"""Free text in a tag option must survive XenForo's parser, which reads a quoted option up to "]."""

from md2bbcode import Dialect, convert, html_to_bbcode
from md2bbcode.dialect import TAGS


def test_free_text_options_are_quoted_in_the_built_in_templates():
    # An unquoted option ends at the first ], which a title or alt text may contain.
    board = Dialect.defaults()
    assert board.tags["block_spoiler"] == '[SPOILER="{title}"]{text}[/SPOILER]'
    assert board.tags["block_quote_author"].startswith('[QUOTE="{author}"]')
    assert board.tags["abbr"] == '[ABBR="{title}"]{text}[/ABBR]'
    assert "title" in TAGS["block_spoiler"]
    # An image's options are written by the renderer, which quotes each one.
    assert html_to_bbcode('<img src="x.png" alt="a]b" width="20">') == '[IMG alt="a]b" width="20px"]x.png[/IMG]'


def test_a_spoiler_title_is_the_summary_as_plain_text():
    # XenForo shows the title as plain text, so [B] in it would show up literally.
    html = "<details><summary><b>Bold</b> title with <code>code</code> and [brackets]</summary>Body.</details>"
    assert html_to_bbcode(html) == '[SPOILER="Bold title with code and [brackets]"]Body.[/SPOILER]'


def test_quotes_and_line_breaks_in_an_option_are_replaced():
    html = '<details><summary>Say "hi"\nthere</summary>Body.</details>'
    assert html_to_bbcode(html) == '[SPOILER="Say \'hi\' there"]Body.[/SPOILER]'

    assert convert('![say "hi" there](x.png)\n') == '[IMG alt="say \'hi\' there"]x.png[/IMG]\n'
    assert html_to_bbcode('<img src="x.png" alt="line one&#10;line two">') == '[IMG alt="line one line two"]x.png[/IMG]'
    assert html_to_bbcode('<blockquote data-author="Bob &quot;B&quot; Smith">hi</blockquote>') == (
        "[QUOTE=\"Bob 'B' Smith\"]\nhi\n[/QUOTE]"
    )
    assert html_to_bbcode('<abbr title="Hyper]Text &quot;Markup&quot;">HTML</abbr>') == (
        "[ABBR=\"Hyper]Text 'Markup'\"]HTML[/ABBR]"
    )


def test_a_summary_that_cleans_to_nothing_gives_a_spoiler_without_a_title():
    assert html_to_bbcode("<details><summary> </summary>Body.</details>") == "[SPOILER]Body.[/SPOILER]"
