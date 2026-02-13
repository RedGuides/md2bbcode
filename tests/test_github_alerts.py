from md2bbcode.main import process_readme


def test_github_alert_blockquote_renders_as_admonition():
    for kind in ["note", "tip", "important", "warning", "caution"]:
        markdown = f"""> [!{kind.upper()}]
> Body for {kind}.
""".lstrip()

        result = process_readme(markdown, domain="")
        lowered = result.lower()

        assert f"[admonition={kind}]" in lowered
        assert f"body for {kind}." in lowered
        assert f"[!{kind}]" not in lowered


def test_normal_blockquote_is_not_admonition():
    markdown = """> Just a quote.
> Still quoted.
""".lstrip()

    result = process_readme(markdown, domain="")
    lowered = result.lower()

    assert "[quote]" in lowered
    assert "[admonition=" not in lowered


def test_unknown_alert_marker_does_not_trigger_admonition():
    markdown = """> [!FOO]
> Not a supported GitHub alert type.
""".lstrip()

    result = process_readme(markdown, domain="")
    lowered = result.lower()

    assert "[quote]" in lowered
    assert "[admonition=" not in lowered
    assert "[!foo]" in lowered

