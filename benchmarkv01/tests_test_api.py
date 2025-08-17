"""
Simple API tests for the FastAPI app in api_fastapi.py. These tests avoid
external network calls and focus on basic validation behavior.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from benchmarkv01.api_fastapi import app


client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_item_validation():
    # Missing name should fail on the validated route
    r = client.post("/items", json={"quantity": 3})
    assert r.status_code == 422

    r = client.post("/items", json={"name": "widget", "quantity": 2})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "widget"
    assert body["quantity"] == 2


def test_unsafe_items():
    r = client.post("/unsafe-items", json={"name": "x"})
    assert r.status_code == 200

    r2 = client.post("/unsafe-items", json={})
    assert r2.status_code == 400


def test_search_mixed_validation():
    r = client.get("/search", params={"q": "foo", "limit": "5"})
    assert r.status_code == 200
    assert r.json()["limit"] == 5

    # Bad limit shows unsafe cast behavior
    r2 = client.get("/search", params={"limit": "not-an-int"})
    assert r2.status_code == 500 or r2.status_code == 422
