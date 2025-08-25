"""Lightweight LLM utilities for provider-agnostic code refactoring via LiteLLM.

Relies on environment variables for provider API keys, e.g.:
- OPENAI_API_KEY
- ANTHROPIC_API_KEY
- GEMINI_API_KEY or GOOGLE_API_KEY
- MISTRAL_API_KEY
- COHERE_API_KEY
- FIREWORKS_API_KEY
- GROQ_API_KEY

Usage: see the `llm_battle` command integrated in `main.py`.
"""

from __future__ import annotations

from typing import Optional
import re
import os

try:
    # LiteLLM provides a unified interface across providers
    from litellm import completion
except Exception as exc:  # pragma: no cover - optional runtime dependency
    completion = None  # type: ignore


# Matches fenced code blocks and captures their inner contents (non-greedy)
_CODE_BLOCK_RE = re.compile(r"[a-zA-Z0-9+\-_.]*\n([\s\S]*?)", re.MULTILINE)


def extract_code_from_text(text: str) -> str:
    """Extract the first fenced code block from an LLM response.

    If a fenced code block (lang\n...) is found, return its inner contents
    trimmed of leading/trailing whitespace. Otherwise, return the original text
    trimmed of whitespace.

    Args:
        text: The text to search for a fenced code block.

    Returns:
        The extracted code string or the trimmed original text if no code block is found.
    """
    if not text:
        return ""
    # Use compiled regex to find the first fenced code block and return its capture group.
    match = _CODE_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def perfect_code_with_model(
    *,
    model: str,
    code: str,
    file_name: str,
    temperature: float = 0.0,
    extra_instructions: Optional[str] = None,
) -> str:
    """Ask the specified model to "perfect" a single source file and return the new code.

    This function routes requests through OpenRouter when OPENROUTER_API_KEY is present
    to ensure the LiteLLM model string is properly prefixed and extra headers are set.

    Args:
        model: LiteLLM model string, e.g. "openai/gpt-4o-mini", "anthropic/claude-3-5-sonnet-20240620",
               "gemini/gemini-1.5-pro", "groq/llama3-70b-8192", etc.
        code: Original source code to be perfected.
        file_name: Name of the file being perfected (context only).
        temperature: Creativity control for the LLM.
        extra_instructions: Optional additional guidance appended to the prompt.

    Returns:
        The perfected source code returned by the model, or the original code on failure.
    """
    if completion is None:
        raise RuntimeError(
            "litellm is not installed. Please run: pip install litellm"
        )

    # System prompt instructing the model on the goals and checks to perform.
    system_msg = (
        "You are a senior software engineer tasked with refactoring code without breaking tests. "
        """please perfect based off of the following **1. READABILITY AND CLARITY TASKS:**
- Benchmark: Code should be self-explanatory, with clear naming conventions and logical structure.
- Look for: unclear variable names, missing comments on complex logic, poor formatting
- Create tasks for: Variable/function names that don't describe intent (e.g., calculateTotalPrice vs. calc), inconsistent formatting, high cognitive load
- Metric threshold: Cognitive complexity >15 per function
- Example task: "Improve readability in payment_processor.py: rename variables 'x', 'calc' to 'transaction', 'calculateTotal' and add comments explaining complex business logic"

**2. MAINTAINABILITY TASKS:**
- Benchmark: Code is easy to modify without introducing bugs
- Look for: DRY violations, SOLID principle violations, low cohesion/high coupling
- Create tasks for: Maintainability Index <70, functions >50 lines, repeated code patterns
- Example task: "Improve maintainability in order_service.py: extract repeated validation logic into validate_order_data() helper method, break 200-line process_order() into smaller single-purpose functions"

**3. PERFORMANCE TASKS:**
- Benchmark: Code executes efficiently for its use case
- Look for: O(n²) algorithms, unnecessary computations, redundant database queries, inefficient data structures
- Create tasks for: Identified bottlenecks, nested loops that could use hash maps, synchronous operations that could be async
- Example task: "Optimize performance in user_lookup.py: replace nested loop user search (O(n²)) with hash map lookup (O(1)), cache frequent database queries"

**4. TESTABILITY AND TEST COVERAGE TASKS:**
- Benchmark: Code is designed to be easily testable with high coverage
- Look for: High coupling, no dependency injection, side effects in pure functions, missing edge case handling
- Create tasks for: Functions with side effects, hard dependencies, missing error condition handling
- Example task: "Improve testability in email_service.py: add dependency injection for SMTP client, extract side effects from send_email() method, add input validation for edge cases"

**5. ROBUSTNESS AND ERROR HANDLING TASKS:**
- Benchmark: Code handles errors gracefully and fails safely
- Look for: Missing try-catch blocks, generic exception handling, no input validation, missing logging
- Create tasks for: Functions without error handling, invalid input scenarios, missing retries for external dependencies
- Example task: "Add robust error handling to api_client.py: replace generic 'except Exception' with specific exception types, add input validation for API parameters, implement retry logic with exponential backoff"

**6. SECURITY TASKS:**
- Benchmark: Code minimizes vulnerabilities
- Look for: SQL injection, XSS vulnerabilities, hard-coded secrets, missing input sanitization
- Create tasks for: ALL identified security vulnerabilities from security_analysis
- Example task: "Fix security vulnerabilities in auth_service.py: replace string concatenation in SQL queries with parameterized queries, move API keys from code to environment variables, add input sanitization for user data"

**7. SCALABILITY TASKS:**
- Benchmark: Code supports growth in data volume or users
- Look for: Synchronous I/O bottlenecks, stateful components, inefficient database queries, missing caching
- Create tasks for: Blocking operations, in-memory data structures that don't scale, unindexed database queries
- Metric threshold: Make as much async tasks as possible, without changing the functionality of the code.
- Example task: "Improve scalability in report_generator.py: add Redis caching for expensive calculations, replace synchronous file I/O with async operations, optimize database queries with proper indexing"

**8. DOCUMENTATION TASKS:**
- Benchmark: Code is well-documented but not over-documented
- Look for: Missing docstrings on public methods, complex logic without comments, missing API documentation
- Create tasks for: Public methods without docstrings, complex algorithms without explanation, missing type hints
- Example task: "Add documentation to data_processor.py: add docstrings to all public methods, add type hints to function signatures, comment complex regex patterns with their purpose"

**9. CONSISTENCY WITH STANDARDS TASKS:**
- Benchmark: Code adheres to language-specific and team-defined standards
- Look for: Style guide violations, inconsistent error handling patterns, mixed frameworks
- Create tasks for: PEP 8 violations (Python), inconsistent naming conventions, mixed coding patterns
- Example task: "Improve consistency in utils module: convert camelCase to snake_case (PEP 8), standardize error handling patterns across all functions, consistent import ordering"

**10. ARCHITECTURE TASKS (TypeScript/JavaScript):**
- Benchmark: Codebase follows scalable, modular, and maintainable front-end architecture principles
- Look for: oversized React/TSX components (>300 LOC), tight coupling between UI layers, scattered utilities, excessive prop-drilling, inconsistent folder structure, missing separation of concerns
- Create tasks for: Splitting large components, extracting reusable hooks or utilities, reorganizing files into feature-based folders, adopting atomic design layers, extracting UI sub-components, enforcing clear import boundaries
- Example task: "Improve architecture in src/components/Sidebar.tsx: split 700-line component into SidebarMain.tsx, SidebarItem.tsx, SidebarUtils.ts; move to components/sidebar/ folder; introduce React Context for shared state; add barrel export index.ts"
"""
    )

    # Build the user message efficiently using join to avoid repeated concatenation
    initial_user_message = f"Perfect this code file: {file_name}.\n\nOriginal code:\n{code}"
    if extra_instructions:
        # extra_instructions should be placed before the main prompt; strip incidental whitespace
        user_msg = "\n\n".join([extra_instructions.strip(), initial_user_message])
    else:
        user_msg = initial_user_message

    # Route via OpenRouter if OPENROUTER_API_KEY is present
    api_kwargs = {}
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if openrouter_key:
        # Ensure model is prefixed for LiteLLM's provider router
        if not model.startswith("openrouter/"):
            model = f"openrouter/{model}"
        # Provide recommended headers and base URL for OpenRouter routing
        api_kwargs = {
            "api_key": openrouter_key,
            "api_base": os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1"),
            "extra_headers": {
                # Optional but recommended by OpenRouter
                "HTTP-Referer": os.environ.get("OPENROUTER_SITE_URL", "https://openrouter.ai"),
                "X-Title": os.environ.get("OPENROUTER_APP_NAME", "Polarity Benchmarks"),
            },
        }

    # Call the unified completion interface
    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=temperature,
        **api_kwargs,
    )

    try:
        # Typical shape: response["choices"][0]["message"]["content"]
        content = response["choices"][0]["message"]["content"]  # type: ignore[index]
    except Exception:
        # Best-effort fallback to a few likely alternative shapes; keep robust access without raising
        # Use getattr to support objects with attribute-style access as well.
        content = getattr(response, "choices", [{}])[0].get("message", {}).get("content", "")  # type: ignore[attr-defined]

    new_code = extract_code_from_text(content)
    return new_code or code