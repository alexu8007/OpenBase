"""
Simple API tests for the FastAPI app in api_fastapi.py. These tests avoid
external network calls and focus on basic validation behavior.
"""
from __future__ import annotations

import unittest

import pytest
from fastapi.testclient import TestClient

from benchmarkv01.api_fastapi import app


tc = unittest.TestCase()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    tc.assertEqual(r.status_code, 200)
    body = r.json()
    tc.assertIn("status", body)
    tc.assertEqual(body["status"], "ok")
    tc.assertIsInstance(body["status"], str)


def test_create_item_validation(client):
    # Missing name should fail on the validated route
    r = client.post("/items", json={"quantity": 3})
    tc.assertEqual(r.status_code, 422)

    r = client.post("/items", json={"name": "widget", "quantity": 2})
    tc.assertEqual(r.status_code, 201)
    body = r.json()
    tc.assertIn("name", body)
    tc.assertIn("quantity", body)
    tc.assertEqual(body["name"], "widget")
    tc.assertEqual(body["quantity"], 2)
    tc.assertIsInstance(body["quantity"], int)


def test_unsafe_items(client):
    r = client.post("/unsafe-items", json={"name": "x"})
    tc.assertEqual(r.status_code, 200)
    # Ensure response is JSON and has an expected content-type
    tc.assertIn("application/json", r.headers.get("content-type", ""))

    r2 = client.post("/unsafe-items", json={})
    tc.assertEqual(r2.status_code, 400)
    tc.assertIn("application/json", r2.headers.get("content-type", ""))


def test_search_mixed_validation(client):
    r = client.get("/search", params={"q": "foo", "limit": "5"})
    tc.assertEqual(r.status_code, 200)
    body = r.json()
    tc.assertIn("limit", body)
    # ensure limit is parsed as an integer
    tc.assertEqual(body["limit"], 5)
    tc.assertIsInstance(body["limit"], int)

    # Bad limit shows unsafe cast behavior; be explicit about allowed error codes
    r2 = client.get("/search", params={"limit": "not-an-int"})
    tc.assertIn(r2.status_code, (500, 422))