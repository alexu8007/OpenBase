import ast
import os
import logging
from pathlib import Path
from typing import Optional

SUPPORTED_LANGUAGES = {"any"}

from .utils import get_python_files, parse_file

logger = logging.getLogger(__name__)

def _contains_any(haystack: str, needles) -> bool:
    """Return True if any of the needle substrings are found in haystack."""
    return any(kw in haystack for kw in needles)

def assess_scalability(codebase_path: str):
    """
    Comprehensive scalability assessment looking at multiple scalability patterns and practices.
    """
    if not codebase_path:
        logger.warning("assess_scalability called with empty codebase_path")
        return 2.0, ["No codebase_path provided - baseline score for potential scalability."]

    # Coerce PathLike inputs to string for downstream functions
    try:
        codebase_path = str(codebase_path)
    except Exception as e:
        logger.exception("Failed to coerce codebase_path to string")
        return 2.0, ["Invalid codebase_path provided - baseline score for potential scalability."]

    python_files = get_python_files(codebase_path)
    if not python_files:
        return 2.0, ["No Python files found - baseline score for potential scalability."]

    # Scalability indicators
    uses_asyncio = False
    uses_multiprocessing = False
    uses_threading = False
    uses_caching_libs = False
    uses_web_frameworks = False
    uses_database_libs = False
    uses_queue_systems = False
    uses_connection_pooling = False

    async_functions = 0
    total_functions = 0
    class_count = 0
    modular_structure = False
    config_management = False
    details = []

    # Extended keyword sets for better detection
    caching_keywords = frozenset(["redis", "memcached", "celery", "cache", "cachetools", "functools.lru_cache", "lru_cache"])
    web_framework_keywords = frozenset(["flask", "django", "fastapi", "tornado", "bottle", "cherrypy", "pyramid", "starlette"])
    database_keywords = frozenset(["sqlalchemy", "django.db", "psycopg2", "pymongo", "sqlite3", "mysql", "postgresql", "asyncpg", "aiomysql"])
    queue_keywords = frozenset(["celery", "rq", "kombu", "pika", "rabbitmq", "kafka", "sqs"])
    threading_keywords = frozenset(["threading", "concurrent.futures", "thread", "threadpool"])
    pooling_keywords = frozenset(["pool", "connectionpool", "dbutils", "pooleddb"])
    config_keywords = frozenset(["configparser", "environ", "settings", "config", "dotenv"])
    modular_patterns = frozenset(["__init__.py", "from . import", "from ..", "package"])

    for file_path in python_files:
        tree = parse_file(file_path)
        if not tree:
            continue

        file_content = ""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read().lower()
        except (OSError, UnicodeDecodeError) as e:
            logger.debug("Failed to read file %s: %s", file_path, e)
            file_content = ""

        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name_lower = alias.name.lower()
                    if "asyncio" in name_lower: uses_asyncio = True
                    if "multiprocessing" in name_lower: uses_multiprocessing = True
                    if _contains_any(name_lower, threading_keywords): uses_threading = True
                    if _contains_any(name_lower, caching_keywords): uses_caching_libs = True
                    if _contains_any(name_lower, web_framework_keywords): uses_web_frameworks = True
                    if _contains_any(name_lower, database_keywords): uses_database_libs = True
                    if _contains_any(name_lower, queue_keywords): uses_queue_systems = True
                    if _contains_any(name_lower, pooling_keywords): uses_connection_pooling = True
                    if _contains_any(name_lower, config_keywords): config_management = True

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_lower = node.module.lower()
                    if "asyncio" in module_lower: uses_asyncio = True
                    if "multiprocessing" in module_lower: uses_multiprocessing = True
                    if _contains_any(module_lower, threading_keywords): uses_threading = True
                    if _contains_any(module_lower, caching_keywords): uses_caching_libs = True
                    if _contains_any(module_lower, web_framework_keywords): uses_web_frameworks = True
                    if _contains_any(module_lower, database_keywords): uses_database_libs = True
                    if _contains_any(module_lower, queue_keywords): uses_queue_systems = True
                    if _contains_any(module_lower, pooling_keywords): uses_connection_pooling = True
                    if _contains_any(module_lower, config_keywords): config_management = True

            # Count functions and classes
            elif isinstance(node, ast.FunctionDef):
                total_functions += 1
            elif isinstance(node, ast.AsyncFunctionDef):
                total_functions += 1
                async_functions += 1
            elif isinstance(node, ast.ClassDef):
                class_count += 1

        # Check for modular structure indicators in file content
        if any(pattern in file_content for pattern in modular_patterns):
            modular_structure = True

    # Calculate comprehensive scalability score (2-10 scale, baseline 2.0)
    score = 2.0  # Baseline score - even basic code has some scalability potential

    # High-impact scalability features
    if uses_asyncio:
        score += 2.5
        details.append("✓ Uses asyncio for asynchronous I/O operations")
    if uses_multiprocessing:
        score += 2.5
        details.append("✓ Uses multiprocessing for CPU-bound parallelism")
    if uses_web_frameworks:
        score += 1.5
        details.append("✓ Uses web framework (inherent request handling scalability)")
    if uses_database_libs:
        score += 1.0
        details.append("✓ Uses database libraries (data persistence scalability)")

    # Medium-impact features
    if uses_threading:
        score += 1.0
        details.append("✓ Uses threading for concurrent operations")
    if uses_caching_libs:
        score += 1.5
        details.append("✓ Implements caching mechanisms")
    if uses_queue_systems:
        score += 1.5
        details.append("✓ Uses queue/messaging systems for async processing")
    if uses_connection_pooling:
        score += 1.0
        details.append("✓ Uses connection pooling for resource management")

    # Architecture and design indicators
    if class_count > 0:
        class_ratio = min(1.0, class_count / max(1, len(python_files)))
        score += class_ratio * 0.5
        details.append(f"✓ Object-oriented design with {class_count} classes")

    if modular_structure:
        score += 0.5
        details.append("✓ Modular package structure detected")

    if config_management:
        score += 0.5
        details.append("✓ Configuration management for environment flexibility")

    # Async function ratio bonus
    if total_functions > 0:
        async_ratio = async_functions / total_functions
        if async_ratio > 0:
            score += min(1.0, async_ratio * 2.0)
            details.append(f"✓ {async_ratio*100:.1f}% of functions are async")

    # File organization bonus
    if len(python_files) > 1:
        score += min(0.5, len(python_files) * 0.1)
        details.append(f"✓ Multi-file organization ({len(python_files)} Python files)")

    # Add baseline explanation if score is still low
    if score < 4.0:
        details.append("ℹ Basic codebase with limited scalability patterns detected")
        details.append("• Consider adding async/await for I/O operations")
        details.append("• Consider connection pooling for database operations")
        details.append("• Consider caching frequently accessed data")

    # ------------------------------------------------------------------ #
    # Static architectural scalability assessment
    # ------------------------------------------------------------------ #
    architectural_score = _assess_static_architecture(python_files, codebase_path)
    if architectural_score > 0:
        details.append(f"🏗️ Architectural analysis: {architectural_score:.1f}/10")

        # Weight: 70% architectural analysis, 30% pattern analysis
        final_score = (architectural_score * 0.7) + (min(10.0, score) * 0.3)
        details.append(f"📊 Combined score: {final_score:.1f}/10 (70% architectural + 30% pattern analysis)")
    else:
        final_score = min(10.0, max(2.0, score))

    return final_score, details


def _assess_static_architecture(python_files, codebase_path: str) -> float:
    """Deterministic architectural scalability assessment based on code structure."""
    arch_score = 0.0

    # 1. Analyze file organization and separation of concerns
    file_structure_score = _analyze_file_structure(python_files, codebase_path)
    arch_score += file_structure_score

    # 2. Analyze import dependencies and coupling
    dependency_score = _analyze_dependencies(python_files, codebase_path)
    arch_score += dependency_score

    # 3. Analyze design patterns and architectural decisions
    pattern_score = _analyze_design_patterns(python_files)
    arch_score += pattern_score

    # 4. Analyze data flow and processing architecture
    data_flow_score = _analyze_data_flow(python_files)
    arch_score += data_flow_score

    return min(10.0, arch_score)


def _analyze_file_structure(python_files, codebase_path: str) -> float:
    """Analyze file organization for scalability indicators."""
    score = 0.0

    # Get relative paths for analysis
    rel_paths = [os.path.relpath(f, codebase_path) for f in python_files]

    # Check for clear separation of concerns
    lowered = [p.lower() for p in rel_paths]
    has_models = any('model' in path for path in lowered)
    has_views = any('view' in path or 'template' in path for path in lowered)
    has_controllers = any('controller' in path or 'handler' in path for path in lowered)
    has_services = any('service' in path or 'business' in path for path in lowered)
    has_utils = any('util' in path or 'helper' in path for path in lowered)
    has_config = any('config' in path or 'setting' in path for path in lowered)
    has_tests = any('test' in path for path in lowered)

    # Layered architecture bonus
    if has_models and (has_views or has_controllers): score += 1.0
    if has_services: score += 0.5
    if has_utils: score += 0.3
    if has_config: score += 0.4
    if has_tests: score += 0.3

    # Directory depth analysis (deeper = more organized)
    avg_depth = sum(len(Path(p).parts) for p in rel_paths) / len(rel_paths) if rel_paths else 1
    if avg_depth > 2: score += 0.5
    if avg_depth > 3: score += 0.3

    # File count considerations
    file_count = len(python_files)
    if 5 <= file_count <= 20: score += 0.5  # Sweet spot
    elif file_count > 20: score += 0.3      # Large but manageable

    return min(2.5, score)


def _analyze_dependencies(python_files, codebase_path: str) -> float:
    """Analyze import dependencies and coupling."""
    score = 0.0
    total_imports = 0
    external_imports = 0
    internal_imports = 0

    import_graph = {}
    internal_prefixes = ('app', 'src', 'lib')

    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            tree = ast.parse(content)
            file_imports = set()

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.name
                        file_imports.add(name)
                        total_imports += 1
                        if name.startswith('.') or any(name.startswith(p) for p in internal_prefixes):
                            internal_imports += 1
                        else:
                            external_imports += 1

                elif isinstance(node, ast.ImportFrom) and node.module:
                    name = node.module
                    file_imports.add(name)
                    total_imports += 1
                    if name.startswith('.') or any(name.startswith(p) for p in internal_prefixes):
                        internal_imports += 1
                    else:
                        external_imports += 1

            rel_path = os.path.relpath(file_path, codebase_path)
            import_graph[rel_path] = list(file_imports)

        except (OSError, UnicodeDecodeError, SyntaxError) as e:
            logger.debug("Skipping file %s during dependency analysis due to error: %s", file_path, e)
            continue

    # Low coupling bonus (more external than internal dependencies)
    if total_imports > 0:
        external_ratio = external_imports / total_imports
        if external_ratio > 0.6: score += 1.0
        elif external_ratio > 0.4: score += 0.5

    # Reasonable import count
    avg_imports = total_imports / len(python_files) if python_files else 0
    if 3 <= avg_imports <= 15: score += 0.5

    # Bonus for using standard libraries (good design)
    stdlibs = ('os', 'sys', 'json', 'time', 'datetime', 'collections', 'itertools')
    stdlib_imports = sum(1 for imports in import_graph.values()
                        for imp in imports
                        if any(imp.startswith(lib) for lib in stdlibs))
    if stdlib_imports > 0: score += 0.3

    return min(2.0, score)


def _analyze_design_patterns(python_files) -> float:
    """Analyze code for scalable design patterns."""
    score = 0.0

    total_classes = 0
    abstract_classes = 0
    interfaces = 0
    singletons = 0
    factories = 0
    decorators = 0
    context_managers = 0

    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    total_classes += 1

                    # Check for abstract base classes
                    if any(base.id == 'ABC' if isinstance(base, ast.Name) else False
                          for base in node.bases):
                        abstract_classes += 1

                    # Check for interface-like classes (mostly abstract methods)
                    abstract_methods = sum(1 for n in node.body
                                         if isinstance(n, ast.FunctionDef) and
                                         any(isinstance(d, ast.Name) and d.id == 'abstractmethod'
                                             for d in getattr(n, 'decorator_list', [])))
                    if abstract_methods > 0:
                        interfaces += 1

                    # Check for singleton pattern
                    if 'singleton' in node.name.lower() or any('__new__' in n.name for n in node.body if isinstance(n, ast.FunctionDef)):
                        singletons += 1

                    # Check for factory pattern
                    if 'factory' in node.name.lower() or any('create' in n.name.lower() for n in node.body if isinstance(n, ast.FunctionDef)):
                        factories += 1

                elif isinstance(node, ast.FunctionDef):
                    # Check for decorators
                    if node.decorator_list:
                        decorators += 1

                    # Check for context managers
                    if '__enter__' in node.name or '__exit__' in node.name:
                        context_managers += 1
        except (OSError, UnicodeDecodeError, SyntaxError) as e:
            logger.debug("Skipping file %s during design pattern analysis due to error: %s", file_path, e)
            continue

    # Design pattern bonuses
    if abstract_classes > 0: score += 0.5
    if interfaces > 0: score += 0.4
    if factories > 0: score += 0.3
    if decorators > 0: score += 0.3
    if context_managers > 0: score += 0.2

    # Class organization bonus
    if total_classes > 0:
        class_ratio = total_classes / len(python_files) if python_files else 0
        if 1 <= class_ratio <= 3: score += 0.5  # Good class distribution

    return min(2.0, score)


def _analyze_data_flow(python_files) -> float:
    """Analyze data processing and flow patterns."""
    score = 0.0

    has_generators = False
    has_iterators = False
    has_streaming = False
    has_batch_processing = False
    has_pipeline_pattern = False
    async_data_processing = False

    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()

            # Check for efficient data processing patterns
            if 'yield' in content: has_generators = True
            if '__iter__' in content or '__next__' in content: has_iterators = True
            if 'stream' in content or 'chunk' in content: has_streaming = True
            if 'batch' in content or 'bulk' in content: has_batch_processing = True
            if 'pipeline' in content or 'process' in content: has_pipeline_pattern = True
            if 'async def' in content and ('process' in content or 'handle' in content): async_data_processing = True

        except (OSError, UnicodeDecodeError) as e:
            logger.debug("Skipping file %s during data flow analysis due to error: %s", file_path, e)
            continue

    # Data flow efficiency bonuses
    if has_generators: score += 0.5
    if has_iterators: score += 0.3
    if has_streaming: score += 0.4
    if has_batch_processing: score += 0.4
    if has_pipeline_pattern: score += 0.3
    if async_data_processing: score += 0.6

    return min(1.5, score)