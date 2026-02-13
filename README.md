[![Publish to PyPI](https://github.com/RedGuides/md2bbcode/actions/workflows/publish.yml/badge.svg)](https://github.com/RedGuides/md2bbcode/actions/workflows/publish.yml)

![md2bbcode logo, original image 'A Specious Origin' by Jerry LoFaro.](https://www.redguides.com/images/md2bbcode-logo.png)

# md2bbcode
**A wrapper and plugin for [Mistune](https://github.com/lepture/mistune).** It converts most GitHub-flavored Markdown to Xenforo-flavored BBCode. 

> [!TIP]
> Custom BBCodes made for RedGuides are included in `bb_codes.xml`, import the ones you want in your Xenforo installation at `admin.php?bb-codes`. Some custom BBCodes include css, which you can split off to your extra.css template for more efficiency.

> [!NOTE]  
> This project is made with LLM assistance.

## Usage

After installation, you can use md2bbcode from the command line:

```bash
md2bbcode README.md
```

If the markdown includes relative images or other assets, you can use the --domain flag to prepend a domain to the relative URLs:

```bash
md2bbcode README.md --domain https://raw.githubusercontent.com/RedGuides/md2bbcode/main/
```

You can also use the package in your Python project:

```python
from md2bbcode.main import process_readme

# Your Markdown content
markdown_text = "# Hell World"

# Optional domain to prepend to relative URLs
domain = 'https://raw.githubusercontent.com/yourusername/yourrepo/main/'

# Convert Markdown to BBCode
bbcode_output = process_readme(markdown_text, domain=domain)

# Output the BBCode
print(bbcode_output)
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