"""CLI contract: UTF-8 both ways, one-line errors with exit code 1, --version."""

import io
import sys
from importlib.metadata import version as metadata_version

import pytest

import md2bbcode
from md2bbcode import main as md2bbcode_main

ENTRY_POINTS = {
    "md2bbcode": lambda path: md2bbcode_main.main([path]),
    "html2bbcode": lambda path: md2bbcode_main.html2bbcode_main([path]),
    "md2ast": lambda path: md2bbcode_main.md2ast_main([path]),
}


def _run(callable_, expected_code):
    with pytest.raises(SystemExit) as excinfo:
        callable_()
    assert excinfo.value.code == expected_code


@pytest.mark.parametrize("name", sorted(ENTRY_POINTS))
def test_missing_input_is_one_stderr_line_and_exit_1(name, tmp_path, capsys):
    missing = str(tmp_path / "does-not-exist.md")
    _run(lambda: ENTRY_POINTS[name](missing), 1)

    out, err = capsys.readouterr()
    assert out == ""
    assert err.endswith("\n") and err.count("\n") == 1
    assert "does-not-exist.md" in err
    assert "Traceback" not in err


def test_invalid_utf8_input_is_one_stderr_line_and_exit_1(tmp_path, capsys):
    bad = tmp_path / "bad.md"
    bad.write_bytes(b"# ok\n\xff\xfe not utf-8\n")
    _run(lambda: md2bbcode_main.main([str(bad)]), 1)

    out, err = capsys.readouterr()
    assert out == ""
    assert err.count("\n") == 1
    assert "bad.md" in err and "UTF-8" in err


def test_failure_leaves_no_partial_output_file(tmp_path, capsys):
    out_path = tmp_path / "out.bbcode"
    _run(lambda: md2bbcode_main.main([str(tmp_path / "missing.md"), "-o", str(out_path)]), 1)
    assert not out_path.exists()


def test_usage_error_keeps_argparse_exit_code_2(capsys):
    _run(lambda: md2bbcode_main.main([]), 2)
    out, err = capsys.readouterr()
    assert out == ""
    assert "usage:" in err


@pytest.mark.parametrize(
    "entry",
    [md2bbcode_main.main, md2bbcode_main.html2bbcode_main, md2bbcode_main.md2ast_main],
    ids=["md2bbcode", "html2bbcode", "md2ast"],
)
def test_version_matches_installed_metadata(entry, capsys):
    _run(lambda: entry(["--version"]), 0)
    out, _ = capsys.readouterr()
    assert out.strip().endswith(metadata_version("md2bbcode"))


def test_dunder_version_matches_installed_metadata():
    assert md2bbcode.__version__ == metadata_version("md2bbcode")


def test_stdin_is_read_as_utf8_under_a_non_utf8_locale(tmp_path, monkeypatch):
    text = "# Héllo — ☐ 🗹 ünïcödé\n"
    # Simulate a Windows console pipe: a text wrapper whose default decoding is a legacy code page.
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="cp1252"))
    out_path = tmp_path / "out.bbcode"

    md2bbcode_main.main(["-", "-o", str(out_path)])

    assert out_path.read_text(encoding="utf-8") == "[HEADING=1]Héllo — ☐ 🗹 ünïcödé[/HEADING]\n"


def test_stdout_output_is_utf8_and_matches_output_file(tmp_path, capsys):
    src = tmp_path / "in.md"
    src.write_text("Emoji ☐ 🗹 and *em*\n", encoding="utf-8")
    out_path = tmp_path / "out.bbcode"

    md2bbcode_main.main([str(src)])
    md2bbcode_main.main([str(src), "-o", str(out_path)])

    out, err = capsys.readouterr()
    assert err == ""
    assert out == "Emoji ☐ 🗹 and [i]em[/i]\n\n"
    assert out_path.read_bytes().decode("utf-8") == out


def test_closed_stdout_pipe_is_one_stderr_line_and_exit_1(tmp_path, monkeypatch, capsys):
    src = tmp_path / "in.md"
    src.write_text("text\n", encoding="utf-8")

    class ClosedPipe(io.StringIO):
        def write(self, _):
            raise BrokenPipeError

    monkeypatch.setattr(sys, "stdout", ClosedPipe())
    _run(lambda: md2bbcode_main.main([str(src)]), 1)
    _, err = capsys.readouterr()
    assert err.count("\n") == 1 and "stdout" in err


def test_output_file_gets_exactly_one_trailing_newline_added_when_missing(tmp_path):
    src = tmp_path / "in.html"
    src.write_text("<b>x</b>", encoding="utf-8")
    out_path = tmp_path / "out.bbcode"

    md2bbcode_main.html2bbcode_main([str(src), "-o", str(out_path)])

    assert out_path.read_bytes() == b"[B]x[/B]\n"


def test_html2bbcode_reads_stdin(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("<i>from stdin</i>"))
    md2bbcode_main.html2bbcode_main(["-"])
    out, _ = capsys.readouterr()
    assert out == "[I]from stdin[/I]\n"
