import ast

SUPPORTED_LANGUAGES = {"python"}
import re
from .utils import get_python_files, parse_file

SNAKE_CASE_REGEX = re.compile(r"^[a-z_][a-z0-9_]*$")
CAMEL_CASE_REGEX = re.compile(r"^[A-Z][a-zA-Z0-9]*$")

class ConsistencyVisitor(ast.NodeVisitor):
    def __init__(self, file_path, details_list):
        self.file_path = file_path
        self.details = details_list
        self.inconsistent_for_file = 0
        self.total_for_file = 0

    def visit_ClassDef(self, node):
        self.total_for_file += 1
        if not CAMEL_CASE_REGEX.match(node.name):
            self.inconsistent_for_file += 1
            self.details.append(''.join(["Inconsistent class name: '", node.name, "' should be CamelCase. (", self.file_path, ":", str(node.lineno), ")"]))
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.total_for_file += 1
        if not node.name.startswith("__") and not SNAKE_CASE_REGEX.match(node.name):
            self.inconsistent_for_file += 1
            self.details.append(''.join(["Inconsistent function name: '", node.name, "' should be snake_case. (", self.file_path, ":", str(node.lineno), ")"]))
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.total_for_file += 1
            if not SNAKE_CASE_REGEX.match(node.id):
                self.inconsistent_for_file += 1
                self.details.append(''.join(["Inconsistent variable name: '", node.id, "' should be snake_case. (", self.file_path, ":", str(node.lineno), ")"]))
        self.generic_visit(node)

def assess_consistency(codebase_path: str):
    """
    Assesses the consistency of naming conventions in a codebase.
    - Class names should be CamelCase.
    - Function and variable names should be snake_case.
    """
    python_files = get_python_files(codebase_path)
    if not python_files:
        return 0.0, ["No Python files found."]

    total_names = 0
    inconsistent_names = 0
    details = []

    for file_path in python_files:
        tree = parse_file(file_path)
        if tree:
            visitor = ConsistencyVisitor(file_path, details)
            visitor.visit(tree)
            total_names += visitor.total_for_file
            inconsistent_names += visitor.inconsistent_for_file

    if total_names == 0:
        return 10.0, ["No relevant names found to check."]

    consistency_ratio = (total_names - inconsistent_names) / total_names
    consistency_score = consistency_ratio * 10.0
    details.insert(0, f"Naming consistency: {consistency_ratio*100:.2f}% ({total_names - inconsistent_names}/{total_names} consistent)")

    return min(10.0, max(0.0, consistency_score)), details