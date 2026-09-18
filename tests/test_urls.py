"""Test links and images in Markdown and HTML."""

import pytest

from md2bbcode import process_readme
from md2bbcode.html2bbcode import html_to_bbcode
from md2bbcode.renderers.bbcode import resolve_bases, resolve_url

LINK_BASE = "https://github.com/o/r/blob/main/docs/"
IMAGE_BASE = "https://raw.githubusercontent.com/o/r/main/docs/"

# url, expected when joined to "<base>"
RULES = [
    ("https://example.com/a", "https://example.com/a"),
    ("http://example.com/a", "http://example.com/a"),
    ("mailto:a@b.c", "mailto:a@b.c"),
    ("ftp://example.com/f", "ftp://example.com/f"),
    ("//cdn.example.com/x.js", "//cdn.example.com/x.js"),
    ("#section", "#section"),
    ("javascript:alert(1)", "#harmful-link"),
    ("JavaScript:alert(1)", "#harmful-link"),
    (" vbscript:x", "#harmful-link"),
    ("data:text/plain,hi", "#harmful-link"),
    ("guide.md", "<base>guide.md"),
    ("./guide.md#install", "<base>guide.md#install"),
    ("../up.md", "<parent>up.md"),
    ("/root.md", "<host>/root.md"),
    ("page.md?x=1", "<base>page.md?x=1"),
]


def _expected(template: str, base: str) -> str:
    host = base.split("/", 3)
    return (
        template.replace("<base>", base)
        .replace("<parent>", base.rsplit("/", 2)[0] + "/")
        .replace("<host>", "/".join(host[:3]))
    )


@pytest.mark.parametrize("url, expected", RULES)
def test_resolve_url_with_a_base(url, expected):
    assert resolve_url(url, LINK_BASE) == _expected(expected, LINK_BASE)


@pytest.mark.parametrize("url, expected", RULES)
def test_resolve_url_without_a_base_only_neutralises_harmful_urls(url, expected):
    assert resolve_url(url, None) == ("#harmful-link" if expected == "#harmful-link" else url)


@pytest.mark.parametrize(
    "given, expected",
    [
        ({}, (None, None)),
        ({"link_base": LINK_BASE}, (LINK_BASE, LINK_BASE)),
        ({"image_base": IMAGE_BASE}, (IMAGE_BASE, IMAGE_BASE)),
        ({"link_base": LINK_BASE, "image_base": IMAGE_BASE}, (LINK_BASE, IMAGE_BASE)),
        ({"domain": "https://d.example/"}, ("https://d.example/", "https://d.example/")),
        ({"domain": "https://d.example/", "image_base": IMAGE_BASE}, ("https://d.example/", IMAGE_BASE)),
        ({"domain": "", "link_base": ""}, (None, None)),
    ],
)
def test_resolve_bases_fallback(given, expected):
    assert resolve_bases(**given) == expected


BASE_CASES = {
    "neither": ({}, "guide.md", "logo.png"),
    "link base only": ({"link_base": LINK_BASE}, LINK_BASE + "guide.md", LINK_BASE + "logo.png"),
    "image base only": ({"image_base": IMAGE_BASE}, IMAGE_BASE + "guide.md", IMAGE_BASE + "logo.png"),
    "both": ({"link_base": LINK_BASE, "image_base": IMAGE_BASE}, LINK_BASE + "guide.md", IMAGE_BASE + "logo.png"),
    "domain": ({"domain": LINK_BASE}, LINK_BASE + "guide.md", LINK_BASE + "logo.png"),
}


@pytest.mark.parametrize("case", sorted(BASE_CASES))
def test_markdown_and_html_use_the_link_base_for_links_and_the_image_base_for_images(case):
    bases, link, image = BASE_CASES[case]

    markdown = process_readme("[g](guide.md) ![l](logo.png)", **bases)
    assert markdown == f'[URL={link}]g[/URL] [IMG alt="l"]{image}[/IMG]\n\n'

    html = html_to_bbcode('<a href="guide.md">g</a> <img src="logo.png" alt="l">', **bases)
    assert html == f'[URL={link}]g[/URL] [IMG alt="l"]{image}[/IMG]'

    # Also check HTML inside Markdown.
    mixed = process_readme('See <a href="guide.md">g</a> <img src="logo.png" alt="l">.', **bases)
    assert mixed == "See " + html + ".\n\n"


@pytest.mark.parametrize("url, expected", RULES)
def test_every_rule_holds_for_all_four_kinds_of_url(url, expected):
    link = _expected(expected, LINK_BASE)
    image = _expected(expected, IMAGE_BASE)
    bases = {"link_base": LINK_BASE, "image_base": IMAGE_BASE}

    assert html_to_bbcode(f'<img src="{url}">', **bases) == f"[IMG]{image}[/IMG]"
    if not url.startswith(("#", "mailto:")):
        # Anchors and email links use [JUMPTO] and [EMAIL], not [URL].
        assert html_to_bbcode(f'<a href="{url}">t</a>', **bases) == f"[URL={link}]t[/URL]"

    if url == url.strip() and "(" not in url:
        assert process_readme(f"[t](<{url}>)", **bases) == f"[URL={link}]t[/URL]\n\n"
        assert process_readme(f"![](<{url}>)", **bases) == f"[IMG]{image}[/IMG]\n\n"


@pytest.mark.parametrize("url", ["https://[::1", "http://[oops", "https://exa]mple.com/"])
def test_a_url_urlparse_rejects_is_left_alone_instead_of_crashing(url):
    # Bad URLs must not stop conversion; Markdown encodes these brackets,
    # so only HTML passes them through as written.
    assert resolve_url(url, LINK_BASE) == url
    bases = {"link_base": LINK_BASE, "image_base": IMAGE_BASE}
    assert html_to_bbcode(f'<a href="{url}">t</a>', **bases) == f"[URL={url}]t[/URL]"
    assert html_to_bbcode(f'<img src="{url}">', **bases) == f"[IMG]{url}[/IMG]"


def test_markdown_anchor_link_is_not_joined_to_the_base():
    result = process_readme("[top](#getting-started)", domain="https://github.com/o/r/blob/main/")
    assert result == "[URL=#getting-started]top[/URL]\n\n"
