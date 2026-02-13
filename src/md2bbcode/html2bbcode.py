# converts some HTML tags to BBCode
# pass --debug to save the output to readme.finalpass
import argparse
import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from md2bbcode.image_rewrite import rewrite_svg_url

# XenForo (2.3.x) built-in BBCode option validation (see XF\BbCode\RuleSet::addDefaultTags()).
_XF_COLOR_OPTION_RE = re.compile(
    r"^(rgb\(\s*\d+%?\s*,\s*\d+%?\s*,\s*\d+%?\s*\)|#[a-f0-9]{6}|#[a-f0-9]{3}|[a-z]+)$",
    re.IGNORECASE,
)
_XF_FONT_OPTION_RE = re.compile(r"^[a-z0-9 \-]+$", re.IGNORECASE)
_XF_SIZE_OPTION_RE = re.compile(r"^[0-9]+(px)?$", re.IGNORECASE)

_TOKEN_RE = re.compile("\x1A(\\d+)\x1A")


def _strip_important(value: str) -> str:
    # Common in inline CSS; XF doesn't accept it in BBCode options.
    return value.replace("!important", "").strip()


def _sanitize_color(value: str) -> Optional[str]:
    value = _strip_important(value.strip().strip('"').strip("'"))
    return value if value and _XF_COLOR_OPTION_RE.match(value) else None


def _sanitize_size(value: str) -> Optional[str]:
    value = _strip_important(value.strip().strip('"').strip("'"))
    return value if value and _XF_SIZE_OPTION_RE.match(value) else None


def _sanitize_font(value: str) -> Optional[str]:
    value = _strip_important(value.strip())
    # CSS font-family often includes fallbacks: "Arial", sans-serif
    if "," in value:
        value = value.split(",", 1)[0]
    value = value.strip().strip('"').strip("'")
    # XF allows letters/numbers/spaces/hyphens. Drop other characters safely.
    value = re.sub(r"[^a-z0-9 \-]+", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip()
    return value if value and _XF_FONT_OPTION_RE.match(value) else None


def _safe_url(url: str, domain: Optional[str]) -> str:
    # Simple URL sanitization matching BBCodeRenderer.safe_url.
    if url.startswith(("javascript:", "vbscript:", "data:")):
        return "#harmful-link"
    if domain and not urlparse(url).netloc:
        return urljoin(domain, url)
    return url


def _add_token(tokens: List[str], original: str) -> str:
    token_id = len(tokens)
    token = f"\x1A{token_id}\x1A"
    tokens.append(original)
    return token


def _stash_bbcode_plain_items(text: str) -> Tuple[str, List[str]]:
    """
    Stash BBCode segments that must be treated as "plain" so we don't accidentally
    parse/convert HTML inside them (e.g. inline code that contains <font>...).

    Mirrors the spirit of XF's own Markdown stashing of plain tags.
    """
    tokens: List[str] = []
    # Tags that XF treats as plain or that should not be HTML-parsed in our pipeline.
    plain_tags = ("code", "icode", "php", "html", "plain", "media", "img", "user", "attach")
    plain_tags_regex = "|".join(plain_tags)

    pattern = re.compile(
        rf"\[(?P<tag>{plain_tags_regex})(?:[^\]]*)\](?P<content>.*?)\[/\1\]",
        re.IGNORECASE | re.DOTALL,
    )

    def repl(match: "re.Match") -> str:
        return _add_token(tokens, match.group(0))

    return pattern.sub(repl, text), tokens


def _restore_tokens(text: str, tokens: List[str]) -> str:
    def repl(match: "re.Match") -> str:
        idx = int(match.group(1))
        return tokens[idx] if 0 <= idx < len(tokens) else ""

    return _TOKEN_RE.sub(repl, text)


class HtmlToBbCodeConverter:
    def __init__(self, domain: Optional[str] = None) -> None:
        self.domain = domain or ""
        self.handlers = {
            "details": self._handle_details,
            "font": self._handle_font,
            "span": self._handle_span,
            "div": self._handle_div,
            "sup": lambda tag: self._wrap_simple(tag, "SUP"),
            "sub": lambda tag: self._wrap_simple(tag, "SUB"),
            "b": lambda tag: self._wrap_simple(tag, "B"),
            "strong": lambda tag: self._wrap_simple(tag, "B"),
            "i": lambda tag: self._wrap_simple(tag, "I"),
            "em": lambda tag: self._wrap_simple(tag, "I"),
            "u": lambda tag: self._wrap_simple(tag, "U"),
            "s": lambda tag: self._wrap_simple(tag, "S"),
            "del": lambda tag: self._wrap_simple(tag, "S"),
            "strike": lambda tag: self._wrap_simple(tag, "S"),
            "ins": lambda tag: self._wrap_simple(tag, "U"),
            "mark": lambda tag: self._wrap_simple(tag, "MARK"),
            "kbd": self._handle_kbd,
            "br": lambda tag: "\n",
            "hr": lambda tag: "[HR][/HR]\n",
            "a": self._handle_link,
            "img": self._handle_image,
            "p": self._handle_paragraph,
            "blockquote": self._handle_blockquote,
            "pre": self._handle_pre,
            "code": self._handle_code,
            "ul": lambda tag: self._handle_list(tag, ordered=False),
            "ol": lambda tag: self._handle_list(tag, ordered=True),
            "li": self._handle_list_item,
            "table": self._handle_table,
            "thead": self._handle_passthrough_children,
            "tbody": self._handle_passthrough_children,
            "tfoot": self._handle_passthrough_children,
            "tr": self._handle_table_row,
            "th": lambda tag: self._handle_table_cell(tag, head=True),
            "td": lambda tag: self._handle_table_cell(tag, head=False),
            "abbr": self._handle_abbr,
        }

    def convert(self, html: str) -> str:
        # Avoid parsing HTML inside BBCode plain-ish tags like [ICODE]...[/ICODE].
        stashed, tokens = _stash_bbcode_plain_items(html)
        soup = BeautifulSoup(stashed, "html.parser")
        root = soup.body or soup
        converted = self._convert_children(root)
        return _restore_tokens(converted, tokens)

    def _convert_children(self, tag: Tag) -> str:
        return "".join(self._convert_node(child) for child in tag.contents)

    def _convert_node(self, node) -> str:
        if isinstance(node, Comment):
            return f"<!--{node}-->"
        if isinstance(node, NavigableString):
            return str(node)
        if isinstance(node, Tag):
            handler = self.handlers.get(node.name.lower())
            if handler:
                return handler(node)
            return str(node)
        return ""

    def _wrap(self, content: str, wrappers: List[Tuple[str, Optional[str]]]) -> str:
        for tag, value in reversed(wrappers):
            if value is None:
                content = f"[{tag}]{content}[/{tag}]"
            else:
                content = f"[{tag}={value}]{content}[/{tag}]"
        return content

    def _wrap_simple(self, tag: Tag, bbcode_tag: str) -> str:
        content = self._convert_children(tag)
        content = f"[{bbcode_tag}]{content}[/{bbcode_tag}]"
        return self._apply_style_wrappers(tag, content, skip_tags={bbcode_tag})

    def _parse_style(self, style: str) -> Dict[str, str]:
        css_properties: Dict[str, str] = {}
        for item in style.split(";"):
            if ":" not in item:
                continue
            key, value = item.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key:
                css_properties[key] = value
        return css_properties

    def _style_wrappers(
        self,
        tag: Tag,
        skip_tags: Optional[Set[str]] = None,
        skip_props: Optional[Set[str]] = None,
    ) -> List[Tuple[str, Optional[str]]]:
        style = tag.attrs.get("style", "")
        if not style:
            return []
        css_properties = self._parse_style(style)
        wrappers: List[Tuple[str, Optional[str]]] = []
        skip_tags = {t.upper() for t in (skip_tags or set())}
        skip_props = set(skip_props or set())

        if "color" in css_properties and "color" not in skip_props:
            color = _sanitize_color(css_properties["color"])
            if color:
                wrappers.append(("COLOR", color))
        if "font-size" in css_properties and "size" not in skip_props:
            size = _sanitize_size(css_properties["font-size"])
            if size:
                wrappers.append(("SIZE", size))
        if "font-family" in css_properties and "font" not in skip_props:
            face = _sanitize_font(css_properties["font-family"])
            if face:
                wrappers.append(("FONT", face))
        if "text-decoration" in css_properties:
            decoration = css_properties["text-decoration"].lower()
            if "line-through" in decoration and "S" not in skip_tags:
                wrappers.append(("S", None))
            if "underline" in decoration and "U" not in skip_tags:
                wrappers.append(("U", None))
        if "font-weight" in css_properties and "B" not in skip_tags:
            weight = css_properties["font-weight"].lower()
            if weight == "bold" or (weight.isdigit() and int(weight) >= 700):
                wrappers.append(("B", None))
        if "font-style" in css_properties and "I" not in skip_tags:
            style_val = css_properties["font-style"].lower()
            if style_val in {"italic", "oblique"}:
                wrappers.append(("I", None))

        return wrappers

    def _apply_style_wrappers(
        self,
        tag: Tag,
        content: str,
        skip_tags: Optional[Set[str]] = None,
        skip_props: Optional[Set[str]] = None,
    ) -> str:
        wrappers = self._style_wrappers(tag, skip_tags=skip_tags, skip_props=skip_props)
        return self._wrap(content, wrappers) if wrappers else content

    def _handle_details(self, tag: Tag) -> str:
        summary = tag.find("summary")
        spoiler_title = ""
        if summary:
            spoiler_title = self._convert_children(summary).strip()
            summary.decompose()
        content = self._convert_children(tag)
        if spoiler_title:
            return f"[SPOILER={spoiler_title}]{content}[/SPOILER]"
        return f"[SPOILER]{content}[/SPOILER]"

    def _handle_font(self, tag: Tag) -> str:
        wrappers: List[Tuple[str, Optional[str]]] = []
        skip_props: Set[str] = set()
        if "color" in tag.attrs:
            color = _sanitize_color(tag["color"])
            if color:
                wrappers.append(("COLOR", color))
                skip_props.add("color")
        if "size" in tag.attrs:
            size = _sanitize_size(tag["size"])
            if size:
                wrappers.append(("SIZE", size))
                skip_props.add("size")
        if "face" in tag.attrs:
            face = _sanitize_font(tag["face"])
            if face:
                wrappers.append(("FONT", face))
                skip_props.add("font")

        content = self._convert_children(tag)
        wrappers.extend(self._style_wrappers(tag, skip_props=skip_props))
        return self._wrap(content, wrappers) if wrappers else content

    def _handle_span(self, tag: Tag) -> str:
        content = self._convert_children(tag)
        if tag.attrs.get("style"):
            content = self._apply_style_wrappers(tag, content)
        return content

    def _handle_div(self, tag: Tag) -> str:
        content = self._convert_children(tag)
        content = self._apply_style_wrappers(tag, content)
        align = self._extract_alignment(tag)
        if align:
            content = self._wrap_alignment(content, align)
        return content

    def _handle_kbd(self, tag: Tag) -> str:
        content = tag.get_text()
        return f"[ICODE]{content}[/ICODE]"

    def _handle_link(self, tag: Tag) -> str:
        href = tag.attrs.get("href")
        name = tag.attrs.get("name") or tag.attrs.get("id")
        if href:
            href = href.strip()
            if href.lower().startswith("mailto:"):
                email = href[7:].strip()
                if "?" in email:
                    email = email.split("?", 1)[0]
                if email:
                    return f"[EMAIL]{email}[/EMAIL]"
            text = self._convert_children(tag)
            if href.startswith("#"):
                anchor = href[1:]
                if anchor:
                    return f"[JUMPTO={anchor}]{text}[/JUMPTO]"
            return f"[URL={_safe_url(href, self.domain)}]{text}[/URL]"
        if name:
            text = self._convert_children(tag)
            return f"[ANAME={name}]{text}[/ANAME]"
        return str(tag)

    def _handle_image(self, tag: Tag) -> str:
        src = tag.attrs.get("src")
        if not src:
            return str(tag)
        alt = tag.attrs.get("alt", "")
        safe_src = _safe_url(src, self.domain)
        rewritten_url = rewrite_svg_url(safe_src)
        if rewritten_url is None:
            link_text = alt or safe_src
            return f"[URL={safe_src}]{link_text}[/URL]"
        alt_text = f' alt="{alt}"' if alt else ""
        return f"[IMG{alt_text}]{rewritten_url}[/IMG]"

    def _handle_paragraph(self, tag: Tag) -> str:
        content = self._convert_children(tag)
        content = self._apply_style_wrappers(tag, content)
        align = self._extract_alignment(tag)
        if align:
            content = self._wrap_alignment(content, align)
        return f"{content}\n\n"

    def _handle_blockquote(self, tag: Tag) -> str:
        content = self._convert_children(tag)
        content = self._apply_style_wrappers(tag, content)
        align = self._extract_alignment(tag)
        if align:
            content = self._wrap_alignment(content, align)
        attribution = self._extract_blockquote_attribution(tag)
        if attribution:
            attribution = attribution.replace('"', "'")
            return f'[QUOTE="{attribution}"]\n{content}[/QUOTE]\n'
        return f"[QUOTE]\n{content}[/QUOTE]\n"

    def _extract_code_language(self, tag: Tag) -> Optional[str]:
        classes = tag.attrs.get("class", [])
        if isinstance(classes, str):
            classes = classes.split()
        for cls in classes:
            if cls.startswith("language-"):
                return cls.split("language-", 1)[1]
            if cls.startswith("lang-"):
                return cls.split("lang-", 1)[1]
        return None

    def _handle_pre(self, tag: Tag) -> str:
        code_tag = tag.find("code")
        if code_tag:
            lang = self._extract_code_language(code_tag)
            code_text = code_tag.get_text()
        else:
            lang = self._extract_code_language(tag)
            code_text = tag.get_text()

        if lang:
            return f"[CODE={lang}]{code_text}[/CODE]\n"
        return f"[CODE]{code_text}[/CODE]\n"

    def _handle_code(self, tag: Tag) -> str:
        if tag.parent and isinstance(tag.parent, Tag) and tag.parent.name.lower() == "pre":
            return ""
        content = tag.get_text()
        return f"[ICODE]{content}[/ICODE]"

    def _handle_list(self, tag: Tag, ordered: bool) -> str:
        content = self._convert_children(tag)
        list_tag = "LIST=1" if ordered else "LIST"
        return f"[{list_tag}]{content}[/LIST]\n"

    def _handle_list_item(self, tag: Tag) -> str:
        content = self._convert_children(tag)
        return f"[*]{content}\n"

    def _handle_table(self, tag: Tag) -> str:
        content = self._convert_children(tag)
        return f"[TABLE]\n{content}[/TABLE]\n"

    def _handle_passthrough_children(self, tag: Tag) -> str:
        return self._convert_children(tag)

    def _handle_table_row(self, tag: Tag) -> str:
        content = self._convert_children(tag)
        return f"[TR]\n{content}[/TR]\n"

    def _extract_alignment(self, tag: Tag) -> Optional[str]:
        align = tag.attrs.get("align")
        if align:
            return align.strip().lower()
        style = tag.attrs.get("style", "")
        if not style:
            return None
        css = self._parse_style(style)
        if "text-align" in css:
            return css["text-align"].strip().lower()
        return None

    def _wrap_alignment(self, content: str, align: str) -> str:
        if align == "center":
            return f"[CENTER]{content}[/CENTER]"
        if align == "right":
            return f"[RIGHT]{content}[/RIGHT]"
        if align == "left":
            return f"[LEFT]{content}[/LEFT]"
        return content

    def _extract_blockquote_attribution(self, tag: Tag) -> Optional[str]:
        for key in (
            "data-quote",
            "data-attribution",
            "data-author",
            "data-username",
            "data-cite",
            "cite",
        ):
            value = tag.attrs.get(key)
            if value:
                value = str(value).strip()
                if value:
                    return value
        return None

    def _handle_table_cell(self, tag: Tag, head: bool) -> str:
        tag_name = "TH" if head else "TD"
        content = self._convert_children(tag)
        content = self._apply_style_wrappers(tag, content)
        align = self._extract_alignment(tag)
        if align == "center":
            content = f"[CENTER]{content}[/CENTER]"
        elif align == "right":
            content = f"[RIGHT]{content}[/RIGHT]"
        elif align == "left":
            content = f"[LEFT]{content}[/LEFT]"
        return f"[{tag_name}]{content}[/{tag_name}]\n"

    def _handle_abbr(self, tag: Tag) -> str:
        title = tag.attrs.get("title")
        if not title:
            return str(tag)
        content = self._convert_children(tag)
        return f"[ABBR={title}]{content}[/ABBR]"


def html_to_bbcode(html: str, domain: Optional[str] = None) -> str:
    converter = HtmlToBbCodeConverter(domain=domain)
    return converter.convert(html)


def process_html(input_html: str, debug: bool = False, output_file: Optional[str] = None, domain: Optional[str] = None) -> str:
    converted_bbcode = html_to_bbcode(input_html, domain=domain)

    if debug:
        if output_file is None:
            output_file = "readme.finalpass"
        with open(output_file, "w", encoding="utf-8") as file:
            file.write(converted_bbcode)
    return converted_bbcode


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Convert HTML to BBCode with optional debugging output.")
    parser.add_argument("input_file", type=str, help="Input HTML file path")
    parser.add_argument("--debug", action="store_true", help="Save output to readme.finalpass for debugging")

    args = parser.parse_args(argv)
    input_file = args.input_file
    output_file = "readme.finalpass" if args.debug else None

    with open(input_file, "r", encoding="utf-8") as file:
        html_content = file.read()

    converted_bbcode = process_html(html_content, debug=args.debug, output_file=output_file)

    # Print output unless we're in debug (file) mode.
    if not args.debug:
        print(converted_bbcode)


if __name__ == "__main__":
    main()
