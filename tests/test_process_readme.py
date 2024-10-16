import os
import sys

# Add the src directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from md2bbcode.main import process_readme

def test_conversion():
    # Read the README.md content from the local file
    readme_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'README.md'))
    with open(readme_path, 'r', encoding='utf-8') as file:
        markdown_content = file.read()

    domain = ''  # Set domain if needed
    debug_mode = False  # Set to True to generate debug files

    # Call the process_readme function with the Markdown content
    result = process_readme(markdown_content, domain, debug=debug_mode)

    # Perform assertions to validate the output
    assert result is not None
    assert isinstance(result, str)
    
    # Check for the presence of specific BBCode elements from the new README content
    expected_bbcodes = [
        "[img alt",
        "[icode]",
        "[HEADING=1]",
        "[b]",
        "[HEADING=2]",
        "[CODE=bash]"
    ]
    
    for bbcode in expected_bbcodes:
        assert bbcode in result, f"Expected BBCode not found: {bbcode}"