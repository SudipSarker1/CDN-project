# controller/controller.py
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from urllib.parse import quote
import httpx
import os
import json
import random
import logging
import time

logger = logging.getLogger("controller")
logging.basicConfig(level=logging.INFO)

# ==== CORS config (frontend origin) ====
ALLOWED_ORIGINS = ["https://localhost:3000"]
EXPOSE_HEADERS = [
    "Accept-Ranges",
    "Content-Range",
    "ETag",
    "Last-Modified",
    "Cache-Control",
    "Content-Length",
    "Location",
]


def _corsify_headers(h: dict | None) -> dict:
    h = dict(h or {})
    h["Access-Control-Allow-Origin"] = ALLOWED_ORIGINS[0]
    h["Access-Control-Expose-Headers"] = ", ".join(EXPOSE_HEADERS)
    return h


# ==== Load replicas from config/replicas.json ====
BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG = BASE_DIR / "config" / "replicas.json"


def _load_replicas() -> list[str]:
    if not CONFIG.exists():
        logger.error("Missing replicas config file: %s", CONFIG)
        return []

    with CONFIG.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        replicas = data
    else:
        replicas = data.get("replicas", [])

    replicas = [r.rstrip("/") for r in replicas if isinstance(r, str)]

    logger.info("Loaded replicas: %s", replicas)
    return replicas


REPLICAS: list[str] = _load_replicas()

app = FastAPI(title="CDN Controller")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=EXPOSE_HEADERS,
)


# Optional: Alt-Svc for HTTP/3 from controller itself
@app.middleware("http")
async def add_alt_svc(request: Request, call_next):
    response = await call_next(request)
    # Adjust port if you move controller away from 8000
    response.headers["Alt-Svc"] = 'h3=":8000"; ma=86400'
    return response


# ---------- basic health + config ----------


@app.get("/healthz")
async def healthz():
    return JSONResponse({"ok": True}, headers=_corsify_headers({}))


@app.get("/config")
async def get_config():
    return JSONResponse({"replicas": REPLICAS}, headers=_corsify_headers({}))


# ---------- helper: choose closest replica by RTT ----------


async def choose_closest_replica() -> str:
    """
    Measure latency (RTT) to each replica's /healthz endpoint
    and return the URL of the 'closest' replica. If all checks
    fail, fall back to a random replica.
    """
    if not REPLICAS:
        raise RuntimeError("No replicas configured")

    timeout = httpx.Timeout(connect=0.5, read=1.0, write=1.0, pool=None)
    best_url: str | None = None
    best_rtt: float | None = None

    async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
        for url in REPLICAS:
            health_url = url.rstrip("/") + "/healthz"
            start = time.perf_counter()
            try:
                r = await client.get(health_url)
                r.raise_for_status()
                rtt = time.perf_counter() - start
                logger.info("Replica %s RTT ~ %.1f ms", url, rtt * 1000.0)

                if best_rtt is None or rtt < best_rtt:
                    best_rtt = rtt
                    best_url = url
            except Exception as e:
                logger.warning("Replica %s failed latency check: %r", url, e)

    if best_url is None:
        logger.warning("No replicas passed latency check; falling back to random.")
        return random.choice(REPLICAS)

    logger.info("Chose closest replica %s (%.1f ms)", best_url, best_rtt * 1000.0)
    return best_url


# ---------- debug: see all replicas' status + RTT ----------


@app.get("/debug/replicas")
async def debug_replicas():
    """
    Small debug endpoint to see each replica's /healthz status and RTT.
    Useful for testing 'closest replica' behavior.
    """
    if not REPLICAS:
        return JSONResponse({"error": "no replicas configured"}, headers=_corsify_headers({}))

    timeout = httpx.Timeout(connect=0.5, read=1.0, write=1.0, pool=None)
    out: dict[str, dict] = {}

    async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
        for i, url in enumerate(REPLICAS):
            health_url = url.rstrip("/") + "/healthz"
            key = f"replica{i}"
            start = time.perf_counter()
            try:
                r = await client.get(health_url)
                r.raise_for_status()
                rtt = time.perf_counter() - start
                out[key] = {
                    "url": url,
                    "ok": True,
                    "status": r.status_code,
                    "rtt_ms": round(rtt * 1000.0, 1),
                }
            except Exception as e:
                rtt = time.perf_counter() - start
                out[key] = {
                    "url": url,
                    "ok": False,
                    "error": str(e),
                    "rtt_ms": round(rtt * 1000.0, 1),
                }

    return JSONResponse(out, headers=_corsify_headers({}))


# ---------- main router: redirect to closest replica ----------


@app.get("/videos/{video_id}")
async def route_video(video_id: str, request: Request):
    """
    Main entry point for the frontend.

    Instead of round-robin/random, we choose the 'closest' replica
    based on live RTT measurements to /healthz, then return a 302
    redirect so the browser fetches the video directly from that replica.
    """
    chosen = await choose_closest_replica()
    target = f"{chosen}/videos/{quote(video_id)}.mp4"

    return RedirectResponse(
        url=target,
        status_code=302,
        headers=_corsify_headers({"Location": target}),
    )
