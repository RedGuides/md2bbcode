from urllib.parse import quote

from md2bbcode.main import process_readme


def test_github_actions_badge_rewrites_to_png():
    markdown = (
        "[![Publish to PyPI](https://github.com/RedGuides/md2bbcode/actions/workflows/publish.yml/badge.svg)]"
        "(https://github.com/RedGuides/md2bbcode/actions/workflows/publish.yml)"
    )
    result = process_readme(markdown, domain="")
    lowered = result.lower()

    assert "[url=https://github.com/redguides/md2bbcode/actions/workflows/publish.yml]" in lowered
    assert (
        "https://raster.shields.io/github/actions/workflow/status/redguides/md2bbcode/publish.yml.png"
        in lowered
    )


def test_html_svg_wraps_weserv():
    svg_url = "https://example.com/asset.svg?x=1&y=2"
    markdown = f'<img src="{svg_url}" alt="Alt text">'
    result = process_readme(markdown, domain="")
    lowered = result.lower()

    expected = f"https://images.weserv.nl/?url={quote(svg_url, safe='')}&output=png"
    assert expected.lower() in lowered
    assert '[img alt="alt text"]' in lowered


def test_redguides_sparkline_adds_png_format():
    sparkline_url = (
        "https://www.redguides.com/community/resources/ghoul-resource.1623/watchers-sparkline"
        "?months=24&w=500&h=180"
    )
    markdown = f'<img src="{sparkline_url}" alt="Watchers">'
    result = process_readme(markdown, domain="")
    lowered = result.lower()

    assert "watchers-sparkline?months=24&w=500&h=180&format=png" in lowered


def test_non_svg_image_unchanged():
    png_url = "https://example.com/x.png"
    markdown = f"![alt]({png_url})"
    result = process_readme(markdown, domain="")
    lowered = result.lower()

    assert png_url in lowered
