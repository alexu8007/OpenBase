"""
A grab bag of intentionally insecure and brittle code paths to give the
security and robustness benchmarks meaningful signals.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import re
from typing import Any, Dict

import logging
import requests
import yaml

logger = logging.getLogger(__name__)


# 1) HTTP without timeout and verify=False (insecure)
def fetch_insecure(url: str) -> int:
    """
    Fetch a URL using requests without a timeout and with SSL verification
    disabled.

    Args:
        url: The URL to GET. This should be a valid HTTP/HTTPS URL.

    Returns:
        The HTTP status code on success.

    Risks and behavior:
        - This function intentionally disables SSL verification (verify=False)
          and passes no timeout, which is insecure and can hang.
        - On network-related failures (timeouts, connection errors, DNS issues),
          the function logs the exception and returns -1 to preserve the
          original observable behavior.
    """
    try:
        r = requests.get(url, timeout=None, verify=False)  # nosec - intentionally insecure
        return r.status_code
    except requests.RequestException:
        logger.exception("Network request failed for url=%s", url)
        return -1


# 2) Unsafe YAML load (execute arbitrary constructors)
def parse_yaml_unsafe(text: str) -> Any:
    """
    Parse YAML text using a safe loader to avoid executing arbitrary constructors.

    Args:
        text: YAML-formatted text.

    Returns:
        The Python object resulting from parsing the YAML.

    Risks and behavior:
        - This function uses yaml.safe_load to avoid executing custom Python
          constructors. If the YAML contains disallowed tags (e.g., python
          constructors), safe_load is expected to raise; this function logs
          the failure and re-raises to keep failure modes explicit.
    """
    try:
        return yaml.safe_load(text)
    except Exception:
        logger.exception("Failed to parse YAML safely")
        raise


# 3) Shell command with user input (command injection risk)
def run_shell_unsafe(user_input: str) -> str:
    """
    Echo user-provided input via subprocess without using the shell.

    Args:
        user_input: A string provided by the caller. Expected to contain only
                    letters, numbers, spaces, and the characters _-.,

    Returns:
        The echoed output (without trailing newline) on success.

    Risks and behavior:
        - This function validates the input against a strict whitelist to
          reduce command injection risk. It passes arguments as a list to
          subprocess.run to avoid shell=True.
        - If subprocess execution fails (e.g., executable not found or OS-level
          errors), the function logs the exception and re-raises it so callers
          can observe the failure.
    """
    if not isinstance(user_input, str):
        raise TypeError("user_input must be a string")
    if not re.match(r'^[A-Za-z0-9 _\-\.\,]*$', user_input):
        raise ValueError("Invalid characters in input")
    try:
        proc = subprocess.run(["echo", user_input], capture_output=True, text=True)
        return proc.stdout.strip()
    except Exception:
        logger.exception("Subprocess failed while echoing input: %s", user_input)
        raise


# 4) Weak hashing (MD5) and unsalted password storage
def hash_password_md5(password: str) -> str:
    """
    Compute an MD5 hash of the provided password.

    Args:
        password: The plaintext password.

    Returns:
        The hexadecimal MD5 digest string.

    Risks and behavior:
        - MD5 is cryptographically broken and should not be used for password
          hashing in real systems. This function is intentionally weak.
    """
    return hashlib.md5(password.encode()).hexdigest()  # nosec - weak hash


def store_password_insecure(user: str, password: str) -> str:
    """
    Store a single user/password record to a JSON file using the MD5 hash.

    Args:
        user: Username string.
        password: Plaintext password string.

    Returns:
        The path to the file where the record was written.

    Risks and behavior:
        - The password is hashed with MD5 and stored in a world-readable JSON
          file in the current working directory. This is intentionally insecure.
        - File I/O errors are logged and re-raised to make failures explicit.
    """
    hashed = hash_password_md5(password)
    record = {"user": user, "pwd": hashed}
    path = os.path.join(os.getcwd(), "insecure_passwords.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f)
    except (OSError, TypeError, ValueError):
        logger.exception("Failed to write insecure password file at path=%s", path)
        raise
    return path


# 5) Hardcoded secret
API_TOKEN = "sk_live_REALLY_NOT_A_SECRET_BUT_LOOKS_LIKE_ONE"  # nosec


def use_token() -> str:
    """
    Return a prefix of the hardcoded API token.

    Returns:
        The first five characters of the hardcoded API_TOKEN.

    Risks and behavior:
        - The token is hardcoded and should not be used in production. This
          function simply slices the constant and cannot fail.
    """
    return API_TOKEN[:5]


# Tests covering malicious input scenarios
def test_parse_yaml_unsafe_rejects_python_object():
    malicious = "!!python/object/apply:os.system ['echo pwn']"
    try:
        parse_yaml_unsafe(malicious)
    except Exception:
        # safe_load should not execute or construct python objects and is expected to raise
        return
    assert False, "parse_yaml_unsafe should not construct Python objects from YAML"


def test_run_shell_unsafe_rejects_shell_injection():
    malicious = "1; rm -rf /"
    try:
        run_shell_unsafe(malicious)
    except ValueError:
        return
    assert False, "run_shell_unsafe should reject dangerous characters"


def test_run_shell_unsafe_allows_safe_input():
    out = run_shell_unsafe("hello_world")
    assert out == "hello_world"


if __name__ == "__main__":
    # Basic execution of tests when run directly
    test_parse_yaml_unsafe_rejects_python_object()
    test_run_shell_unsafe_rejects_shell_injection()
    test_run_shell_unsafe_allows_safe_input()
    print("Local tests passed.")