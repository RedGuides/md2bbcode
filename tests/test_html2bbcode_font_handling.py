from md2bbcode.main import process_readme


def test_html_font_tag_converts_to_xf_bbcode():
    markdown = '<font color="red" size="3" face="Times New Roman">Hello</font>\n'
    result = process_readme(markdown, domain="")
    lowered = result.lower()

    assert "[color=red]" in lowered
    assert "[size=3]" in lowered
    assert "[font=times new roman]hello[/font]" in lowered
    assert "[/size][/color]" in lowered


def test_html_style_attribute_converts_to_xf_bbcode():
    markdown = (
        '<span style="color: #f00; font-size: 12px; font-family: Arial; '
        'font-weight: bold; font-style: italic; text-decoration: underline line-through;">X</span>\n'
    )
    result = process_readme(markdown, domain="")
    lowered = result.lower()

    assert "[color=#f00]" in lowered
    assert "[size=12px]" in lowered
    assert "[font=arial]" in lowered
    assert "[b]" in lowered
    assert "[i]" in lowered
    assert "[u]" in lowered
    assert "[s]" in lowered


def test_inline_code_does_not_convert_html_inside_icode():
    markdown = '<font color="red">Red</font> and `<font color="red">Code</font>`\n'
    result = process_readme(markdown, domain="")
    lowered = result.lower()

    # Outside inline code: should convert
    assert "[color=red]" in lowered
    # Inside inline code: should remain literal HTML, not converted
    assert '[icode]<font color="red">code</font>[/icode]' in lowered

