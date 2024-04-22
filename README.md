# BBCode Renderer for [Mistune v3.0.2](https://github.com/lepture/mistune/releases/tag/v3.0.2)

Converts Markdown to a Xenforo flavor BBCode with a few tags custom to RedGuides. You can supply the beginning of a URL (domain) to help parse relative URLs. 

### Usage
Placed in a `/renderers` subfolder of your project,

```python 
import mistune
from renderers.bbcode import BBCodeRenderer

mistune.create_markdown(renderer=BBCodeRenderer(domain='https://github.com/RedGuides/MistuneBBCode/'))
```
