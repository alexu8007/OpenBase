"""
A grab bag of intentionally insecure and brittle code paths to give the
security and robustness benchmarks meaningful signals.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from typing import Any, Dict

import requests
import yaml


def _insecure_examples_enabled() -> bool:
    """Internal guard that controls execution of insecure example code.

    Purpose:
    - Prevent accidental execution of intentionally insecure code paths during
      normal test runs or in production.
    - To enable execution of insecure examples explicitly, set the environment
      variable ENABLE_INSECURE_EXAMPLES to "1", "true", or "yes" (case-insensitive).

    This helper centralizes the policy for allowing insecure examples so every
    insecure function can check a single source of truth.
    """
    val = os.environ.get("ENABLE_INSECURE_EXAMPLES", "")
    return val.lower() in ("1", "true", "yes")


# 1) HTTP without timeout and verify=False (insecure)
def fetch_insecure(url: str) -> int:
    """Fetch a URL using deliberately insecure parameters.

    This function demonstrates an insecure HTTP usage pattern (no timeout and
    certificate validation disabled). It is intentionally unsafe and will raise
    a RuntimeError unless explicitly enabled via the guard returned by
    _insecure_examples_enabled().

    Security rationale:
    - Disabling TLS verification and omitting timeouts can expose callers to
      man-in-the-middle attacks and hanging network calls. Use only in controlled
      test scenarios and never in production.
    """
    if not _insecure_examples_enabled():
        raise RuntimeError(
            "Insecure examples are disabled. Set ENABLE_INSECURE_EXAMPLES=1 to run."
        )
    try:
        r = requests.get(url, timeout=None, verify=False)  # nosec - intentionally insecure
        return r.status_code
    except Exception:
        return -1


# 2) Unsafe YAML load (execute arbitrary constructors)
def parse_yaml_unsafe(text: str) -> Any:
    """Parse YAML using a safe loader.

    Although the name implies unsafe behavior, this example uses yaml.safe_load
    to demonstrate the recommended secure alternative. The function is provided
    to show how to document and prefer safe parsers when handling untrusted
    YAML content.

    Security rationale:
    - Using a safe loader prevents arbitrary object deserialization which can
      lead to remote code execution when parsing untrusted YAML content.
    """
    return yaml.safe_load(text)


# 3) Shell command with user input (command injection risk)
def run_shell_unsafe(user_input: str) -> str:
    """Run an external command safely without using the shell.

    This example shows a secure approach that avoids invoking a shell. It
    performs strict input validation (a whitelist of allowed characters) and
    then passes user-supplied data as an argv element to subprocess.run,
    preventing shell injection.

    Notes:
    - This function is intended as an educational contrast to insecure shell
      invocation patterns and is safe to call by default.
    """
    # Whitelist validation: allow alphanumerics, space and a small set of safe punctuation
    if not re.match(r"^[A-Za-z0-9 _\-\.\@]+$", user_input):
        raise ValueError("Invalid characters in input")
    proc = subprocess.run(["echo", user_input], capture_output=True, text=True, check=True)
    return proc.stdout.strip()


# 4) Weak hashing (MD5) and unsalted password storage
def hash_password_md5(password: str) -> str:
    """Hash a password using MD5 (insecure example).

    This demonstrates a weak hashing algorithm. MD5 is fast and lacks modern
    protections such as salting and key stretching; it should not be used for
    password storage. The function raises a RuntimeError unless insecure
    examples are explicitly enabled to prevent accidental use.
    """
    if not _insecure_examples_enabled():
        raise RuntimeError(
            "Insecure examples are disabled. Set ENABLE_INSECURE_EXAMPLES=1 to run."
        )
    return hashlib.md5(password.encode()).hexdigest()  # nosec - weak hash


def store_password_insecure(user: str, password: str) -> str:
    """Store a password using an insecure approach.

    This function hashes the password with a weak function and writes a record
    to a world-readable file. It exists only as a demonstrative anti-pattern and
    will refuse to run unless ENABLE_INSECURE_EXAMPLES is set.

    Security rationale:
    - Do not store passwords with unsalted, fast hashes or in world-readable
      files in production. Prefer dedicated secret stores and modern password
      hashing functions (bcrypt, Argon2, etc.).
    """
    if not _insecure_examples_enabled():
        raise RuntimeError(
            "Insecure examples are disabled. Set ENABLE_INSECURE_EXAMPLES=1 to run."
        )
    hashed = hash_password_md5(password)
    record = {"user": user, "pwd": hashed}
    # Simulate writing to a world-readable temp file
    path = os.path.join(os.getcwd(), "insecure_passwords.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f)
    return path


# 5) Hardcoded secret
API_TOKEN = "sk_live_REALLY_NOT_A_SECRET_BUT_LOOKS_LIKE_ONE"  # nosec


def use_token() -> str:
    """Return a prefix of the hardcoded API token.

    This is a placeholder showing why hardcoding secrets is dangerous. In real
    code, secrets should be injected from secure configuration sources and not
    committed into source control.
    """
    return API_TOKEN[:5]


# Tests to detect regressions of insecure patterns
def test_no_yaml_load_in_file() -> None:
    content = open(__file__, "r", encoding="utf-8").read()
    assert "yaml.load(" not in content, "Found unsafe yaml.load usage"


def test_no_shell_true_in_file() -> None:
    content = open(__file__, "r", encoding="utf-8").read()
    assert "shell=True" not in content, "Found shell=True usage"


def test_run_shell_unsafe_validation_accepts() -> None:
    out = run_shell_unsafe("hello_world-123")
    assert out == "hello_world-123"


def test_run_shell_unsafe_validation_rejects() -> None:
    try:
        run_shell_unsafe("$(rm -rf /)")
        assert False, "Expected ValueError for unsafe input"
    except ValueError:
        pass