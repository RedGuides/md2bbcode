# testcall.py

from md2bbcode import process_readme

def test_conversion():
    # Specify the path to the README.md you want to test
    input_path = 'eqlog.md'
    domain = 'https://raw.githubusercontent.com/kauffman12/EQLogParser/master/'
    debug_mode = False  # Set to True to generate debug files

    # Call the function from md2bbcode.py
    result = process_readme(input_path, domain, debug=debug_mode)

    # Print the result to check it
    print(result)

if __name__ == "__main__":
    test_conversion()
