"""Compare converted Markdown with saved BBCode; update with ``hatch test -- --update-goldens``."""

import tomllib
from pathlib import Path

import pytest

from md2bbcode import Dialect
from md2bbcode.dialect import TAGS
from md2bbcode.main import convert

FIXTURES = Path(__file__).parent / "fixtures"
# "xenforo" includes the RedGuides BB codes that ship with md2bbcode; "xenforo-stock" is a board with none.
DIALECTS = {
    "xenforo": lambda: Dialect.defaults(),
    "xenforo-stock": lambda: Dialect.defaults(bb_codes=False),
}
CASES = sorted(p.stem for p in FIXTURES.glob("*.md"))


def _read(path: Path) -> str:
    # newline="" keeps the bytes as they are so CRLF checkouts cannot mask a diff.
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def _write(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _options(case: str) -> dict:
    opts = FIXTURES / f"{case}.opts.toml"
    if opts.exists():
        with open(opts, "rb") as f:
            return tomllib.load(f)
    return {}


def convert_fixture(case: str, name: str) -> str:
    markdown = _read(FIXTURES / f"{case}.md")
    return convert(markdown, dialect=DIALECTS[name](), **_options(case))


@pytest.mark.parametrize("name", DIALECTS)
@pytest.mark.parametrize("case", CASES)
def test_golden(case: str, name: str, update_goldens: bool):
    expected_path = FIXTURES / f"{case}.{name}.bbcode"
    actual = convert_fixture(case, name)

    if update_goldens:
        _write(expected_path, actual)
        return

    assert expected_path.exists(), (
        f"missing golden {expected_path.name}; run: hatch test -- --update-goldens"
    )
    assert actual == _read(expected_path)


def test_the_renderer_fills_exactly_the_placeholders_a_config_may_use(monkeypatch):
    # dialect.TAGS lists the {placeholders} a config's template may use, and the renderer's
    # self.tag(...) calls supply the values. Nothing else ties the two lists together, and
    # a mismatch would only surface as a KeyError in somebody's custom config.
    real_render = Dialect.render

    def checked_render(self, key, **values):
        assert set(values) == set(TAGS[key]), f"tags.{key}: the renderer passes {sorted(values)}"
        return real_render(self, key, **values)

    monkeypatch.setattr(Dialect, "render", checked_render)
    for case in CASES:
        for name in DIALECTS:
            convert_fixture(case, name)


def test_every_golden_has_a_fixture():
    # Catch a renamed or deleted .md whose .bbcode was left behind.
    for golden in FIXTURES.glob("*.bbcode"):
        case = golden.name
        for name in DIALECTS:
            case = case.removesuffix(f".{name}.bbcode")
        assert (FIXTURES / f"{case}.md").exists(), f"orphan golden {golden.name}"
