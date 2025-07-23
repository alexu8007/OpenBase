import ast

SUPPORTED_LANGUAGES = {"python"}
from .utils import get_python_files, parse_file

class RobustnessVisitor(ast.NodeVisitor):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.uses_logging = False
        self.total_handlers = 0
        self.good_handlers = 0
        self.details = []
    
    def visit_Import(self, node):
        if any(alias.name == "logging" for alias in node.names):
            self.uses_logging = True
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        if node.module == "logging":
            self.uses_logging = True
        self.generic_visit(node)
    
    def visit_ExceptHandler(self, node):
        self.total_handlers += 1
        if node.type:
            if isinstance(node.type, ast.Name) and node.type.id == 'Exception':
                self.details.append(f"Generic 'except Exception' used in {self.file_path}:{node.lineno}")
            else:
                self.good_handlers += 1
        else:
            self.details.append(f"Bare 'except:' used in {self.file_path}:{node.lineno}")
        self.generic_visit(node)

def assess_robustness(codebase_path: str):
    """
    Assesses the robustness of a codebase.
    - Checks for specific exception handling vs. generic `except:`.
    - Checks for the use of logging.
    """
    python_files = get_python_files(codebase_path)
    if not python_files:
        return 0.0, ["No Python files found."]

    total_handlers = 0
    good_handlers = 0
    uses_logging = False
    details = []

    for file_path in python_files:
        tree = parse_file(file_path)
        if not tree:
            continue
        
        visitor = RobustnessVisitor(file_path)
        visitor.visit(tree)
        
        total_handlers += visitor.total_handlers
        good_handlers += visitor.good_handlers
        uses_logging = uses_logging or visitor.uses_logging
        details.extend(visitor.details)

    if uses_logging:
        details.insert(0, "Codebase appears to use the 'logging' module.")
    else:
        details.insert(0, "Codebase does not appear to use the 'logging' module.")

    if total_handlers == 0:
        return 5.0 if uses_logging else 2.0, details

    handler_quality = (good_handlers / total_handlers)
    handler_score = handler_quality * 8.0 # Max 8 points from handlers
    
    if uses_logging:
        handler_score += 2.0 # Bonus points for logging
    
    details.insert(1, f"Error handling quality: {handler_quality*100:.2f}% ({good_handlers}/{total_handlers} specific handlers)")

    return min(10.0, max(0.0, handler_score)), details