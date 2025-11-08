# controller/controller.py
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
import itertools
import json
import pathlib
import httpx

app = FastAPI(title="controller (HTTP/3-ready)")

# ---------- Load replica list ----------
CONFIG = pathlib.Path("config/replicas.json")
if CONFIG.exists():
    _cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    REPLICAS = _cfg.get("replicas", [])
else:
    REPLICAS = []

# Fallback if config missing/empty: two local replicas on HTTP
if not REPLICAS:
    REPLICAS = [
        {"name": "ReplicaA", "url": "http://127.0.0.1:9101"},
        {"name": "ReplicaB", "url": "http://127.0.0.1:9102"},
    ]

_rr = itertools.cycle(REPLICAS)


# ---------- Optional: advertise HTTP/3 and HTTP/2 via Alt-Svc ----------
@app.middleware("http")
async def advertise_h3(request: Request, call_next):
    resp = await call_next(request)
    # Tell clients that this same host also serves HTTP/3 on :8443 and HTTP/2 on :8000
    # (Browsers will learn this and upgrade to QUIC/H3 next requests.)
    resp.headers["Alt-Svc"] = 'h3=":8443"; ma=86400, h2=":8000"; ma=86400'
    return resp


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


# ---------- Proxy endpoint: client stays on controller URL ----------
@app.get("/videos/{video_name}")
async def proxy_video(video_name: str, request: Request):
    if not video_name:
        raise HTTPException(status_code=400, detail="video name required")

    # Round-robin choose a replica and build its URL
    target = next(_rr)["url"].rstrip("/") + f"/videos/{video_name}"

    # Forward byte-range header if the browser asks for partial content
    fwd_headers = {}
    if "range" in request.headers:
        fwd_headers["range"] = request.headers["range"]

    # Stream from replica to client; keep controller in the data path
    # httpx doesn't speak H3 yet; replicas can be HTTP/1.1 or HTTP/2 (http2=False here is very stable on Windows)
    async with httpx.AsyncClient(http2=False, timeout=None) as client:
        try:
            r = await client.stream("GET", target, headers=fwd_headers)
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"replica fetch error: {e!s}")

        # Allow 200 or 206; pass through 404/416; treat others as bad gateway
        if r.status_code in (404, 416):
            detail = (await r.aread()).decode("utf-8", "ignore")
            raise HTTPException(status_code=r.status_code, detail=detail)
        if r.status_code not in (200, 206):
            await r.aclose()
            raise HTTPException(status_code=502, detail=f"replica status {r.status_code}")

        # Propagate key headers for video playback
        passthrough = {}
        for h in ("content-type", "content-length", "content-range", "accept-ranges"):
            if h in r.headers:
                passthrough[h] = r.headers[h]

        return StreamingResponse(r.aiter_bytes(), status_code=r.status_code, headers=passthrough)
