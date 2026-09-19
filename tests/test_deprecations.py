"""What still works after the rename, for scripts written against the old names."""

import os

import pytest

import md2bbcode
from md2bbcode import convert
from md2bbcode.main import process_readme

README = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "README.md"))


def _readme() -> str:
    with open(README, "r", encoding="utf-8") as file:
        return file.read()


def test_process_readme_still_converts_a_readme():
    markdown = _readme()
    with pytest.deprecated_call():
        result = process_readme(markdown, domain="")

    assert result == convert(markdown, domain="")
    lowered = result.lower()
    for bbcode in ["[img alt", "[icode]", "[heading=1]", "[b]", "[heading=2]", "[code=bash]", "[sup]2[/sup]"]:
        assert bbcode in lowered, f"Expected BBCode not found: {bbcode}"


def test_old_positional_calls_still_line_up():
    # debug used to sit third; it is ignored but keeps its place.
    markdown = "[a](docs/a.md) ![i](img/i.png)\n"
    with pytest.deprecated_call():
        result = process_readme(markdown, None, False, "https://links.example/")
    assert result == convert(markdown, link_base="https://links.example/")
    with pytest.deprecated_call():
        assert process_readme("**x**", debug=True) == "[B]x[/B]\n"


def test_the_old_import_paths_still_resolve():
    # The one name the 1.x README told people to import, from both places it lived.
    assert md2bbcode.process_readme is process_readme
