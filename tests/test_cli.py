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
    assert out == "Emoji ☐ 🗹 and [I]em[/I]\n"
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


# dialects and base URLs

@pytest.fixture
def board(tmp_path):
    path = tmp_path / "board.toml"
    path.write_text('[tags]\ncodespan = "[code]{text}[/code]"\n', encoding="utf-8")
    return str(path)


@pytest.fixture
def readme(tmp_path):
    path = tmp_path / "in.md"
    path.write_text("`x` [g](guide.md) ![](logo.png)\n", encoding="utf-8")
    return str(path)


def test_config_changes_the_output_of_both_commands(board, readme, tmp_path, capsys):
    md2bbcode_main.main([readme, "--config", board])
    html = tmp_path / "in.html"
    html.write_text("<code>x</code>", encoding="utf-8")
    md2bbcode_main.html2bbcode_main([str(html), "--config", board])

    out, _ = capsys.readouterr()
    assert out == "[code]x[/code] [URL=guide.md]g[/URL] [IMG]logo.png[/IMG]\n[code]x[/code]\n"


def test_config_is_taken_from_the_environment_when_not_given(board, readme, monkeypatch, capsys):
    monkeypatch.setenv("MD2BBCODE_CONFIG", board)
    md2bbcode_main.main([readme])
    out, _ = capsys.readouterr()
    assert out.startswith("[code]x[/code]")


def test_link_base_image_base_and_domain(readme, capsys):
    md2bbcode_main.main([readme, "--link-base", "https://l.example/", "--image-base", "https://i.example/"])
    md2bbcode_main.main([readme, "--domain", "https://d.example/"])
    md2bbcode_main.main([readme, "--domain", ""])

    out, _ = capsys.readouterr()
    assert out.splitlines() == [
        "[ICODE]x[/ICODE] [URL=https://l.example/guide.md]g[/URL] [IMG]https://i.example/logo.png[/IMG]",
        "[ICODE]x[/ICODE] [URL=https://d.example/guide.md]g[/URL] [IMG]https://d.example/logo.png[/IMG]",
        "[ICODE]x[/ICODE] [URL=guide.md]g[/URL] [IMG]logo.png[/IMG]",
    ]


def test_dump_config_needs_no_input_and_is_a_working_config(board, readme, tmp_path, capsys):
    dumped = tmp_path / "dumped.toml"
    md2bbcode_main.main(["--dump-config", "--config", board, "-o", str(dumped)])
    assert 'codespan = "[code]{text}[/code]"' in dumped.read_text(encoding="utf-8")
    assert 'strong = "[B]{text}[/B]"' in dumped.read_text(encoding="utf-8")

    md2bbcode_main.main([readme, "--config", str(dumped)])
    out, _ = capsys.readouterr()
    assert out.startswith("[code]x[/code]")


def test_dump_config_prints_the_built_in_settings(capsys):
    md2bbcode_main.main(["--dump-config"])
    out, _ = capsys.readouterr()
    assert 'unknown_html = "keep"' in out and "[tags]" in out


@pytest.mark.parametrize(
    "extra, expected",
    [
        (["--config", "no-such-board.toml"], "config file not found: no-such-board.toml"),
        (["--domain", "example.com"], "--domain must be a full URL"),
        # Bad URLs should show a short error, not a traceback.
        (["--domain", "https://[::1"], "--domain must be a full URL"),
        (["--link-base", "http://[oops"], "--link-base must be a full URL"),
        (["--link-base", "javascript:alert(1)//"], "--link-base must be a full URL"),
        (["--image-base", "//cdn.example.com/"], "--image-base must be a full URL"),
    ],
)
@pytest.mark.parametrize("entry", [md2bbcode_main.main, md2bbcode_main.html2bbcode_main], ids=["md2bbcode", "html2bbcode"])
def test_bad_options_are_one_stderr_line_and_exit_1(entry, extra, expected, readme, capsys):
    _run(lambda: entry([readme, *extra]), 1)
    out, err = capsys.readouterr()
    assert out == ""
    assert err.count("\n") == 1 and expected in err


def test_bad_config_names_the_key(readme, tmp_path, capsys):
    bad = tmp_path / "bad.toml"
    bad.write_text('[tags]\ncodespan = "[code][/code]"\n', encoding="utf-8")
    _run(lambda: md2bbcode_main.main([readme, "--config", str(bad)]), 1)
    out, err = capsys.readouterr()
    assert out == ""
    assert err.count("\n") == 1 and "bad.toml" in err and "tags.codespan" in err


def test_ast_prints_the_tokens_the_renderer_works_from(readme, capsys):
    md2bbcode_main.main([readme, "--ast"])
    out, _ = capsys.readouterr()
    assert out.startswith("[")

    md2bbcode_main.md2ast_main([readme])
    alias, _ = capsys.readouterr()
    assert alias == out


def test_ast_works_while_the_config_is_broken(readme, tmp_path, capsys):
    # The tokens do not depend on the dialect, and this is when you want to see them.
    bad = tmp_path / "bad.toml"
    bad.write_text("not toml", encoding="utf-8")
    md2bbcode_main.main([readme, "--ast", "--config", str(bad)])
    out, err = capsys.readouterr()
    assert out.startswith("[") and err == ""


@pytest.mark.parametrize("entry", [md2bbcode_main.main, md2bbcode_main.html2bbcode_main], ids=["md2bbcode", "html2bbcode"])
def test_debug_is_gone_and_argparse_says_so(entry, readme, capsys):
    # Removed with the second pass it used to dump; --ast covers the debugging need.
    _run(lambda: entry([readme, "--debug"]), 2)
    _, err = capsys.readouterr()
    assert "--debug" in err
