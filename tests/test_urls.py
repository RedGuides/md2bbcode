"""Test links and images in Markdown and HTML."""

import pytest

from md2bbcode import convert
from md2bbcode import html_to_bbcode
from md2bbcode.renderer import resolve_bases, resolve_url

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
        ({"domain": LINK_BASE}, (LINK_BASE, IMAGE_BASE)),
        ({"domain": LINK_BASE, "link_base": "https://docs.example/"}, ("https://docs.example/", IMAGE_BASE)),
        ({"domain": LINK_BASE, "image_base": "https://cdn.example/"}, (LINK_BASE, "https://cdn.example/")),
        ({"domain": LINK_BASE, "image_base": LINK_BASE}, (LINK_BASE, LINK_BASE)),
        ({"domain": "https://d.example/"}, ("https://d.example/", "https://d.example/")),
        ({"domain": "https://d.example/", "image_base": IMAGE_BASE}, ("https://d.example/", IMAGE_BASE)),
        ({"domain": "", "link_base": ""}, (None, None)),
    ],
)
def test_resolve_bases_fallback(given, expected):
    assert resolve_bases(**given) == expected


@pytest.mark.parametrize(
    "domain, image_base",
    [
        ("https://github.com/o/r/blob/main/", "https://raw.githubusercontent.com/o/r/main/"),
        (LINK_BASE, IMAGE_BASE),
        ("https://github.com/o/r/blob/feature/topic/docs/", "https://raw.githubusercontent.com/o/r/feature/topic/docs/"),
        ("https://github.com/o/r/blob/release%2Fv1/my%20docs/", "https://raw.githubusercontent.com/o/r/release%2Fv1/my%20docs/"),
        (LINK_BASE + "?download=1#part", IMAGE_BASE + "?download=1#part"),
        ("http://GITHUB.COM/o/r/blob/main/", "http://raw.githubusercontent.com/o/r/main/"),
    ],
)
def test_github_domain_preserves_ref_path_and_url_components(domain, image_base):
    assert resolve_bases(domain=domain) == (domain, image_base)


@pytest.mark.parametrize(
    "domain",
    [
        # What people copy from the address bar: the repo's home page, or a folder.
        "https://github.com/o/r",
        "https://github.com/o/r/",
        "https://www.github.com/o/r",
    ],
)
def test_a_github_home_page_uses_the_default_branch(domain):
    host = domain.split("/o/r")[0]
    assert resolve_bases(domain=domain) == (f"{host}/o/r/blob/HEAD/", "https://raw.githubusercontent.com/o/r/HEAD/")


@pytest.mark.parametrize(
    "domain, link_base, image_base",
    [
        ("https://github.com/o/r/tree/main", "https://github.com/o/r/blob/main/", "https://raw.githubusercontent.com/o/r/main/"),
        ("https://github.com/o/r/tree/main/docs", "https://github.com/o/r/blob/main/docs/", "https://raw.githubusercontent.com/o/r/main/docs/"),
        ("https://github.com/o/r/tree/main/docs/", "https://github.com/o/r/blob/main/docs/", "https://raw.githubusercontent.com/o/r/main/docs/"),
        # A branch on its own gets its missing slash; a file does not, and its folder is used.
        ("https://github.com/o/r/blob/main", "https://github.com/o/r/blob/main/", "https://raw.githubusercontent.com/o/r/main/"),
        ("https://github.com/o/r/blob/main/README.md", "https://github.com/o/r/blob/main/README.md", "https://raw.githubusercontent.com/o/r/main/README.md"),
    ],
)
def test_a_github_folder_url_and_a_missing_slash(domain, link_base, image_base):
    assert resolve_bases(domain=domain) == (link_base, image_base)
    # Overrides still win.
    assert resolve_bases(domain=domain, link_base="https://docs.example/") == ("https://docs.example/", image_base)
    assert resolve_bases(domain=domain, image_base="https://cdn.example/") == (link_base, "https://cdn.example/")


def test_the_repo_home_page_is_enough_for_a_readme():
    result = convert("[guide](docs/guide.md) ![](img/logo.png)", domain="https://github.com/o/r")
    assert result == (
        "[URL=https://github.com/o/r/blob/HEAD/docs/guide.md]guide[/URL] "
        "[IMG]https://raw.githubusercontent.com/o/r/HEAD/img/logo.png[/IMG]\n"
    )


@pytest.mark.parametrize(
    "domain",
    [
        "https://example.com/o/r/blob/main/",
        "https://github.com.example.com/o/r/blob/main/",
        "https://github.com@elsewhere.example/o/r/blob/main/",
        IMAGE_BASE,
        "https://github.com/o/r/issues",
        "https://github.com/o/r/wiki/Home",
        "https://github.com/o",
        "https://github.com/o/r/blob/",
        "https://github.com/o/r/blob//docs/",
        "https://github.com//r/blob/main/",
        "https://github.com/o//blob/main/",
        "https://[oops",
        "ftp://github.com/o/r/blob/main/",
    ],
)
def test_domain_without_a_recognized_github_url_is_unchanged(domain):
    assert resolve_bases(domain=domain) == (domain, domain)


@pytest.mark.parametrize("url", ["asset", "logo.png", "image.custom", "../asset", "https://cdn.example/asset", "//cdn.example/asset"])
def test_github_domain_uses_markup_not_file_extensions(url):
    link = resolve_url(url, LINK_BASE)
    image = resolve_url(url, IMAGE_BASE)
    expected = f'[URL={link}]file[/URL] [IMG]{image}[/IMG]'
    html = f'<a href="{url}">file</a> <img src="{url}">'

    assert convert(f"[file]({url}) ![]({url})", domain=LINK_BASE).rstrip("\n") == expected
    assert html_to_bbcode(html, domain=LINK_BASE) == expected
    assert convert(html, domain=LINK_BASE).rstrip("\n") == expected


BASE_CASES = {
    "neither": ({}, "guide.md", "logo.png"),
    "link base only": ({"link_base": LINK_BASE}, LINK_BASE + "guide.md", LINK_BASE + "logo.png"),
    "image base only": ({"image_base": IMAGE_BASE}, IMAGE_BASE + "guide.md", IMAGE_BASE + "logo.png"),
    "both": ({"link_base": LINK_BASE, "image_base": IMAGE_BASE}, LINK_BASE + "guide.md", IMAGE_BASE + "logo.png"),
    "domain": ({"domain": LINK_BASE}, LINK_BASE + "guide.md", IMAGE_BASE + "logo.png"),
}


@pytest.mark.parametrize("case", sorted(BASE_CASES))
def test_markdown_and_html_use_the_link_base_for_links_and_the_image_base_for_images(case):
    bases, link, image = BASE_CASES[case]

    markdown = convert("[g](guide.md) ![l](logo.png)", **bases)
    assert markdown == f'[URL={link}]g[/URL] [IMG alt="l"]{image}[/IMG]\n'

    html = html_to_bbcode('<a href="guide.md">g</a> <img src="logo.png" alt="l">', **bases)
    assert html == f'[URL={link}]g[/URL] [IMG alt="l"]{image}[/IMG]'

    # Also check HTML inside Markdown.
    mixed = convert('See <a href="guide.md">g</a> <img src="logo.png" alt="l">.', **bases)
    assert mixed == "See " + html + ".\n"


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
        if not url.startswith("#"):
            # A Markdown "#section" link uses [JUMPTO] as well.
            assert convert(f"[t](<{url}>)", **bases) == f"[URL={link}]t[/URL]\n"
        assert convert(f"![](<{url}>)", **bases) == f"[IMG]{image}[/IMG]\n"


@pytest.mark.parametrize("url", ["https://[::1", "http://[oops", "https://exa]mple.com/"])
def test_a_url_urlparse_rejects_is_left_alone_instead_of_crashing(url):
    # Bad URLs must not stop conversion; Markdown encodes these brackets,
    # so only HTML passes them through as written.
    assert resolve_url(url, LINK_BASE) == url
    bases = {"link_base": LINK_BASE, "image_base": IMAGE_BASE}
    assert html_to_bbcode(f'<a href="{url}">t</a>', **bases) == f"[URL={url}]t[/URL]"
    assert html_to_bbcode(f'<img src="{url}">', **bases) == f"[IMG]{url}[/IMG]"


def test_markdown_anchor_link_is_not_joined_to_the_base():
    result = convert("[top](#getting-started)", domain="https://github.com/o/r/blob/main/")
    assert result == "[JUMPTO=getting-started]top[/JUMPTO]\n"
