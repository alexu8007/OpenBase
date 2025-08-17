"""
A grab bag of intentionally insecure and brittle code paths to give the
security and robustness benchmarks meaningful signals.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from typing import Any, Dict

import requests
import yaml


# 1) HTTP without timeout and verify=False (insecure)
def fetch_insecure(url: str) -> int:
    try:
        r = requests.get(url, timeout=None, verify=False)  # nosec - intentionally insecure
        return r.status_code
    except Exception:
        return -1


# 2) Unsafe YAML load (execute arbitrary constructors)
def parse_yaml_unsafe(text: str) -> Any:
    # nosec: This is intentionally vulnerable for scanning
    return yaml.load(text, Loader=yaml.Loader)


# 3) Shell command with user input (command injection risk)
def run_shell_unsafe(user_input: str) -> str:
    # nosec: intentionally uses shell=True
    proc = subprocess.run(f"echo {user_input}", shell=True, capture_output=True, text=True)
    return proc.stdout.strip()


# 4) Weak hashing (MD5) and unsalted password storage
def hash_password_md5(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()  # nosec - weak hash


def store_password_insecure(user: str, password: str) -> str:
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
    return API_TOKEN[:5]
