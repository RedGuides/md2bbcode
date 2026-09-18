# uses a custom mistune renderer to convert Markdown to BBCode. The custom renderer is defined in the bbcode.py file.
# HTML tags are parsed before rendering (plugins.py, html_tokens.py).
# use md2ast to see what the renderer gets, for debugging.

# standard library
import argparse
import functools
import json
import os
import sys
from urllib.parse import urlparse
from importlib.metadata import PackageNotFoundError, version as _distribution_version

# mistune
import mistune
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
from md2bbcode.renderers.bbcode import BBCodeRenderer
from md2bbcode.html2bbcode import process_html

# Use a XenForo export from the current folder if present.
LOCAL_BB_CODES = "bb_codes.xml"

PLUGINS = [strikethrough, mark, superscript, subscript, insert, table, footnotes, task_lists, def_list, abbr, spoiler, table_in_list, merge_ordered_lists]


# conversion functions

def convert_markdown_to_bbcode(markdown_text, domain=None, link_base=None, image_base=None, dialect=None):
    # Create a Markdown parser instance using the custom BBCode renderer
    renderer = BBCodeRenderer(domain=domain, link_base=link_base, image_base=image_base, dialect=dialect)
    markdown_parser = mistune.create_markdown(renderer=renderer, plugins=PLUGINS)

    # Convert Markdown text to BBCode
    return markdown_parser(markdown_text)


def convert_markdown_to_ast(markdown_text):
    """Show parsed Markdown and HTML before rendering, for debugging."""
    markdown_parser = mistune.create_markdown(renderer=None, plugins=PLUGINS)
    return pair_html(markdown_parser(markdown_text))


def process_readme(markdown_text, domain=None, debug=False, link_base=None, image_base=None, dialect=None):
    """Convert Markdown and any HTML inside it to BBCode."""
    final_bbcode = convert_markdown_to_bbcode(markdown_text, domain, link_base, image_base, dialect)

    # Save the result for debugging.
    if debug:
        with open('readme.finalpass', 'w', encoding='utf-8') as file:
            file.write(final_bbcode)

    return final_bbcode


# shared command-line functions

@functools.cache
def package_version() -> str:
    try:
        return _distribution_version("md2bbcode")
    except PackageNotFoundError:
        return "0+unknown"


class CliError(Exception):
    """An error we can explain without showing a Python traceback."""


def _force_utf8(stream) -> bool:
    try:
        stream.reconfigure(encoding="utf-8")
        return True
    except (AttributeError, ValueError, OSError):
        # Some streams don't let us change the encoding.
        return False


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


def base_urls(args) -> dict:
    """Check and return the base URLs."""
    bases = {}
    for name in ('link_base', 'image_base', 'domain'):
        value = getattr(args, name) or None
        if value is not None:
            try:
                parsed = urlparse(value)
            except ValueError:
                # Invalid URLs, such as a host with an unclosed bracket.
                parsed = None
            if parsed is None or parsed.scheme not in ('http', 'https') or not parsed.netloc:
                option = '--' + name.replace('_', '-')
                raise CliError(f"{option} must be a full URL like https://example.com/: {value}")
        bases[name] = value
    return bases


def load_dialect(args) -> Dialect:
    config = args.config or os.environ.get('MD2BBCODE_CONFIG')
    # None leaves the choice to the config, then the folder, then the export we ship.
    bb_codes = False if args.no_custom_bbcode else args.bb_codes or os.environ.get('MD2BBCODE_BB_CODES') or None
    # Look for an export in the current folder.
    found = LOCAL_BB_CODES if os.path.isfile(LOCAL_BB_CODES) else None
    try:
        if config:
            return Dialect.load(config, bb_codes=bb_codes, default_bb_codes=found)
        return Dialect.defaults(bb_codes=bb_codes, default_bb_codes=found)
    except DialectError as exc:
        raise CliError(str(exc)) from exc


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
    parser.add_argument('--debug', action='store_true', help='Also save the result to readme.finalpass (use md2ast to see the tokens)')
    _add_version_argument(parser)
    args = parser.parse_args(argv)

    dialect = load_dialect(args)
    if args.dump_config:
        write_output(dialect.to_toml(), args.output)
        return
    if args.input is None:
        parser.error('the following arguments are required: input')
    bases = base_urls(args)

    # Read and convert the whole input before writing the result.
    markdown_text = read_input(args.input)
    final_bbcode = process_readme(markdown_text, debug=args.debug, dialect=dialect, **bases)
    write_output(final_bbcode, args.output)


def _html2bbcode(argv=None):
    parser = argparse.ArgumentParser(prog="html2bbcode", description="Convert an HTML file to BBCode.")
    parser.add_argument("input", help='HTML file to convert (use "-" to read piped input)')
    _add_output_argument(parser)
    _add_url_arguments(parser)
    _add_dialect_arguments(parser)
    parser.add_argument("--debug", action="store_true", help="Save output to readme.finalpass for debugging")
    _add_version_argument(parser)
    args = parser.parse_args(argv)

    dialect = load_dialect(args)
    bases = base_urls(args)
    html_content = read_input(args.input)
    converted_bbcode = process_html(html_content, debug=args.debug, dialect=dialect, **bases)
    write_output(converted_bbcode, args.output)


def _md2ast(argv=None):
    parser = argparse.ArgumentParser(prog='md2ast', description='Show how mistune reads a Markdown file (AST in JSON format), for debugging.')
    parser.add_argument('input', help='Markdown file to convert (use "-" to read piped input)')
    parser.add_argument('output', nargs='?', default='-', help='Save the result to a JSON file. Use "-" or leave this out to print the result.')
    _add_version_argument(parser)
    args = parser.parse_args(argv)

    markdown_text = read_input(args.input)
    ast_json = json.dumps(convert_markdown_to_ast(markdown_text), indent=4)
    write_output(ast_json, args.output)


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
