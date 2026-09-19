"""A 200 KB README must be routine: every token walk has to stay linear."""

import timeit
from pathlib import Path

from md2bbcode.main import convert

FIXTURES = Path(__file__).parent / "fixtures"
SMALL_BYTES = 50_000
SCALE = 4
# A linear converter takes about SCALE times longer on a SCALE times larger
# document; a quadratic walk takes SCALE squared. The bound sits between the two
# so it holds on a slow or busy CI runner without depending on absolute speed.
MAX_RATIO = 10.0


def _document(target_bytes: int) -> str:
    unit = (FIXTURES / "markdown_features.md").read_text(encoding="utf-8")
    repeats = target_bytes // len(unit.encode("utf-8")) + 1
    return unit * repeats, repeats


def _time(document: str) -> float:
    # Best of three keeps a single scheduler hiccup from deciding the ratio.
    return min(timeit.repeat(lambda: convert(document), number=1, repeat=3))


def test_conversion_time_scales_linearly():
    small, _ = _document(SMALL_BYTES)
    large, repeats = _document(SMALL_BYTES * SCALE)
    assert len(large.encode("utf-8")) >= 200_000

    ratio = _time(large) / _time(small)
    assert ratio < MAX_RATIO, f"{SCALE}x input took {ratio:.1f}x as long"

    result = convert(large)
    assert result.count("[HEADING=1]Heading one[/HEADING]") == repeats
    assert result.count("Final paragraph.") == repeats
