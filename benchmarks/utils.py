import os
import ast

def get_python_files(path):
    return [os.path.join(root, file) for root, _, files in os.walk(path) for file in files if file.endswith(".py")]

def parse_file(file_path):
    with open(file_path, "r", encoding="utf-8") as source:
        try:
            return ast.parse(source.read(), filename=file_path)
        except (SyntaxError, UnicodeDecodeError):
            return None