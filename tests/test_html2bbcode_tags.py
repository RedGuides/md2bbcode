from md2bbcode.main import process_readme


def test_html_basic_formatting_and_links():
    markdown = (
        "<b>bold</b> <i>italic</i> <u>under</u> <s>strike</s> "
        "<ins>insert</ins> <mark>mark</mark> <kbd>kbd</kbd><br>"
        "<a href=\"https://example.com\">link</a> "
        "<img src=\"https://example.com/x.png\" alt=\"alt text\">"
        "<hr>"
    )
    result = process_readme(markdown, domain="")
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
    result = process_readme(markdown, domain="")
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
    result = process_readme(markdown, domain="")
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
    result = process_readme(markdown, domain="")
    lowered = result.lower()

    assert "[aname=section]target[/aname]" in lowered
    assert "[jumpto=section]jump[/jumpto]" in lowered
    assert "[abbr=world health organization]who[/abbr]" in lowered


def test_html_mailto_and_alignment():
    markdown = (
        "<a href=\"mailto:test@example.com?subject=Hello\">Email</a> "
        "<p style=\"text-align:center\">Centered</p>"
        "<div align=\"right\"><b>Right</b></div>"
        "<blockquote data-author=\"Alice\">Quoted</blockquote>"
    )
    result = process_readme(markdown, domain="")
    lowered = result.lower()

    assert "[email]test@example.com[/email]" in lowered
    assert "[center]centered[/center]" in lowered
    assert "[right][b]right[/b][/right]" in lowered
    assert "[quote=\"alice\"]" in lowered
    assert "quoted" in lowered


def test_span_and_div_without_style_convert_children():
    markdown = "<span><b>Bold</b></span><div><i>Italic</i></div>"
    result = process_readme(markdown, domain="")
    lowered = result.lower()

    assert "[b]bold[/b]" in lowered
    assert "[i]italic[/i]" in lowered
    assert "<span>" not in lowered
    assert "<div>" not in lowered


def test_unknown_html_passthrough():
    markdown = "<custom-tag data-x=\"1\"><b>Bold</b></custom-tag>"
    result = process_readme(markdown, domain="")

    assert "<custom-tag data-x=\"1\">" in result
    assert "<b>Bold</b>" in result
    assert "[b]" not in result
