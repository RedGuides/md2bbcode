[![Publish to PyPI](https://github.com/RedGuides/md2bbcode/actions/workflows/publish.yml/badge.svg)](https://github.com/RedGuides/md2bbcode/actions/workflows/publish.yml)

![md2bbcode logo, original image 'A Specious Origin' by Jerry LoFaro.](https://www.redguides.com/images/md2bbcode-logo.png)

# md2bbcode
**A wrapper and plugin for [Mistune](https://github.com/lepture/mistune).** It converts most GitHub-flavored Markdown to Xenforo-flavored BBCode. 

> [!TIP]
> Custom BBCodes made for RedGuides are included in `bb_codes.xml`, import the ones you want in your Xenforo installation at `admin.php?bb-codes`. Some custom BBCodes include css, which you can split off to your extra.css template for more efficiency.

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

### Other forums

XenForo is the default. To change a tag, add it to a TOML config:

```toml
extends = "xenforo"

[tags]
codespan = "[code]{text}[/code]"
```

```bash
md2bbcode README.md --config myboard.toml
```

`{text}` keeps the content inside a tag. Use `"{text}"` alone to remove the tag.

To export all settings as a config file:

```bash
md2bbcode --dump-config -o myboard.toml
```

`--config` falls back to the `MD2BBCODE_CONFIG` environment variable.

For HTML, only inline code, spoilers and paragraph spacing use the config. Other tags still use XenForo BBCode.

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

### Debug Mode

You can use the `--debug` flag to save intermediate results to files for debugging:

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

[^1]: Mistune does not convert Markdown HTML to AST, hence the need for `html2bbcode`.

## Additional Tools

### html2bbcode

Converts most HTML tags typically allowed in Github Flavored Markdown to BBCode.[^2]

[^2]: Currently used for post-processing mistune output. Reference: https://github.github.com/gfm/#raw-html

```bash
html2bbcode input_file.html
```

### md2ast

For debugging Mistune's renderer, converts a Markdown file to AST (JSON format).

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