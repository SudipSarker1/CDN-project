from __future__ import annotations

import asyncio
import json
import logging
from itertools import count
from pathlib import Path
from typing import Iterable, List, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Response

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config" / "replicas.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("controller")

with CONFIG_FILE.open("r", encoding="utf-8-sig") as f:
    data = json.load(f)
if isinstance(data, dict) and "replicas" in data:
    replicas: List[str] = [str(u).rstrip("/") for u in data["replicas"]]
elif isinstance(data, list):
    replicas = [str(u).rstrip("/") for u in data]
else:
    raise RuntimeError("config/replicas.json must be a list or an object with 'replicas'")
if not replicas:
    raise RuntimeError("replicas list is empty")
log.info("Loaded replicas: %s", replicas)

# ---- health monitor (async) ----
HEALTH: dict[str, bool] = {r: True for r in replicas}
CHECK_INTERVAL = 5.0  # seconds
HEALTH_TIMEOUT = httpx.Timeout(3.0, connect=1.0)

async def _check_once():
    async with httpx.AsyncClient(http2=False, verify=False, timeout=HEALTH_TIMEOUT) as c:
        for r in replicas:
            ok = False
            try:
                resp = await c.get(f"{r}/healthz")
                ok = (200 <= resp.status_code < 300)
            except Exception:
                ok = False
            HEALTH[r] = ok

async def health_task():
    while True:
        await _check_once()
        await asyncio.sleep(CHECK_INTERVAL)

_rr = count(0)
def next_index() -> int: return next(_rr) % len(replicas)

def healthy_cycle(start_idx: int) -> Iterable[str]:
    # prefer healthy replicas; if none healthy, try all
    healthy = [r for r in replicas if HEALTH.get(r, False)]
    pool = healthy if healthy else list(replicas)
    n = len(pool)
    for k in range(n):
        yield pool[(start_idx + k) % n]

app = FastAPI(title="CDN Controller")

@app.on_event("startup")
async def _startup():
    asyncio.create_task(health_task())

@app.middleware("http")
async def add_alt_svc_header(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("Alt-Svc", 'h3=":8443"; ma=86400, h2=":8000"; ma=86400')
    return resp

@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True, "replicas": replicas, "health": HEALTH}

def _normalize_name(video_id: str) -> str:
    return video_id if video_id.endswith(".mp4") else f"{video_id}.mp4"

async def _fetch_bytes(url: str, hdrs: dict) -> Response | None:
    timeout = httpx.Timeout(60.0, connect=10.0)
    async with httpx.AsyncClient(http2=False, verify=False, timeout=timeout) as client:
        try:
            r = await client.get(url, headers=hdrs)
        except Exception as e:
            log.warning("Replica request failed: %s -> %s", url, e)
            return None

        # Accept 200, 206 (content) and 304 (not modified)
        if r.status_code not in (200, 206, 304):
            log.info("Replica returned %s for %s (body preview=%r)", r.status_code, url, r.text[:200])
            return None

        h: dict[str, str] = {}
        for k in ("content-type", "content-length", "content-range", "accept-ranges", "last-modified", "etag", "cache-control"):
            if k in r.headers:
                h[k.title()] = r.headers[k]

        return Response(content=r.content if r.status_code != 304 else b"",  # no body on 304
                        status_code=r.status_code,
                        headers=h,
                        media_type=r.headers.get("content-type", "application/octet-stream"))

@app.get("/videos/{video_id}")
async def get_video(
    video_id: str,
    range: Optional[str] = Header(None),
    if_none_match: Optional[str] = Header(None, alias="If-None-Match"),
    if_modified_since: Optional[str] = Header(None, alias="If-Modified-Since"),
) -> Response:
    remote_name = _normalize_name(video_id)
    start = next_index()
    tried: List[str] = []

    fwd_headers: dict[str, str] = {}
    if range: fwd_headers["Range"] = range
    if if_none_match: fwd_headers["If-None-Match"] = if_none_match
    if if_modified_since: fwd_headers["If-Modified-Since"] = if_modified_since

    for base in healthy_cycle(start):
        url = f"{base}/videos/{remote_name}"
        tried.append(url)
        resp = await _fetch_bytes(url, fwd_headers)
        if resp is not None:
            return resp

    detail = f"All replicas failed for {remote_name}. Tried: {', '.join(tried)}"
    log.error(detail)
    raise HTTPException(status_code=502, detail=detail)

@app.head("/videos/{video_id}")
async def head_video(video_id: str) -> Response:
    remote = _normalize_name(video_id)
    start = next_index()
    timeout = httpx.Timeout(20.0, connect=5.0)
    async with httpx.AsyncClient(http2=False, verify=False, timeout=timeout) as client:
        for base in healthy_cycle(start):
            url = f"{base}/videos/{remote}"
            try:
                r = await client.request("HEAD", url)
            except Exception:
                continue
            if r.status_code == 200:
                headers = {
                    "Accept-Ranges": r.headers.get("accept-ranges", "bytes"),
                    "Content-Type": r.headers.get("content-type", "video/mp4"),
                }
                if "content-length" in r.headers:
                    headers["Content-Length"] = r.headers["content-length"]
                if "etag" in r.headers:
                    headers["ETag"] = r.headers["etag"]
                if "last-modified" in r.headers:
                    headers["Last-Modified"] = r.headers["last-modified"]
                if "cache-control" in r.headers:
                    headers["Cache-Control"] = r.headers["cache-control"]
                return Response(status_code=200, headers=headers)

    raise HTTPException(status_code=404, detail=f"{remote} not found on any replica")
