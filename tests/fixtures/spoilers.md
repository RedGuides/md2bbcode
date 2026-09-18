Top-level spoiler:

<details>
<summary>Title</summary>

Some **markdown** inside.

```bash
echo inside
```

</details>

No summary:

<details>

Hidden without a title.

</details>

Summary with markup:

<details>
<summary><b>Bold</b> title with <code>code</code></summary>

Body.

</details>

Two back to back:

<details>
<summary>One</summary>

First body.

</details>
<details>
<summary>Two</summary>

Second body.

</details>

Nested:

<details>
<summary>Outer</summary>

Outer body.

<details>
<summary>Inner</summary>

Inner body.

</details>

Back in outer.

</details>

Inside a list item:

1. Step one

   <details>
   <summary>Step one details</summary>

   Hidden step content.

   </details>

2. Step two

Single-line spoiler: <details><summary>Tight</summary>Tight body with <b>html</b>.</details>

The end.
