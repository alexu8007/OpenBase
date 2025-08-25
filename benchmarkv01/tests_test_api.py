"""
Simple API tests for the FastAPI app in api_fastapi.py. These tests avoid
external network calls and focus on basic validation behavior.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from benchmarkv01.api_fastapi import app


@pytest.fixture
def client():
    """Provide a fresh TestClient for each test to avoid shared state."""
    with TestClient(app) as c:
        yield c


def test_api_health_endpoint_returns_ok(client):
    """Health endpoint should report status ok and return HTTP 200."""
    r = client.get("/health")
    if r.status_code != 200:
        raise AssertionError(f"Expected HTTP 200 from /health, got {r.status_code}")
    status = r.json().get("status")
    if status != "ok":
        raise AssertionError(f"Expected JSON status 'ok' from /health, got {status}")


def test_items_creation_validation(client):
    """Validated /items route should enforce required fields and allow creation."""
    # Missing name should fail on the validated route
    r = client.post("/items", json={"quantity": 3})
    if r.status_code != 422:
        raise AssertionError(f"Expected HTTP 422 for missing 'name', got {r.status_code}")

    r = client.post("/items", json={"name": "widget", "quantity": 2})
    if r.status_code != 201:
        raise AssertionError(f"Expected HTTP 201 when creating item, got {r.status_code}")
    body = r.json()
    name = body.get("name")
    quantity = body.get("quantity")
    if name != "widget":
        raise AssertionError(f"Expected created item name 'widget', got {name}")
    if quantity != 2:
        raise AssertionError(f"Expected created item quantity 2, got {quantity}")


def test_unsafe_items_behaviour(client):
    """Unsafe items route returns 200 for provided name and 400 for missing data."""
    r = client.post("/unsafe-items", json={"name": "x"})
    if r.status_code != 200:
        raise AssertionError(f"Expected HTTP 200 when posting unsafe item with name, got {r.status_code}")

    r2 = client.post("/unsafe-items", json={})
    if r2.status_code != 400:
        raise AssertionError(f"Expected HTTP 400 when posting unsafe item without data, got {r2.status_code}")


def test_search_endpoint_mixed_validation(client):
    """Search endpoint should cast valid limits and surface errors for bad input."""
    r = client.get("/search", params={"q": "foo", "limit": "5"})
    if r.status_code != 200:
        raise AssertionError(f"Expected HTTP 200 for valid search params, got {r.status_code}")
    limit_value = r.json().get("limit")
    if limit_value != 5:
        raise AssertionError(f"Expected 'limit' value 5 after casting, got {limit_value}")

    # Bad limit shows unsafe cast behavior; accept either a server error or validation error
    r2 = client.get("/search", params={"limit": "not-an-int"})
    if r2.status_code not in (500, 422):
        raise AssertionError(f"Expected HTTP 500 or 422 for invalid limit, got {r2.status_code}")