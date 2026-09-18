# Heading one

## Heading two

### Heading three

#### Heading four

##### Heading five

###### Heading six

Plain paragraph with **bold**, *italic*, ***both***, ~~struck~~, ==marked==, ^^inserted^^,
a soft
line break, and a hard break at the end of this line.  
Next line after the hard break. Inline `code` and a longer `` `nested` `` code span.

E=mc^2^ and H~2~O. Entities: &copy; 2024, 5 &lt; 6 &amp; 7 &gt; 3. Literal: 5 < 6 and a lone & ampersand.

Inline >!spoiler text!< in a sentence.

>! Block spoiler line one
>! Block spoiler line two

---

> A blockquote
> that wraps.
>
> > Nested quote.

> [!NOTE]
> A note.

> [!TIP]
> A tip with `code`.

> [!IMPORTANT]
> Important.

> [!WARNING]
> Warning.

> [!CAUTION]
> Caution.

> [!FOO]
> Not an alert.

```bash
echo "fenced with a language"
```

```
no language
```

```plaintext
plaintext language maps to bare CODE
```

```python title="example.py"
print("info string with extra words")
```

    indented code block
    second line

Code with blank lines inside:

```
line one

line three
```

- Bullet one
- Bullet two
  - Nested bullet
    - Deeper
- Bullet three with `code`

1. Step one
2. Step two

```bash
command after the list attaches to step two
```

3. Step three continues the merged list

4. Step four

- [ ] Unchecked task
- [x] Checked task

Term one
:   Definition one

Term two
:   Definition two

The HTML spec is maintained by the W3C.

*[HTML]: Hyper Text Markup Language
*[W3C]: World Wide Web Consortium

| Left | Center | Right | Default |
| :--- | :----: | ----: | ------- |
| a    | b      | c     | d       |
| `x`  | **y**  | *z*   | [l](https://example.com) |

- Item with a table inside

  | A | B |
  |---|---|
  | 1 | 2 |

Footnote reference one[^1] and two[^note].

[^1]: First footnote.
[^note]: Second footnote with **bold**.

Links: [absolute](https://example.com/path?q=1&r=2 "Title"), [relative](docs/guide.md),
[anchor](#heading-two), [mailto](mailto:someone@example.com), [protocol relative](//example.com/x),
[harmful](javascript:alert(1)), <https://autolink.example.com>, and bare https://bare.example.com.

Images: ![png](https://example.com/image.png), ![svg](https://example.com/logo.svg),
![pixel art alt](https://example.com/sprite.png), ![](https://example.com/noalt.png),
![relative](images/local.png),
[![badge](https://github.com/o/r/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/o/r/actions),
![data svg](data:image/svg+xml;base64,AAAA).

Final paragraph.
