import os

from md2bbcode.main import process_readme


def test_conversion():
    readme_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "README.md"))
    with open(readme_path, "r", encoding="utf-8") as file:
        markdown_content = file.read()

    result = process_readme(markdown_content, domain="")

    assert result is not None
    assert isinstance(result, str)

    expected_bbcodes = [
        "[img alt",
        "[icode]",
        "[HEADING=1]",
        "[b]",
        "[HEADING=2]",
        "[CODE=bash]",
        "[sup]superscript[/sup]",
    ]

    lowered = result.lower()
    for bbcode in expected_bbcodes:
        assert bbcode.lower() in lowered, f"Expected BBCode not found: {bbcode}"
