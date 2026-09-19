# Converts Markdown to BBCode with a custom mistune renderer (renderer.py).
# HTML tags are paired into tokens before rendering (plugins.py, html_tokens.py).
# Run md2bbcode --ast to see what the renderer gets, for debugging.

# standard library
import argparse
import functools
import json
import os
import sys
import warnings
from urllib.parse import urlparse
from importlib.metadata import PackageNotFoundError, version as _distribution_version

# mistune
import mistune
from mistune import BlockState
from mistune.plugins.formatting import strikethrough, mark, superscript, subscript, insert
from mistune.plugins.table import table, table_in_list
from mistune.plugins.footnotes import footnotes
from mistune.plugins.task_lists import task_lists
from mistune.plugins.def_list import def_list
from mistune.plugins.abbr import abbr
from mistune.plugins.spoiler import spoiler

# local
from md2bbcode.dialect import Dialect, DialectError
from md2bbcode.plugins import merge_ordered_lists, pair_html
from md2bbcode.renderer import BBCodeRenderer

# Use a XenForo export from the current folder if present.
LOCAL_BB_CODES = "bb_codes.xml"

PLUGINS = [strikethrough, mark, superscript, subscript, insert, table, footnotes, task_lists, def_list, abbr, spoiler, table_in_list, merge_ordered_lists]


# conversion

class Converter:
    """Convert Markdown or HTML to BBCode with a reusable parser and renderer."""

    def __init__(self, dialect=None, link_base=None, image_base=None, domain=None):
        self.renderer = BBCodeRenderer(domain=domain, link_base=link_base, image_base=image_base, dialect=dialect)
        self._markdown = mistune.create_markdown(renderer=self.renderer, plugins=PLUGINS)
        self._tokens = mistune.create_markdown(renderer=None, plugins=PLUGINS)

    def markdown(self, text: str) -> str:
        """Convert Markdown and embedded HTML to BBCode, adding a final newline to nonempty output."""
        bbcode = self._markdown(text)
        if bbcode:
            bbcode += '\n'
        return bbcode

    def html(self, text: str) -> str:
        """Convert HTML to BBCode without parsing Markdown syntax."""
        return self.renderer([{"type": "block_html", "raw": text}], BlockState())

    def tokens(self, text: str) -> list:
        """Return parsed Markdown tokens with HTML tags paired for rendering."""
        return pair_html(self._tokens(text))


def convert(markdown_text, dialect=None, link_base=None, image_base=None, domain=None) -> str:
    """Convert Markdown, and any HTML inside it, to BBCode."""
    return Converter(dialect=dialect, link_base=link_base, image_base=image_base, domain=domain).markdown(markdown_text)


def convert_markdown_to_ast(markdown_text):
    """Show parsed Markdown and HTML before rendering, for debugging."""
    return Converter().tokens(markdown_text)


def html_to_bbcode(html, domain=None, link_base=None, image_base=None, dialect=None) -> str:
    """Convert an HTML document or fragment to BBCode."""
    return Converter(dialect=dialect, link_base=link_base, image_base=image_base, domain=domain).html(html)


def process_readme(markdown_text, domain=None, debug=False, link_base=None, image_base=None, dialect=None):
    """Deprecated alias for :func:`convert`; ``debug`` is kept for positional compatibility and ignored."""
    warnings.warn(
        "process_readme() is deprecated; use md2bbcode.convert()",
        DeprecationWarning,
        stacklevel=2,
    )
    return convert(markdown_text, dialect=dialect, link_base=link_base, image_base=image_base, domain=domain)


# shared command-line functions

@functools.cache
def package_version() -> str:
    try:
        return _distribution_version("md2bbcode")
    except PackageNotFoundError:
        return "0+unknown"


class CliError(Exception):
    """An error we can explain without showing a Python traceback."""


def _force_utf8(stream) -> None:
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        # Some streams don't let us change the encoding.
        pass


def read_input(path: str) -> str:
    """Read UTF-8 text from a file, or from piped input if the path is "-"."""
    if path == "-":
        # Use UTF-8 so Windows can read piped text with accents and emoji.
        _force_utf8(sys.stdin)
        try:
            return sys.stdin.read()
        except UnicodeDecodeError as exc:
            raise CliError(f"could not read piped input (stdin) as UTF-8: {exc.reason} at byte {exc.start}") from exc

    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError as exc:
        raise CliError(f"input file not found: {path}") from exc
    except UnicodeDecodeError as exc:
        raise CliError(f"could not read {path} as UTF-8: {exc.reason} at byte {exc.start}") from exc
    except OSError as exc:
        raise CliError(f"cannot read {path}: {exc.strerror or exc}") from exc


def write_output(text: str, output_path=None) -> None:
    """Save the result as UTF-8, or print it if no output file is given or the path is "-"."""
    if not text.endswith("\n"):
        text += "\n"

    if output_path is not None and output_path != "-":
        try:
            with open(output_path, "w", encoding="utf-8", newline="") as out_file:
                out_file.write(text)
        except OSError as exc:
            raise CliError(f"cannot write {output_path}: {exc.strerror or exc}") from exc
        return

    try:
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is not None:
            # Write bytes so Windows doesn't change the line endings or break emoji.
            # This keeps the output the same whether you use -o or pipe it to another program.
            sys.stdout.flush()
            buffer.write(text.encode("utf-8"))
            buffer.flush()
        else:
            _force_utf8(sys.stdout)
            sys.stdout.write(text)
            sys.stdout.flush()
    except BrokenPipeError as exc:
        # The program we're piping to stopped reading, so just show a short error.
        raise CliError("output (stdout) was closed before we could finish writing") from exc


def _add_version_argument(parser) -> None:
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version()}")


def _add_output_argument(parser) -> None:
    parser.add_argument('-o', '--output', help='Save the result to a UTF-8 file. Use "-" or leave this out to print the result. On Windows, use -o instead of > to save to a file.')


def _add_url_arguments(parser) -> None:
    parser.add_argument('--link-base', metavar='URL', help='Base URL for relative links (also images if no other base is set)')
    parser.add_argument('--image-base', metavar='URL', help='Base URL for relative images (also links if no other base is set)')
    parser.add_argument('--domain', metavar='URL', help='Base URL for both links and images unless set separately')


def _add_dialect_arguments(parser) -> None:
    parser.add_argument('--config', metavar='FILE', help='TOML file with custom tags (default: MD2BBCODE_CONFIG environment variable)')
    custom = parser.add_mutually_exclusive_group()
    custom.add_argument('--bb-codes', metavar='FILE', help="Your board's custom BB codes, exported from XenForo at admin.php?bb-codes (default: MD2BBCODE_BB_CODES environment variable, then the config, then a bb_codes.xml in the current folder, then the RedGuides set)")
    custom.add_argument('--no-custom-bbcode', action='store_true', help='Use only the tags built into the forum software')


def _checked_base_url(option: str, value):
    """Return a full HTTP(S) URL or None, raising CliError for an invalid URL."""
    if not value:
        return None
    try:
        parsed = urlparse(value)
        is_full_url = parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except ValueError:
        # Invalid URLs, such as a host with an unclosed bracket.
        is_full_url = False
    if not is_full_url:
        raise CliError(f"{option} must be a full URL like https://example.com/: {value}")
    return value


def base_urls(args) -> dict:
    """Check and return the base URLs."""
    return {
        'link_base': _checked_base_url('--link-base', args.link_base),
        'image_base': _checked_base_url('--image-base', args.image_base),
        'domain': _checked_base_url('--domain', args.domain),
    }


def load_dialect(args) -> Dialect:
    config = args.config or os.environ.get('MD2BBCODE_CONFIG')
    if args.no_custom_bbcode:
        bb_codes = False
    else:
        # None leaves the choice to the config, then the folder, then the export we ship.
        bb_codes = args.bb_codes or os.environ.get('MD2BBCODE_BB_CODES') or None
    # Look for an export in the current folder.
    found = LOCAL_BB_CODES if os.path.isfile(LOCAL_BB_CODES) else None
    try:
        if config:
            return Dialect.load(config, bb_codes=bb_codes, default_bb_codes=found)
        return Dialect.defaults(bb_codes=bb_codes, default_bb_codes=found)
    except DialectError as exc:
        raise CliError(str(exc)) from exc


def _write_ast(input_path: str, output_path=None) -> None:
    """Write parsed tokens as JSON for md2bbcode --ast and md2ast."""
    tokens = convert_markdown_to_ast(read_input(input_path))
    write_output(json.dumps(tokens, indent=4), output_path)


def run(command, argv=None) -> None:
    """Run the command, showing a short error and exiting with code 1 if it raises CliError."""
    try:
        command(argv)
    except CliError as exc:
        print(str(exc).rstrip("\n") or "error", file=sys.stderr)
        raise SystemExit(1) from exc


# commands

def _md2bbcode(argv=None):
    parser = argparse.ArgumentParser(prog='md2bbcode', description='Convert a Markdown file to BBCode, including any HTML.')
    parser.add_argument('input', nargs='?', help='Markdown file to convert (use "-" to read piped input)')
    _add_output_argument(parser)
    _add_url_arguments(parser)
    _add_dialect_arguments(parser)
    parser.add_argument('--dump-config', action='store_true', help='Print the current settings as a reusable TOML config, then exit')
    parser.add_argument('--ast', action='store_true', help='Print the tokens the renderer works from (JSON), for debugging')
    _add_version_argument(parser)
    args = parser.parse_args(argv)

    if args.dump_config:
        # The one mode that needs no input file.
        write_output(load_dialect(args).to_toml(), args.output)
        return
    if args.input is None:
        parser.error('the following arguments are required: input')
    if args.ast:
        # The tokens do not depend on the dialect, so a broken config cannot get in the way.
        _write_ast(args.input, args.output)
        return

    dialect = load_dialect(args)
    bases = base_urls(args)

    # Finish reading and converting before opening the output file.
    markdown_text = read_input(args.input)
    write_output(Converter(dialect=dialect, **bases).markdown(markdown_text), args.output)


def _html2bbcode(argv=None):
    parser = argparse.ArgumentParser(prog="html2bbcode", description="Convert an HTML file to BBCode.")
    parser.add_argument("input", help='HTML file to convert (use "-" to read piped input)')
    _add_output_argument(parser)
    _add_url_arguments(parser)
    _add_dialect_arguments(parser)
    _add_version_argument(parser)
    args = parser.parse_args(argv)

    dialect = load_dialect(args)
    bases = base_urls(args)
    html_content = read_input(args.input)
    write_output(Converter(dialect=dialect, **bases).html(html_content), args.output)


def _md2ast(argv=None):
    parser = argparse.ArgumentParser(prog='md2ast', description='Show parsed Markdown and HTML as JSON for debugging (same as md2bbcode --ast).')
    parser.add_argument('input', help='Markdown file to convert (use "-" to read piped input)')
    parser.add_argument('output', nargs='?', default='-', help='Save the result to a JSON file. Use "-" or leave this out to print the result.')
    _add_version_argument(parser)
    args = parser.parse_args(argv)

    _write_ast(args.input, args.output)


def main(argv=None):
    """Run the md2bbcode command."""
    run(_md2bbcode, argv)


def html2bbcode_main(argv=None):
    """Run the html2bbcode command."""
    run(_html2bbcode, argv)


def md2ast_main(argv=None):
    """Run the md2ast command."""
    run(_md2ast, argv)


if __name__ == '__main__':
    main()
