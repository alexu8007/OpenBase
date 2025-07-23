import os
import ast

def get_python_files(path):
    python_files = []
    for root, _, files in os.walk(path):
        python_files.extend([os.path.join(root, f) for f in files if f.endswith(".py")])
    return python_files

def parse_file(file_path):
    with open(file_path, "r", encoding="utf-8") as source:
        try:
            return ast.parse(source.read(), filename=file_path)
        except (SyntaxError, UnicodeDecodeError):
            return None