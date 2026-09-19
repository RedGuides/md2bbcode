[![Publish to PyPI](https://github.com/RedGuides/md2bbcode/actions/workflows/publish.yml/badge.svg)](https://github.com/RedGuides/md2bbcode/actions/workflows/publish.yml)

![md2bbcode logo, original image 'A Specious Origin' by Jerry LoFaro.](https://www.redguides.com/images/md2bbcode-logo.png)

# md2bbcode
**A wrapper and plugin for [Mistune](https://github.com/lepture/mistune).** It converts most GitHub-flavored Markdown to Xenforo-flavored BBCode. 

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

### Relative paths

Use `--domain` to turn relative links and image paths, such as `guide.md` and `images/logo.png`, into full URLs:

```bash
md2bbcode README.md --domain https://example.com/docs/
```

For GitHub, use the repo URL. This assumes you use the default branch:

```bash
md2bbcode README.md --domain https://github.com/RedGuides/md2bbcode
```

<details>
<summary>Advanced URL options</summary>

For a different GitHub branch or a README in a subfolder, pass that folder's GitHub URL to `--domain`, for example `https://github.com/RedGuides/md2bbcode/tree/dev/docs`.

For other sites, `--domain` uses the same base URL for links and images. To set separate base URLs, use `--link-base` and `--image-base`:

```bash
md2bbcode README.md --link-base https://github.com/RedGuides/md2bbcode/blob/main/ --image-base https://raw.githubusercontent.com/RedGuides/md2bbcode/main/
```

Full URLs and URLs starting with `//host/path` are left unchanged.

</details>

### Your board's custom BB codes

XenForo has no built-in tag for highlights, superscript, subscript, abbreviations, anchors, and others, so md2bbcode writes those with custom BB codes. By default it assumes your board has the RedGuides set of custom BB codes.

> [!TIP]
> The RedGuides custom BB codes are packaged for import in [bb_codes.xml](src/md2bbcode/dialects/bb_codes.xml). Import the ones you want into XenForo at `admin.php?bb-codes`. Some include CSS, which you can move to your extra.css template for more efficiency.

If your board has its own custom BB codes, export them at `admin.php?bb-codes` and hand over the file:

```bash
md2bbcode README.md --bb-codes bb_codes.xml
```

md2bbcode checks the HTML each BB code produces to find the right tag for your board. For example, if `[highlight]` produces `<mark>{text}</mark>`, then `==text==` becomes `[HIGHLIGHT]text[/HIGHLIGHT]`. Some common tag names are recognised too.

If your board has no matching BB code, md2bbcode uses a simpler alternative, such as plain text, inline code, or a quote.

Use `--no-custom-bbcode` if your board has only default Xenforo bbcode.

### Changing a tag

Put the settings you want to change in a TOML file, such as `myboard.toml`. This example changes inline code to `[CODE]` and turns off highlighting:

```toml
[tags]
codespan = "[CODE]{text}[/CODE]"
mark = "{text}"
```

`{text}` keeps the content. Using it alone removes the surrounding tag, so `==highlighted text==` becomes plain text. These settings apply to HTML in your Markdown too.

Apply your config with `--config`:

```bash
md2bbcode README.md --config myboard.toml
```

To find other tag names and see their current settings, use `--dump-config`:

```bash
md2bbcode --dump-config
```

<details>
<summary>More config options</summary>

Your config only needs the settings you want to override. Add `-o myboard.toml` to the dump command to start from a full config, or `--bb-codes bb_codes.xml` to inspect the tags detected from your board's export.

To remove unsupported HTML tags instead of keeping them, add this **above** `[tags]`. Their content is kept:

```toml
unknown_html = "strip"
```

A config can also name your board's export, so you don't need `--bb-codes` each time. The path is relative to the config file:

```toml
bb_codes = "bb_codes.xml"
```

You can use the environment variables `MD2BBCODE_CONFIG` and `MD2BBCODE_BB_CODES` instead of `--config` and `--bb-codes`.

</details>

<details>
<summary>Admonitions and footnotes</summary>

Your config can specify BB codes that md2bbcode did not recognise, or change how tags are combined. For example, a footnote reference can include both superscript formatting and a link to the footnote.

If your board has an `[ALERT]` BB code, this config uses it for GitHub alerts. It also shows how to underline footnote references and put a period after each footnote number:

```toml
bb_codes = "bb_codes.xml"

[tags]
admonition    = "[ALERT={kind}]{text}[/ALERT]"
footnote_ref  = "[U]{link}[/U]"
footnote_item = "{target}. {text}"
```

md2bbcode fills in these placeholders:

- `{kind}` is the alert type, such as `warning`. `{label}` is also available for the display name, such as `Warning`.
- `{link}` is the footnote reference number, linked when your board supports anchors.
- `{target}` is the number beside the footnote, with an anchor when supported.
- `{text}` is the content of the alert or footnote.

</details>

### HTML files

md2bbcode also installs `html2bbcode`, which converts an HTML file the same way md2bbcode converts the HTML inside Markdown. It takes the same `-o`, `--domain`, `--config` and `--bb-codes` options:

```bash
html2bbcode page.html -o output.bbcode
```

### Use in Python

You can also use the package in your Python project:

```python
from md2bbcode import convert

bbcode = convert("# Hell World")
print(bbcode)
```

Use `domain` for relative links and images, with the same automatic GitHub handling as the CLI:

```python
bbcode = convert(
    markdown_text,
    domain="https://github.com/yourusername/yourrepo",
)
```

<details>
<summary>Custom BB code in python</summary>

Use `Dialect` to apply a TOML config:

```python
from md2bbcode import Dialect, convert

bbcode = convert(markdown_text, dialect=Dialect.load("myboard.toml"))
```

Or just your board's BB code export (`bb_codes=False` for a board with none):

```python
bbcode = convert(markdown_text, dialect=Dialect.defaults(bb_codes="bb_codes.xml"))
```
</details>

## Development

You need [Hatch](https://hatch.pypa.io), which you can install with `pipx install hatch`. Then clone the repository and run the tests:

```bash
git clone https://github.com/RedGuides/md2bbcode.git
cd md2bbcode
hatch test
```

<details>
<summary>How the code fits together</summary>

- `main.py` has the commands and `convert()`.
- `plugins.py` and `html_tokens.py` turn the HTML inside Markdown into tokens, because Mistune does not.
- `renderer.py` is the Mistune renderer that turns the tokens into BBCode.
- `dialect.py` holds the tag settings, which start from `dialects/xenforo.toml`. `bb_codes.py` reads a board's BB code export.
- `image_rewrite.py` points SVG images at a service that serves them as PNG, which XenForo can show.

Each Markdown file in `tests/fixtures` has its expected BBCode saved beside it. After a change that is meant to alter the output, update the saved files and check the diff:

```bash
hatch test -- --update-goldens
```

To see how your Markdown and HTML were read, print the tokens the renderer works from. `md2ast input.md output.json` does the same:

```bash
md2bbcode README.md --ast
```

</details>
