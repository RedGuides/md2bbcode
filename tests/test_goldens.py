"""Compare converted Markdown with saved BBCode; update with ``hatch test -- --update-goldens``."""

import tomllib
from pathlib import Path

import pytest

from md2bbcode.main import process_readme

FIXTURES = Path(__file__).parent / "fixtures"
PRESETS = ["xenforo"]
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


def convert_fixture(case: str, preset: str) -> str:
    markdown = _read(FIXTURES / f"{case}.md")
    return process_readme(markdown, dialect=preset, **_options(case))


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("case", CASES)
def test_golden(case: str, preset: str, update_goldens: bool):
    expected_path = FIXTURES / f"{case}.{preset}.bbcode"
    actual = convert_fixture(case, preset)

    if update_goldens:
        _write(expected_path, actual)
        return

    assert expected_path.exists(), (
        f"missing golden {expected_path.name}; run: hatch test -- --update-goldens"
    )
    assert actual == _read(expected_path)


def test_every_golden_has_a_fixture():
    # Catch a renamed or deleted .md whose .bbcode was left behind.
    for golden in FIXTURES.glob("*.bbcode"):
        case = golden.name
        for preset in PRESETS:
            case = case.removesuffix(f".{preset}.bbcode")
        assert (FIXTURES / f"{case}.md").exists(), f"orphan golden {golden.name}"
