import ast
import os
import logging

SUPPORTED_LANGUAGES = {"any"}
import asyncio
from typing import Optional

# Attempt to import Google Generative AI SDK for Gemini. If it's not
# available (e.g., in CI without extra deps) we fall back to heuristics.
try:
    import google.generativeai as genai  # type: ignore
except ImportError:  # pragma: no cover
    genai = None

from .utils import get_python_files, parse_file

def assess_scalability(codebase_path: str):
    """
    Assesses scalability by checking for use of asyncio, multiprocessing, and caching.
    This is a simplified static analysis.
    """
    python_files = get_python_files(codebase_path)
    if not python_files:
        return 0.0, ["No Python files found."]

    uses_asyncio = False
    uses_multiprocessing = False
    uses_caching_libs = False
    async_functions = 0
    total_functions = 0
    details = []
    
    caching_keywords = ["redis", "memcached", "celery", "cache", "cachetools", "cachetools.cached"]

    # Iterate through each Python file to analyze AST
    for file_path in python_files:
        tree = parse_file(file_path)
        if not tree:
            continue

        # Process each node in the AST of the file
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "asyncio" in alias.name: uses_asyncio = True
                    if "async" in alias.name: uses_asyncio = True
                    if "multiprocessing" in alias.name: uses_multiprocessing = True
                    if any(keyword in alias.name for keyword in caching_keywords): uses_caching_libs = True
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    if "asyncio" in node.module: uses_asyncio = True
                    if "async" in node.module: uses_asyncio = True
                    if "multiprocessing" in node.module: uses_multiprocessing = True
                    if any(keyword in node.module for keyword in caching_keywords): uses_caching_libs = True

            if isinstance(node, ast.FunctionDef):
                total_functions += 1
            elif isinstance(node, ast.AsyncFunctionDef):
                total_functions += 1
                async_functions += 1

    # ------------------------------------------------------------------ #
    # Heuristic score based on static analysis (0-10 scale)
    # ------------------------------------------------------------------ #
    score = 0.0
    if uses_asyncio:
        score += 3.0
        details.append("Uses 'asyncio' for I/O-bound concurrency.")
    if uses_multiprocessing:
        score += 3.0
        details.append("Uses 'multiprocessing' for CPU-bound parallelism.")
    if uses_caching_libs:
        score += 2.0
        details.append("Appears to use a caching or task-queue library (e.g., Redis, Celery).")
    
    if total_functions > 0:
        async_ratio = async_functions / total_functions
        if async_ratio > 0:
            details.append(f"{async_ratio*100:.1f}% of functions are async.")
        score += async_ratio * 2.0

    # ------------------------------------------------------------------ #
    # Optional Gemini LLM evaluation for a holistic scalability score
    # ------------------------------------------------------------------ #
    llm_score_0_to_10: Optional[float] = None
    api_key = os.getenv("GEMINI_API_KEY")
    if genai and api_key:
        try:
            genai.configure(api_key=api_key)

            summary = (
                f"Python files: {len(python_files)}, total functions: {total_functions}, "
                f"async functions: {async_functions}, uses_asyncio: {uses_asyncio}, "
                f"uses_multiprocessing: {uses_multiprocessing}, uses_caching_libs: {uses_caching_libs}."
            )

            prompt = (
                "You are an expert software architect.\n"
                "Evaluate the *scalability* of the following Python codebase on a scale "
                "from 0 (not scalable) to 100 (highly scalable). "
                "Only reply with the number.\n\n"
                f"Codebase summary:\n{summary}\n"
            )

            # Build a trimmed view of the codebase so Gemini has real context
            model = genai.GenerativeModel("gemini-2.5-flash")  # default config; we'll pass temperature=0 in call

            # Gather code snippets until we hit a reasonable size limit
            snippet_chars = 0
            snippets = []
            MAX_CHARS = 15000  # keep prompt within token budget
            for file_path in python_files:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception as e:
                    logging.error(f"Error reading file {file_path}: {e}")
                    continue  # Skip this file after logging

                # Truncate very large files to avoid blowing the context window
                if len(content) > 2000:
                    content = content[:2000]

                if snippet_chars + len(content) > MAX_CHARS:
                    break

                snippets.append(f"FILE: {file_path}\n\n{content}\n\n")
                snippet_chars += len(content)

            code_corpus = "\n".join(snippets)
            full_prompt = ''.join([prompt, "\nHere are code excerpts:\n", code_corpus])

            rsp = model.generate_content(full_prompt, generation_config={"temperature": 0.0})
            first_token = rsp.text.strip().split()[0]
            numeric = "".join(ch for ch in first_token if (ch.isdigit() or ch == '.'))
            llm_value = float(numeric)
            llm_value = max(0.0, min(100.0, llm_value))
            llm_score_0_to_10 = llm_value / 10.0
            details.append(f"Gemini LLM scalability score: {llm_value:.1f}/100")
        except Exception as e:
            details.append(f"Gemini LLM evaluation failed: {e}")
    else:
        if not genai:
            details.append("google-generativeai not installed; skipping Gemini evaluation.")
        elif not api_key:
            details.append("GEMINI_API_KEY environment variable not set; skipping Gemini evaluation.")

    final_score = llm_score_0_to_10 if llm_score_0_to_10 is not None else min(10.0, max(0.0, score))
    return final_score, details