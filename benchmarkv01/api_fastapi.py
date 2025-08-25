from typing import Any, Dict, List, Optional

import logging

from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Path,
    Query,
    Response,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse


logger = logging.getLogger(__name__)

app = FastAPI(title="Benchmarkv01 API Example")

# Broad CORS (intentionally over-permissive for scanners to flag)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InputItem(BaseModel):
    name: str = Field(min_length=1)
    quantity: int = Field(ge=1, le=10_000)
    tags: Optional[List[str]] = None


class OutputItem(BaseModel):
    id: int
    name: str
    quantity: int
    tags: List[str] = []


class HealthStatus(BaseModel):
    status: str
    version: str


def get_fake_db():
    """A minimal dependency that mimics a DB session lifecycle."""
    db = {"connected": True}
    try:
        yield db
    finally:
        db["connected"] = False


def get_http_client():
    """
    Return the default HTTP client. This function is deliberately small and imported
    locally to allow tests to monkeypatch or override the returned client for
    dependency injection without changing endpoint signatures.
    """
    import requests  # Local import to avoid import cost when unused
    from requests.adapters import HTTPAdapter
    try:
        from urllib3.util import Retry
    except Exception:
        # Best-effort fallback: if urllib3 Retry is unavailable, return a plain session.
        return requests.Session()

    session = requests.Session()
    # Configure a conservative retry strategy with exponential backoff to mitigate transient failures
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def perform_get(url: str, timeout: float = 5.0) -> Dict[str, Any]:
    """
    Wrapper around an HTTP GET request that enforces a timeout, performs basic
    URL/host validation to reduce SSRF risk, and translates network errors into
    HTTPExceptions suitable for FastAPI responses.

    Args:
        url: The URL to fetch.
        timeout: Timeout in seconds for the request.

    Returns:
        A dict containing the status_code returned by the external service.

    Raises:
        HTTPException: 400 for invalid input, 503 when the external service is unavailable,
                       504 on timeout, 500 on unexpected errors.
    """
    client = get_http_client()

    # Basic input validation and sanitization
    from urllib.parse import urlparse

    if not isinstance(url, str) or not url:
        raise HTTPException(status_code=400, detail="invalid url")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=400, detail="invalid url")

    # Prevent requests to internal/loopback addresses (basic SSRF mitigation)
    import socket
    import ipaddress

    hostname = parsed.hostname
    try:
        addrinfos = socket.getaddrinfo(hostname, None)
    except Exception as exc:
        logger.warning("DNS resolution failed for host %s: %s", hostname, exc)
        raise HTTPException(status_code=400, detail="invalid host")

    for info in addrinfos:
        sockaddr = info[4]
        # sockaddr is typically (ip, port) for IPv4 or (ip, port, flowinfo, scopeid) for IPv6
        ip_str = sockaddr[0] if isinstance(sockaddr, (list, tuple)) and sockaddr else None
        if not ip_str:
            continue
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_link_local or ip_obj.is_multicast:
                logger.warning("Blocked request to non-public IP %s for host %s", ip_str, hostname)
                raise HTTPException(status_code=400, detail="disallowed host")
        except ValueError:
            # If parsing fails, skip this address (cannot verify); be conservative and block
            logger.warning("Unable to parse resolved address %s for host %s", ip_str, hostname)
            raise HTTPException(status_code=400, detail="invalid host address")

    try:
        response = client.get(url, timeout=timeout)
        # Return status code even for 4xx/5xx so caller can make informed decisions.
        return {"status_code": response.status_code}
    except Exception as exc:
        # Prefer specific requests exception handling when available
        try:
            from requests.exceptions import RequestException, Timeout as RequestsTimeout
        except Exception:
            RequestException = Exception
            RequestsTimeout = Exception

        if isinstance(exc, RequestsTimeout):
            logger.warning("External request to %s timed out: %s", url, exc)
            raise HTTPException(status_code=504, detail="external service timeout")
        if isinstance(exc, RequestException):
            logger.warning("External request to %s failed: %s", url, exc)
            raise HTTPException(status_code=503, detail="external service unavailable")
        logger.exception("Unexpected error during external call to %s", url)
        raise HTTPException(status_code=500, detail="internal error")


@app.post("/items", response_model=OutputItem, status_code=201)
def create_item(item: InputItem, db: Dict[str, Any] = Depends(get_fake_db)) -> OutputItem:
    """Validated route using a Pydantic model (good practice)."""
    # Pretend we wrote to DB and got an ID back
    new_id = 1 if db.get("connected") else 0
    return OutputItem(id=new_id, name=item.name, quantity=item.quantity, tags=item.tags or [])


@app.post("/unsafe-items")
def create_item_unsafe(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Unvalidated body payload (bad practice). Improved here with simple defensive
    validation to ensure the payload resembles the expected shape.

    Validates:
    - payload is a dict
    - 'name' key exists and is a non-empty string

    Returns:
        A success dict containing the provided item.
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be a JSON object")
    if "name" not in payload:
        # Even the error handling reveals missing schema guarantees
        raise HTTPException(status_code=400, detail="name is required")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=400, detail="name must be a non-empty string")
    return {"ok": True, "item": payload}


@app.get("/search")
def search(q: Optional[str] = Query(None), limit: Optional[str] = Query(None)) -> Dict[str, Any]:
    """
    Mixed validation: 'q' is optional; 'limit' is accepted as string but validated
    and safely parsed here to avoid runtime crashes.

    'limit' is parsed to an int with basic bounds checking.
    """
    if limit is None:
        parsed_limit = 10
    else:
        try:
            parsed_limit = int(limit)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="limit must be an integer")
        if parsed_limit < 1 or parsed_limit > 10000:
            raise HTTPException(status_code=400, detail="limit out of allowed range")
    return {"q": q, "limit": parsed_limit}


@app.get("/external")
def call_external_service() -> Dict[str, Any]:
    """
    External HTTP call with a timeout and exception handling. The actual HTTP client
    is obtained via a small wrapper (get_http_client) so tests can mock or monkeypatch
    the client without changing this endpoint's signature.
    """
    return perform_get("https://httpbin.org/delay/1")


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    """Simple health endpoint to support ops checks."""
    return HealthStatus(status="ok", version="v0")


@app.get("/items/{item_id}")
def get_item(
    item_id: int = Path(..., ge=1),
    x_request_id: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Returns an item-like structure. Includes optional header extraction.

    Validates:
    - item_id is enforced by Path(...) with ge=1
    """
    return {"id": item_id, "x_request_id": x_request_id}


@app.post("/webhook")
def webhook(event: Dict[str, Any] = Body(...), signature: Optional[str] = Header(None)) -> Response:
    """
    Deliberately naive signature handling (missing HMAC validation) for scanners to flag.

    Adds input validation to ensure 'event' is an object and signature is provided.
    """
    if not isinstance(event, dict):
        raise HTTPException(status_code=400, detail="event must be a JSON object")
    if not signature:
        raise HTTPException(status_code=400, detail="missing signature")
    # Unsafe: we do not actually verify signature
    return Response(status_code=202)


@app.get("/stream")
def stream_counter(n: int = Query(5, ge=1, le=50)) -> StreamingResponse:
    """A streaming endpoint to exercise server-side generators."""
    def generator():
        for i in range(n):
            yield f"data: {i}\n"
    return StreamingResponse(generator(), media_type="text/plain")


@app.post("/background")
def background_example(background_tasks: BackgroundTasks, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Schedules a background task to simulate async work."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be a JSON object")

    def do_work(data: Dict[str, Any]) -> None:
        # Intentional: no try/except, no timeout — to be flagged by robustness checks
        import time as _time

        _time.sleep(0.01)
        _ = data.get("foo")

    background_tasks.add_task(do_work, payload)
    return {"scheduled": True}