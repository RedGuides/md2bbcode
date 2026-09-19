from md2bbcode.main import convert


def test_hard_wrapped_paragraph_keeps_word_separation():
    markdown = """Say you have a paragraph that
is formatted for a specific
length, so it has new line
characters without a space at
the end, like this text ...
""".lstrip()

    result = convert(markdown, domain="")

    assert "paragraph that is formatted" in result
    assert "specific length" in result
    assert "new line characters" in result
    assert "thatis" not in result
    assert "specificlength" not in result


def test_blank_line_still_separates_paragraphs():
    markdown = """First paragraph
wrapped here.

Second paragraph
wrapped here.
""".lstrip()

    result = convert(markdown, domain="")

    assert "First paragraph wrapped here." in result
    assert "Second paragraph wrapped here." in result
    # Paragraphs stay separate.
    assert "here. Second" not in result
    assert "\n\n" in result


def test_code_block_newlines_are_preserved():
    markdown = """```
code line 1
code line 2
```
""".lstrip()

    result = convert(markdown, domain="")

    assert "code line 1\ncode line 2" in result
    assert "code line 1 code line 2" not in result


def test_hard_break_still_emits_a_line_break():
    # Hard break stays a break.
    markdown = "before the break  \nafter the break\n"

    result = convert(markdown, domain="")

    assert "before the break\nafter the break" in result
    assert "before the break after the break" not in result


def test_wrapped_list_items_and_blockquotes_keep_separation():
    markdown = """- a list item that is
  hard wrapped too

> a blockquote that is
> hard wrapped
""".lstrip()

    result = convert(markdown, domain="")

    assert "a list item that is hard wrapped too" in result
    assert "a blockquote that is hard wrapped" in result
    assert "ishard" not in result


def test_softbreak_does_not_introduce_double_spaces():
    markdown = "one trailing space \nnext line\n"

    result = convert(markdown, domain="")

    assert "one trailing space next line" in result
    assert "space  next" not in result
