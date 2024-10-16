![md2bbcode logo](https://www.redguides.com/images/md2bbcode-logo.png)

# md2bbcode
**A wrapper and plugin for [Mistune](https://github.com/lepture/mistune).** It converts GitHub-flavored Markdown to Xenforo-flavored BBCode. Custom BBCodes made for RedGuides are included in `bb_codes.xml`.

## Installation

You can install md2bbcode using pip:

```bash
pip install md2bbcode
```

## Usage

After installation, you can use md2bbcode from the command line:

```bash
md2bbcode README.md
```

If the markdown includes relative images or other assets, you can use the --domain flag to prepend a domain to the relative URLs:

```bash
md2bbcode README.md --domain https://raw.githubusercontent.com/RedGuides/md2bbcode/main/
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

2. Install Hatch, which is used for building and managing the project:
   ```bash
   pip install hatch
   ```

3. Create a development environment and install dependencies:
   ```bash
   hatch env create
   ```

4. Activate the development environment:
   ```bash
   hatch shell
   ```

### renderers/bbcode.py

The custom plugin for Mistune, which converts AST to bbcode.[^1]

[^1]: Mistune does not convert Markdown HTML to AST, hence the need for `html2bbcode`.

## Additional Tools

### html2bbcode

Converts several HTML tags typically allowed in Markdown to BBCode.[^2]

[^2]: Currently used for post-processing mistune output, but there's a better way. See inside the file for a suggestion.

```bash
html2bbcode input_file.html
```

### md2ast

For debugging Mistune's renderer, converts a Markdown file to AST (JSON format).

```bash
md2ast input.md output.json
```

## Features Test

Here are a few GitHub-flavored Markdown features so you can use this README.md for testing:

- **Strikethrough:** ~~This text is struck through.~~
- **Superscript:** This text is normal and this is <sup>superscript</sup>.
- **Table:**

  | Syntax      | Description |
  | ----------- | ----------- |
  | Header      | Title       |
  | Paragraph   | Text        |

## Todo

- refactor html2bbcode
- update for new Xenforo 2.3 and 2.4 BBCode
