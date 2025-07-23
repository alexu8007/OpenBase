import os
import ast

def get_python_files(path):
    python_files = [os.path.join(root, file) for root, dirs, files in os.walk(path) for file in files if file.endswith(".py")]
    return python_files

def parse_file(file_path):
    with open(file_path, "r", encoding="utf-8") as source:
        try:
            return ast.parse(source.read(), filename=file_path)
        except (SyntaxError, UnicodeDecodeError):
            return None