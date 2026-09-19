from md2bbcode.main import convert
from md2bbcode import html_to_bbcode


def test_html_basic_formatting_and_links():
    markdown = (
        "<b>bold</b> <i>italic</i> <u>under</u> <s>strike</s> "
        "<ins>insert</ins> <mark>mark</mark> <kbd>kbd</kbd><br>"
        "<a href=\"https://example.com\">link</a> "
        "<img src=\"https://example.com/x.png\" alt=\"alt text\">"
        "<hr>"
    )
    result = convert(markdown, domain="")
    lowered = result.lower()

    assert "[b]bold[/b]" in lowered
    assert "[i]italic[/i]" in lowered
    assert "[u]under[/u]" in lowered
    assert "[s]strike[/s]" in lowered
    assert "[u]insert[/u]" in lowered
    assert "[mark]mark[/mark]" in lowered
    assert "[icode]kbd[/icode]" in lowered
    assert "[url=https://example.com]link[/url]" in lowered
    assert "[img alt=\"alt text\"]https://example.com/x.png[/img]" in lowered
    assert "[hr][/hr]" in lowered


def test_html_code_blocks_and_inline_code():
    markdown = (
        "<pre><code class=\"language-python\">print('hi')</code></pre>"
        " and <code>inline</code>"
    )
    result = convert(markdown, domain="")
    lowered = result.lower()

    assert "[code=python]print('hi')[/code]" in lowered
    assert "[icode]inline[/icode]" in lowered


def test_html_lists_and_tables():
    markdown = (
        "<ul><li>One</li><li>Two</li></ul>"
        "<ol><li>First</li><li>Second</li></ol>"
        "<table>"
        "<tr><th>H</th><th>H2</th></tr>"
        "<tr><td>A</td><td>B</td></tr>"
        "</table>"
    )
    result = convert(markdown, domain="")
    lowered = result.lower()

    assert "[list]" in lowered
    assert "[*]one" in lowered
    assert "[*]two" in lowered
    assert "[list=1]" in lowered
    assert "[*]first" in lowered
    assert "[*]second" in lowered
    assert "[table]" in lowered
    assert "[tr]" in lowered
    assert "[th]h[/th]" in lowered
    assert "[td]a[/td]" in lowered


def test_html_anchor_and_abbr():
    markdown = (
        "<a name=\"section\">Target</a> "
        "<a href=\"#section\">Jump</a> "
        "<abbr title=\"World Health Organization\">WHO</abbr>"
    )
    result = convert(markdown, domain="")
    lowered = result.lower()

    assert "[aname=section]target[/aname]" in lowered
    assert "[jumpto=section]jump[/jumpto]" in lowered
    assert '[abbr="world health organization"]who[/abbr]' in lowered


def test_html_mailto_and_alignment():
    markdown = (
        "<a href=\"mailto:test@example.com?subject=Hello\">Email</a> "
        "<p style=\"text-align:center\">Centered</p>"
        "<div align=\"right\"><b>Right</b></div>"
        "<blockquote data-author=\"Alice\">Quoted</blockquote>"
    )
    result = convert(markdown, domain="")
    lowered = result.lower()

    assert "[email]test@example.com[/email]" in lowered
    assert "[center]centered[/center]" in lowered
    assert "[right][b]right[/b][/right]" in lowered
    assert "[quote=\"alice\"]" in lowered
    assert "quoted" in lowered


def test_span_and_div_without_style_convert_children():
    markdown = "<span><b>Bold</b></span><div><i>Italic</i></div>"
    result = convert(markdown, domain="")
    lowered = result.lower()

    assert "[b]bold[/b]" in lowered
    assert "[i]italic[/i]" in lowered
    assert "<span>" not in lowered
    assert "<div>" not in lowered


def test_unknown_html_passthrough():
    # The tag we do not know stays as written; what is inside it is still converted.
    markdown = "<custom-tag data-x=\"1\"><b>Bold</b></custom-tag>"
    result = convert(markdown, domain="")

    assert result == "<custom-tag data-x=\"1\">[B]Bold[/B]</custom-tag>\n"


def test_video_and_audio_become_a_link_to_the_file():
    # XenForo plays video through attachments and media sites, neither of which a
    # README can address, so the next best thing is a link someone can click.
    markdown = (
        '<video src="demo.mp4" controls>Your browser cannot play this.</video>\n\n'
        '<audio src="https://example.com/clip.ogg"></audio>\n'
    )
    assert convert(markdown, domain="https://example.com/r/") == (
        "[URL=https://example.com/r/demo.mp4]demo.mp4[/URL]\n\n"
        "[URL=https://example.com/clip.ogg]https://example.com/clip.ogg[/URL]\n"
    )


def test_a_video_built_from_source_children_stays_as_written():
    # There is no src to link to without picking one of the sources, so leave it alone.
    markdown = '<video controls><source src="a.mp4" type="video/mp4">Fallback.</video>'
    result = convert(markdown, domain="")

    assert result == '<video controls><source src="a.mp4" type="video/mp4">Fallback.</video>\n'


def test_standalone_html_comment_is_dropped():
    # Mirrors the redfetch README's generated-block markers, which are invisible
    # in Markdown but would render as literal text in BBCode.
    markdown = (
        "Before\n\n"
        "<!-- BEGIN GENERATED CLI REFERENCE -->\n\n"
        "Middle\n\n"
        "<!-- END GENERATED CLI REFERENCE -->\n\n"
        "After"
    )
    result = convert(markdown, domain="")

    assert "<!--" not in result
    assert "GENERATED CLI REFERENCE" not in result
    assert "Before" in result
    assert "Middle" in result
    assert "After" in result


def test_comment_nested_in_html_block_is_dropped():
    # A comment buried inside a larger raw HTML block still reaches the HTML pass
    # as part of one block; the converter must strip it there too.
    html = "<div><!-- hidden note --><b>Visible</b></div>"
    result = html_to_bbcode(html, domain="")

    assert "<!--" not in result
    assert "hidden note" not in result
    assert "[B]Visible[/B]" in result


def test_html_headings_convert_like_markdown_headings():
    assert convert("<h1>Title</h1>\n\ntext\n") == convert("# Title\n\ntext\n") == "[HEADING=1]Title[/HEADING]\ntext\n"
    assert convert("<h2>Sub <b>bold</b></h2>\n") == "[HEADING=2]Sub [B]bold[/B][/HEADING]\n"
    assert convert('<h2 style="color:red">Red</h2>\n') == "[HEADING=2][COLOR=red]Red[/COLOR][/HEADING]\n"
    # A level the board lacks falls back the way ##### does.
    assert convert("<h5>Five</h5>\n") == convert("##### Five\n") == "[HEADING=3]Five[/HEADING]\n"
    assert html_to_bbcode("<h1>Title</h1><p>text</p>") == "[HEADING=1]Title[/HEADING]\ntext"


def test_an_aligned_html_heading_is_wrapped_in_the_alignment():
    # The most common HTML in a README: a centered title, often with a logo above it.
    assert convert('<h1 align="center">Project</h1>\n\ntext\n') == "[CENTER][HEADING=1]Project[/HEADING][/CENTER]\n\ntext\n"
    logo = '<h1 align="center">\n  <img src="logo.png" alt="logo">\n  <br>\n  Project\n</h1>\n'
    assert convert(logo) == '[CENTER][HEADING=1][IMG alt="logo"]logo.png[/IMG]\nProject[/HEADING][/CENTER]\n'


def test_an_html_heading_ends_an_open_paragraph_and_an_unclosed_one_stays_as_written():
    assert convert("<p>para<h3>Head</h3>\n") == "para\n[HEADING=3]Head[/HEADING]\n"
    assert convert("<h2>never closed\n\ntext\n") == "<h2>never closed\n\ntext\n"
