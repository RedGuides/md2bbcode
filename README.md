[![Publish to PyPI](https://github.com/RedGuides/md2bbcode/actions/workflows/publish.yml/badge.svg)](https://github.com/RedGuides/md2bbcode/actions/workflows/publish.yml)

![md2bbcode logo, original image 'A Specious Origin' by Jerry LoFaro.](https://www.redguides.com/images/md2bbcode-logo.png)

# md2bbcode
**A wrapper and plugin for [Mistune](https://github.com/lepture/mistune).** It converts most GitHub-flavored Markdown to Xenforo-flavored BBCode. 

> [!TIP]
> Custom BBCodes made for RedGuides are included in [`bb_codes.xml`](src/md2bbcode/dialects/bb_codes.xml), import the ones you want in your Xenforo installation at `admin.php?bb-codes`. Some custom BBCodes include css, which you can split off to your extra.css template for more efficiency. Running a different board? [Give md2bbcode your own export](#your-boards-custom-bb-codes).

> [!NOTE]  
> This project is made with LLM assistance (derogatory).

## Installation

Install as a CLI tool with [pipx](https://pipx.pypa.io):

```bash
pipx install md2bbcode
```

## Usage

After installation, you can use md2bbcode from the command line:

```bash
md2bbcode README.md
```

Output prints to stdout as UTF-8. To write straight to a file (recommended on Windows, where shell > redirection can mangle the encoding), use `-o`:

```bash
md2bbcode README.md -o output.bbcode
```

For relative links and images, set their base URLs. GitHub needs `blob` URLs for links and raw URLs for images:

```bash
md2bbcode README.md --link-base https://github.com/RedGuides/md2bbcode/blob/main/ --image-base https://raw.githubusercontent.com/RedGuides/md2bbcode/main/
```

`--domain URL` sets both bases. If only one base is given, links and images share it. Full URLs, `//host/path` and `#anchor` links stay unchanged.

### Your board's custom BB codes

XenForo has no built-in tag for highlights, superscript, subscript, abbreviations, anchors or GitHub-style admonitions, so md2bbcode writes those with custom BB codes. By default it assumes your board has the RedGuides set. If it has its own, export them at `admin.php?bb-codes` and hand over the file:

```bash
md2bbcode README.md --bb-codes bb_codes.xml
```

md2bbcode reads what each BB code does, not what it is called: if your board turns `[highlight]` into `<mark>{text}</mark>`, then `==text==` becomes `[HIGHLIGHT]text[/HIGHLIGHT]`. Anything your board lacks is written with built-in tags instead, so nothing shows up as literal `[MARK]` in a post.

| Markdown or HTML | Found in your export by | Without it |
| --- | --- | --- |
| `==highlight==`, `<mark>` | `<mark>{text}</mark>`, or the name `mark` | plain text |
| `<sup>`, `<sub>`, footnote numbers | `<sup>{text}</sup>`, `<sub>{text}</sub>`, or the names `sup`, `sub` | plain text |
| abbreviations, `<abbr>` | `<abbr title="{option}">{text}</abbr>`, or the name `abbr` | plain text |
| `<a href="#x">`, footnote links | `<a href="#{option}">{text}</a>` | `[URL=#x]`, which works on any Xenforo |
| `<a name="x">`, footnote targets | `<a name="{option}">{text}</a>` (or `id`) | plain text, and footnote numbers stop linking, since there is nothing to land on |
| `> [!NOTE]` alerts | the name `admonition`, with an option | a quote that starts with **Note:** |
| images with alt text starting "pixel" | the name `pixelate` | a normal image |

For a board with no custom BB codes at all, use `--no-custom-bbcode`. To check what was picked up, add `--dump-config`.

Some things have no BBCode of their own and are put together from the tags above. A footnote number is superscript and links to its footnote; an alert is an `[admonition]`. How they are put together is a line each in your config (next section), where you can also name a BB code md2bbcode did not recognise:

```toml
bb_codes = "bb_codes.xml"

[tags]
admonition    = "[ALERT={kind}]{text}[/ALERT]"   # {kind} is "note", {label} is "Note"
footnote_ref  = "[U]{link}[/U]"                   # {link} is the number, linked if your board has anchors
footnote_item = "{target}. {text}"                # {target} is the number, as the anchor the link lands on
```

### Changing a tag

Every tag md2bbcode writes is a setting in a TOML file of your own. Write the current ones out, edit, and pass it back:

```bash
md2bbcode --dump-config -o myboard.toml
md2bbcode README.md --config myboard.toml
```

Your file only needs the lines that differ, so this is a complete config:

```toml
[tags]
codespan = "[code]{text}[/code]"
```

`{text}` keeps the content inside a tag. Use `"{text}"` alone to remove the tag. The config covers HTML in your Markdown too, since it is converted with the same tags.

You can also use env vars, `MD2BBCODE_CONFIG` and `MD2BBCODE_BB_CODES` in place of `--config` and `--bb-codes`.

`<video>` and `<audio>` become a link to the file. XenForo plays media only through attachments and its media sites, and a README can address neither, so a link is the closest it gets.

Other HTML that has no BBCode, such as `<iframe>`, is kept as written. To remove those tags and keep their content, add this to the top of your config:

```toml
unknown_html = "strip"
```

You can also use the package in your Python project:

```python
from md2bbcode import process_readme

bbcode = process_readme("# Hell World")
print(bbcode)
```

Set `link_base` and `image_base` for relative URLs, or `domain` for both:

```python
bbcode = process_readme(
    markdown_text,
    link_base="https://github.com/yourusername/yourrepo/blob/main/",
    image_base="https://raw.githubusercontent.com/yourusername/yourrepo/main/",
)
```

Pass a custom config as `dialect`:

```python
from md2bbcode import Dialect, process_readme

bbcode = process_readme(markdown_text, dialect=Dialect.load("myboard.toml"))
```

Or just your board's BB code export (`bb_codes=False` for a board with none):

```python
bbcode = process_readme(markdown_text, dialect=Dialect.defaults(bb_codes="bb_codes.xml"))
```

### Debug Mode

To see how your Markdown and HTML were read, use [md2ast](#md2ast). The `--debug` flag also saves the result to `readme.finalpass`:

```bash
md2bbcode README.md --debug
```
## Development

If you want to contribute to md2bbcode or set up a development environment, follow these steps:

1. Clone the repository:
   ```bash
   git clone https://github.com/RedGuides/md2bbcode.git
   cd md2bbcode
   ```

2. Create a development environment and install dependencies:
   ```bash
   hatch env create
   ```

3. Activate the development environment:
   ```bash
   hatch shell
   ```

### renderers/bbcode.py

The custom plugin for Mistune, which converts AST to bbcode.[^1]

[^1]: Mistune does not convert Markdown HTML to AST, so `plugins.py` and `html_tokens.py` do that first.

## Additional Tools

### html2bbcode

Converts most HTML tags typically allowed in Github Flavored Markdown to BBCode.[^2]

[^2]: It converts HTML the same way `md2bbcode` converts the HTML inside Markdown. Reference: https://github.github.com/gfm/#raw-html

```bash
html2bbcode input_file.html
```

### md2ast

For debugging, converts a Markdown file to the AST (JSON format) that the BBCode renderer works from, with HTML already turned into tokens.

```bash
md2ast input.md output.json
```

## Features Test

Here are a few GitHub-flavored Markdown features so you can use this README.md for testing, including the table:

  | Feature       | Markdown        | Rendered        |
  | :------------ | :-------------: | ---------------:|
  | Bold         | `**text**`      | **bold**        |
  | Italic       | `*text*`        | *italic*        |
  | Strikethrough| `~~text~~`      | ~~struck~~      |
  | Code         | `` `code` ``    | `inline`        |
  | Link         | `[text](url)`   | [example](https://example.com) |
  | Superscript  | `<sup>2</sup>`  | E=mc<sup>2</sup> |
  | Subscript    | `<sub>2</sub>`  | H<sub>2</sub>O  |

<details>
<summary>HTML spoiler (details/summary)</summary>

<b>html2bbcode</b> test. This is hidden content. Water is H<sub>2</sub>O.

<font color="red" size="3" face="Arial">Font tag inside details size 3 Arial red</font>

<span style="color: #27F573; font-size: 12px; font-family: Times New Roman; font-weight: bold; font-style: italic; text-decoration: underline line-through;">Inline style inside details green times new roman strikethrough italic bold underline</span>
<blockquote data-author="John Doe">This is a quote by John Doe</blockquote>
</details>