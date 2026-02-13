import os
import xml.etree.ElementTree as ET

from md2bbcode.main import process_readme


def test_redguides_specific_bbcodes_from_xml():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    bbcode_xml_path = os.path.join(repo_root, "bb_codes.xml")

    tree = ET.parse(bbcode_xml_path)
    root = tree.getroot()
    bbcode_defs = [
        (el.attrib["bb_code_id"].strip().lower(), el.attrib.get("has_option", "no").strip().lower())
        for el in root.findall(".//bb_code")
    ]

    # Markdown that exercises every BBCode defined in bb_codes.xml.
    markdown = """
Some ==highlighted== text and a footnote.[^1]

![pixel art](https://example.com/pixel.png)

> [!TIP]
> A GitHub-style alert should become a custom BBCode.

---

Water is H<sub>2</sub>O.

The HTML specification is maintained by the W3C.

*[HTML]: Hyper Text Markup Language
*[W3C]: World Wide Web Consortium

[^1]: This is the footnote.
""".lstrip()

    result = process_readme(markdown, domain="")
    assert result is not None
    assert isinstance(result, str)

    lowered = result.lower()

    for bb_code_id, has_option in bbcode_defs:
        if has_option == "yes":
            assert f"[{bb_code_id}=" in lowered, f"Expected BBCode tag not found: [{bb_code_id}=...]"
        elif has_option == "optional":
            assert (
                f"[{bb_code_id}=" in lowered or f"[{bb_code_id}]" in lowered
            ), f"Expected BBCode tag not found: [{bb_code_id}] or [{bb_code_id}=...]"
        else:
            assert f"[{bb_code_id}]" in lowered, f"Expected BBCode tag not found: [{bb_code_id}]"

