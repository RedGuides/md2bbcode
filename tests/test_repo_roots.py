"""Test URLs starting with /, which GitHub and GitLab read from the repository root."""

import pytest

from md2bbcode import convert, html_to_bbcode
from md2bbcode import main as md2bbcode_main
from md2bbcode.renderer import resolve_roots, resolve_url

REPO = "https://github.com/o/r/blob/main/"
DOCS = REPO + "docs/"
LINK_ROOT = "https://github.com/o/r/blob/main/"
IMAGE_ROOT = "https://raw.githubusercontent.com/o/r/main/"

GITLAB_DOCS = "https://gitlab.com/g/sub/r/-/blob/main/docs/"
GITLAB_LINK_ROOT = "https://gitlab.com/g/sub/r/-/blob/main/"
GITLAB_IMAGE_ROOT = "https://gitlab.com/g/sub/r/-/raw/main/"

# Based on projecteon/MQ2DotNet's README, which writes images as /images/x.png.
LINK_AND_IMAGE = "[c](/docs/z.md) ![a](/images/x.png) ![b](images/y.png)"
EXPECTED = (
    f"[URL={LINK_ROOT}docs/z.md]c[/URL] "
    f'[IMG alt="a"]{IMAGE_ROOT}images/x.png[/IMG] '
    f'[IMG alt="b"]{{base}}images/y.png[/IMG]\n'
)


@pytest.mark.parametrize("domain, image_base", [(REPO, IMAGE_ROOT), (DOCS, IMAGE_ROOT + "docs/")])
def test_a_slash_path_goes_to_the_repo_root_and_a_relative_one_to_the_base(domain, image_base):
    assert convert(LINK_AND_IMAGE, domain=domain) == EXPECTED.format(base=image_base)


def test_a_github_link_base_is_enough_to_guess_the_roots():
    result = convert(LINK_AND_IMAGE, link_base=DOCS, image_base=IMAGE_ROOT + "docs/")
    assert result == EXPECTED.format(base=IMAGE_ROOT + "docs/")


def test_reference_style_links_and_images():
    text = "[c][z] ![a][x]\n\n[z]: /docs/z.md\n[x]: /images/x.png\n"
    assert convert(text, domain=DOCS) == f'[URL={LINK_ROOT}docs/z.md]c[/URL] [IMG alt="a"]{IMAGE_ROOT}images/x.png[/IMG]\n'


def test_inline_html_in_markdown_and_html_files():
    html = '<a href="/docs/z.md">c</a> <img src="/images/x.png" alt="a">'
    expected = f'[URL={LINK_ROOT}docs/z.md]c[/URL] [IMG alt="a"]{IMAGE_ROOT}images/x.png[/IMG]'
    assert convert(html, domain=DOCS) == expected + "\n"
    assert html_to_bbcode(html, domain=DOCS) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("/a.png?raw=1", "<root>a.png?raw=1"),
        ("/doc.md#section", "<root>doc.md#section"),
        ("/a/./b.md", "<root>a/b.md"),
        ("/a/../b.md", "<root>b.md"),
        ("/", "<root>"),
        # Climbing above the root is left alone, as GitForo does.
        ("/../b.md", "/../b.md"),
        ("/a/../../b.md", "/a/../../b.md"),
        # Everything else works as without a root.
        ("images/y.png", DOCS + "images/y.png"),
        ("../up.md", REPO + "up.md"),
        ("#section", "#section"),
        ("//cdn.example/x.js", "//cdn.example/x.js"),
        ("https://example.com/a", "https://example.com/a"),
        ("mailto:a@b.c", "mailto:a@b.c"),
        ("javascript:alert(1)", "#harmful-link"),
    ],
)
def test_resolve_url_with_a_root(url, expected):
    assert resolve_url(url, DOCS, LINK_ROOT) == expected.replace("<root>", LINK_ROOT)


def test_a_root_without_a_base_only_changes_slash_paths():
    assert resolve_url("/x.md", None, LINK_ROOT) == LINK_ROOT + "x.md"
    assert resolve_url("x.md", None, LINK_ROOT) == "x.md"


def test_an_explicit_root_wins_and_gets_its_slash():
    # The guess takes "feature" as the branch. The given roots are right.
    domain = "https://github.com/o/r/blob/feature/x/docs/"
    guessed = resolve_roots(domain=domain)
    assert guessed == ("https://github.com/o/r/blob/feature/", "https://raw.githubusercontent.com/o/r/feature/")

    link_root = "https://github.com/o/r/blob/feature/x"
    image_root = "https://raw.githubusercontent.com/o/r/feature/x"
    assert resolve_roots(link_root, image_root, domain=domain) == (link_root, image_root)
    assert resolve_roots(link_root, domain=domain) == (link_root, guessed[1])

    # A trailing slash is added, so the last folder is kept.
    result = convert("![a](/images/x.png)", domain=domain, link_root=link_root, image_root=image_root)
    assert result == f'[IMG alt="a"]{image_root}/images/x.png[/IMG]\n'
    assert resolve_url("/x.md", None, link_root) == link_root + "/x.md"


@pytest.mark.parametrize(
    "domain, roots",
    [
        ("https://github.com/o/r", ("https://github.com/o/r/blob/HEAD/", "https://raw.githubusercontent.com/o/r/HEAD/")),
        ("https://github.com/o/r/tree/main/docs", (LINK_ROOT, IMAGE_ROOT)),
        (DOCS + "README.md", (LINK_ROOT, IMAGE_ROOT)),
        (DOCS + "?download=1#part", (LINK_ROOT, IMAGE_ROOT)),
        # Not GitHub: no guess.
        (GITLAB_DOCS, (None, None)),
        ("https://d.example/docs/", (None, None)),
        (None, (None, None)),
    ],
)
def test_roots_are_guessed_from_github_only(domain, roots):
    assert resolve_roots(domain=domain) == roots


def test_gitlab_needs_explicit_roots():
    # Without them, /images/x.png lands on the host root.
    without = convert("![a](/images/x.png)", domain=GITLAB_DOCS)
    assert without == '[IMG alt="a"]https://gitlab.com/images/x.png[/IMG]\n'

    result = convert(LINK_AND_IMAGE, domain=GITLAB_DOCS, link_root=GITLAB_LINK_ROOT, image_root=GITLAB_IMAGE_ROOT)
    assert result == (
        f"[URL={GITLAB_LINK_ROOT}docs/z.md]c[/URL] "
        f'[IMG alt="a"]{GITLAB_IMAGE_ROOT}images/x.png[/IMG] '
        f'[IMG alt="b"]{GITLAB_DOCS}images/y.png[/IMG]\n'
    )


@pytest.mark.parametrize("entry", [md2bbcode_main.main, md2bbcode_main.html2bbcode_main], ids=["md2bbcode", "html2bbcode"])
def test_cli_root_options(entry, tmp_path, capsys):
    src = tmp_path / "input.txt"
    src.write_text('<a href="/docs/z.md">c</a> <img src="/images/x.png">', encoding="utf-8")
    entry([str(src), "--domain", GITLAB_DOCS, "--link-root", GITLAB_LINK_ROOT, "--image-root", GITLAB_IMAGE_ROOT])

    out, err = capsys.readouterr()
    assert err == ""
    assert out == f"[URL={GITLAB_LINK_ROOT}docs/z.md]c[/URL] [IMG]{GITLAB_IMAGE_ROOT}images/x.png[/IMG]\n"


@pytest.mark.parametrize("option", ["--link-root", "--image-root"])
def test_cli_root_options_must_be_full_urls(option, tmp_path, capsys):
    src = tmp_path / "input.md"
    src.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as exit_info:
        md2bbcode_main.main([str(src), option, "o/r/"])
    _, err = capsys.readouterr()
    assert exit_info.value.code == 1
    assert err == f"{option} must be a full URL like https://example.com/: o/r/\n"
