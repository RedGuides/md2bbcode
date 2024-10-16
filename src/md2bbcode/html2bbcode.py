# converts some HTML tags to BBCode
# pass --debug to save the output to readme.finalpass
# may be better off replacing this with html to markdown (and then to bbcode). Lepture recommeds a JS html to markdown converter: sundown
from bs4 import BeautifulSoup
import argparse

def handle_font_tag(tag, replacements):
    """Handles the conversion of <font> tag with attributes like color and size."""
    attributes = []
    if 'color' in tag.attrs:
        attributes.append(f"COLOR={tag['color']}")
    if 'size' in tag.attrs:
        attributes.append(f"SIZE={tag['size']}")
    if 'face' in tag.attrs:
        attributes.append(f"FONT={tag['face']}")

    inner_content = ''.join(recursive_html_to_bbcode(child, replacements) for child in tag.children)
    if attributes:
        # Nest all attributes. Example: [COLOR=red][SIZE=5]content[/SIZE][/COLOR]
        for attr in reversed(attributes):
            inner_content = f"[{attr}]{inner_content}[/{attr.split('=')[0]}]"
    return inner_content

def handle_style_tag(tag, replacements):
    """Handles the conversion of tags with style attributes like color, size, and font."""
    attributes = []
    style = tag.attrs.get('style', '')

    # Extracting CSS properties
    css_properties = {item.split(':')[0].strip(): item.split(':')[1].strip() for item in style.split(';') if ':' in item}

    # Mapping CSS properties to BBCode
    if 'color' in css_properties:
        attributes.append(f"COLOR={css_properties['color']}")
    if 'font-size' in css_properties:
        attributes.append(f"SIZE={css_properties['font-size']}")
    if 'font-family' in css_properties:
        attributes.append(f"FONT={css_properties['font-family']}")
    if 'text-decoration' in css_properties and 'line-through' in css_properties['text-decoration']:
        attributes.append("S")  # Assume strike-through
    if 'text-decoration' in css_properties and 'underline' in css_properties['text-decoration']:
        attributes.append("U")
    if 'font-weight' in css_properties:
        if css_properties['font-weight'].lower() == 'bold' or (css_properties['font-weight'].isdigit() and int(css_properties['font-weight']) >= 700):
            attributes.append("B")  # Assume bold

    inner_content = ''.join(recursive_html_to_bbcode(child, replacements) for child in tag.children)
    if attributes:
        # Nest all attributes
        for attr in reversed(attributes):
            if '=' in attr:  # For attributes with values
                inner_content = f"[{attr}]{inner_content}[/{attr.split('=')[0]}]"
            else:  # For simple BBCode tags like [B], [I], [U], [S]
                inner_content = f"[{attr}]{inner_content}[/{attr}]"
    return inner_content

def recursive_html_to_bbcode(tag, replacements):
    """Recursively convert HTML content of a given tag to BBCode."""
    if tag.name is None:
        return str(tag)
    elif tag.name == 'br':
        # Directly return a newline for <br> or </br> tags
        return '\n'
    elif tag.name in replacements:
        bb_tag = replacements[tag.name]
        inner_content = ''
        for child in tag.children:
            inner_content += recursive_html_to_bbcode(child, replacements)
        
        if tag.name in ['a', 'img']:
            if tag.name == 'a':
                href = tag.get('href', '')
                return f"[URL={href}]{inner_content}[/URL]"
            elif tag.name == 'img':
                src = tag.get('src', '')
                alt = tag.get('alt', '')
                if alt:
                    return f"[IMG alt=\"{alt}\"]{src}[/IMG]"
                else:
                    return f"[IMG]{src}[/IMG]"
        elif tag.name in ['ul', 'ol']:
            return f"[{bb_tag}]{inner_content}[/LIST]"
        elif tag.name == 'font':
            # Special handling for <font> tag with attributes
            return handle_font_tag(tag, replacements)  # Pass replacements here
        elif tag.name == 'li':
            return f"[*]{inner_content}"
        else:
            return f"[{bb_tag}]{inner_content}[/{bb_tag}]"
    elif tag.name in ['span', 'div']:
        return handle_style_tag(tag, replacements)
    else:
        # For tags not in the replacements, concatenate the content
        return ''.join(recursive_html_to_bbcode(child, replacements) for child in tag.children)

def html_to_bbcode(html):
    replacements = {
        'b': 'B',
        'strong': 'B',
        'i': 'I',
        'em': 'I',
        'u': 'U',
        's': 'S',
        'sub': 'SUB',
        'sup': 'SUP',
        'p': '',  # Handled by default
        'ul': 'LIST',
        'ol': 'LIST=1',
        'li': '*',  # Special handling in recursive function
        'font': '',  # To be handled for attributes
        'blockquote': 'QUOTE',
        'pre': 'CODE',
        'code': 'ICODE',
        'a': 'URL',  # Special handling for attributes
        'img': 'IMG'  # Special handling for attributes
    }

    soup = BeautifulSoup(html, 'html.parser')
    return recursive_html_to_bbcode(soup, replacements)

def process_html(input_html, debug=False, output_file=None):
    converted_bbcode = html_to_bbcode(input_html)

    if debug:
        with open(output_file, 'w', encoding='utf-8') as file:
            file.write(converted_bbcode)
    else:
        return converted_bbcode

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert HTML to BBCode with optional debugging output.")
    parser.add_argument('input_file', type=str, help='Input HTML file path')
    parser.add_argument('--debug', action='store_true', help='Save output to readme.finalpass for debugging')
    
    args = parser.parse_args()
    input_file = args.input_file
    output_file = 'readme.finalpass' if args.debug else None

    with open(input_file, 'r', encoding='utf-8') as file:
        html_content = file.read()

    # Call the processing function
    process_html(html_content, debug=args.debug, output_file=output_file)