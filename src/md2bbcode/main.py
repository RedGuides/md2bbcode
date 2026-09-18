# uses a custom mistune renderer to convert Markdown to BBCode. The custom renderer is defined in the bbcode.py file.
# pass --debug to save the output to readme.1stpass (main.py) and readme.finalpass (html2bbcode)
# for further debugging, use md2ast to see how mistune reads the Markdown. It uses the same plugins as the BBCode converter.

# standard library
import argparse
import functools
import json
import sys
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
from md2bbcode.plugins.merge_lists import merge_ordered_lists
from md2bbcode.renderers.bbcode import BBCodeRenderer
from md2bbcode.html2bbcode import process_html

PLUGINS = [strikethrough, mark, superscript, subscript, insert, table, footnotes, task_lists, def_list, abbr, spoiler, table_in_list, merge_ordered_lists]


# conversion functions

def convert_markdown_to_bbcode(markdown_text, domain):
    # Create a Markdown parser instance using the custom BBCode renderer
    markdown_parser = mistune.create_markdown(renderer=BBCodeRenderer(domain=domain), plugins=PLUGINS)

    # Convert Markdown text to BBCode
    return markdown_parser(markdown_text)


def convert_markdown_to_ast(markdown_text):
    """Show how mistune reads the Markdown before turning it into BBCode, for debugging."""
    markdown_parser = mistune.create_markdown(renderer=None, plugins=PLUGINS)
    return markdown_parser(markdown_text)


def process_readme(markdown_text, domain=None, debug=False):
    # Convert Markdown to BBCode
    bbcode_text = convert_markdown_to_bbcode(markdown_text, domain)

    # If debug mode, save intermediate BBCode
    if debug:
        with open('readme.1stpass', 'w', encoding='utf-8') as file:
            file.write(bbcode_text)

    # Convert BBCode formatted as HTML to final BBCode
    final_bbcode = process_html(bbcode_text, debug, 'readme.finalpass', domain=domain)

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
    parser.add_argument('input', help='Markdown file to convert (use "-" to read piped input)')
    _add_output_argument(parser)
    parser.add_argument('--domain', help='Domain to prepend to relative URLs')
    parser.add_argument('--debug', action='store_true', help='Save each conversion step to readme.1stpass and readme.finalpass for debugging')
    _add_version_argument(parser)
    args = parser.parse_args(argv)

    # Read and convert the whole input before writing the result.
    markdown_text = read_input(args.input)
    final_bbcode = process_readme(markdown_text, args.domain, args.debug)
    write_output(final_bbcode, args.output)


def _html2bbcode(argv=None):
    parser = argparse.ArgumentParser(prog="html2bbcode", description="Convert an HTML file to BBCode.")
    parser.add_argument("input", help='HTML file to convert (use "-" to read piped input)')
    _add_output_argument(parser)
    parser.add_argument("--debug", action="store_true", help="Save output to readme.finalpass for debugging")
    _add_version_argument(parser)
    args = parser.parse_args(argv)

    html_content = read_input(args.input)
    converted_bbcode = process_html(html_content, debug=args.debug)
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
