Inline HTML in prose: <b>bold</b>, <strong>strong</strong>, <i>italic</i>, <em>em</em>, <u>underline</u>, <ins>ins</ins>, <s>s</s>, <del>del</del>, <strike>strike</strike>, <sup>sup</sup>, <sub>sub</sub>, <mark>mark</mark>, <kbd>Ctrl</kbd>+<kbd>C</kbd>, <code>code</code>.

Mixed with markdown: <b>bold with *italic* inside</b> and **bold with <i>html italic</i> inside**.

Links and images: <a href="https://example.com">link</a>, <a href="#section">jump</a>, <a name="section">target</a>, <a id="other">id target</a>, <a href="mailto:me@example.com?subject=Hi">mail</a>, <img src="https://example.com/a.png" alt="alt text">, <img src="https://example.com/b.png">, <img src="https://example.com/c.svg" alt="svg">, <img alt="no src">.

Abbr: <abbr title="World Health Organization">WHO</abbr> and <abbr>no title</abbr>.

Fonts: <font color="red" size="3" face="Times New Roman">font tag</font>, <font color="not a color!" size="huge">bad values</font>, <span style="color: #f00; font-size: 12px; font-family: Arial, sans-serif; font-weight: bold; font-style: italic; text-decoration: underline line-through;">styled span</span>, <span style="font-weight: 700">weight 700</span>, <span style="color: rgb(1, 2, 3) !important">important</span>, <span>plain span</span>.

Mis-nested: <b><i>bold italic</b></i> end.

Stray closers: before </b> after, before </custom> after.

Unknown: <custom-tag data-x="1"><b>Bold</b></custom-tag> and <video src="x.mp4"></video>.

Entities inside HTML: <span>&amp;lt; and &copy;</span>, in code: `&amp;lt;`.

Comment inline: before <!-- hidden --> after.

Code span containing HTML: `<font color="red">Code</font>` stays literal.
