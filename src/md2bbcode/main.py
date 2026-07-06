# uses a custom mistune renderer to convert Markdown to BBCode. The custom renderer is defined in the bbcode.py file.
# pass --debug to save the output to readme.1stpass (main.py) and readme.finalpass (html2bbcode)
# for further debugging, you can convert the markdown file to AST using md2ast.py. Remember to load the plugin(s) you want to test.

#standard library
import argparse
import sys


def _write_output(text, output_path=None):
    # Always emit UTF-8; Windows stdout otherwise defaults to a legacy code
    # page and raises UnicodeEncodeError on characters like emoji.
    if output_path is not None:
        with open(output_path, 'w', encoding='utf-8', newline='') as out_file:
            out_file.write(text)
            if not text.endswith('\n'):
                out_file.write('\n')
        return

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        buffer = getattr(sys.stdout, 'buffer', None)
        if buffer is not None:
            buffer.write((text + '\n').encode('utf-8'))
            buffer.flush()
            return
    print(text)

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

def convert_markdown_to_bbcode(markdown_text, domain):
    # Create a Markdown parser instance using the custom BBCode renderer
    markdown_parser = mistune.create_markdown(renderer=BBCodeRenderer(domain=domain), plugins=[strikethrough, mark, superscript, subscript, insert, table, footnotes, task_lists, def_list, abbr, spoiler, table_in_list, merge_ordered_lists])

    # Convert Markdown text to BBCode
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

def main():
    parser = argparse.ArgumentParser(description='Convert Markdown file to BBCode with HTML processing.')
    parser.add_argument('input', help='Input Markdown file path (use "-" for stdin)')
    parser.add_argument('-o', '--output', help='Output BBCode file path (UTF-8). Recommended on Windows instead of shell redirection. Use "-" or omit for stdout.')
    parser.add_argument('--domain', help='Domain to prepend to relative URLs')
    parser.add_argument('--debug', action='store_true', help='Output intermediate results to files for debugging')
    args = parser.parse_args()

    if args.input == '-':
        # Read Markdown content from stdin
        markdown_text = sys.stdin.read()
    else:
        with open(args.input, 'r', encoding='utf-8') as md_file:
            markdown_text = md_file.read()

    # Process the readme and get the final BBCode
    final_bbcode = process_readme(markdown_text, args.domain, args.debug)

    # Always emit the final BBCode to -o/stdout (debug mode also writes readme.1stpass/readme.finalpass).
    output_path = args.output if args.output and args.output != '-' else None
    _write_output(final_bbcode, output_path)

if __name__ == '__main__':
    main()
