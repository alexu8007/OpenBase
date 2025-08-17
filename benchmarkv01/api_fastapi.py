from typing import Any, Dict, List, Optional

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


@app.post("/items", response_model=OutputItem, status_code=201)
def create_item(item: InputItem, db: Dict[str, Any] = Depends(get_fake_db)) -> OutputItem:
    """Validated route using a Pydantic model (good practice)."""
    # Pretend we wrote to DB and got an ID back
    new_id = 1 if db.get("connected") else 0
    return OutputItem(id=new_id, name=item.name, quantity=item.quantity, tags=item.tags or [])


@app.post("/unsafe-items")
def create_item_unsafe(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Unvalidated body payload (bad practice). Intentional for benchmarking
    input validation detection.
    """
    if "name" not in payload:
        # Even the error handling reveals missing schema guarantees
        raise HTTPException(status_code=400, detail="name is required")
    return {"ok": True, "item": payload}


@app.get("/search")
def search(q: Optional[str] = Query(None), limit: Optional[str] = Query(None)) -> Dict[str, Any]:
    """
    Mixed validation: 'q' is optional; 'limit' is accepted as string and then cast
    without validation, which can raise at runtime (intentional smell).
    """
    parsed_limit: int
    if limit is None:
        parsed_limit = 10
    else:
        # Intentionally unsafe cast for the benchmark to flag
        parsed_limit = int(limit)  # noqa: PLW1510 (example of unsafe parsing)
    return {"q": q, "limit": parsed_limit}


@app.get("/external")
def call_external_service() -> Dict[str, Any]:
    """
    External HTTP call without explicit timeout (security/robustness smell) —
    present intentionally so scanners can flag it.
    """
    import requests  # Local import to avoid import cost when unused

    response = requests.get("https://httpbin.org/delay/1")  # no timeout on purpose
    return {"status_code": response.status_code}


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
    """
    return {"id": item_id, "x_request_id": x_request_id}


@app.post("/webhook")
def webhook(event: Dict[str, Any] = Body(...), signature: Optional[str] = Header(None)) -> Response:
    """
    Deliberately naive signature handling (missing HMAC validation) for scanners to flag.
    """
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

    def do_work(data: Dict[str, Any]) -> None:
        # Intentional: no try/except, no timeout — to be flagged by robustness checks
        import time as _time

        _time.sleep(0.01)
        _ = data.get("foo")

    background_tasks.add_task(do_work, payload)
    return {"scheduled": True}
