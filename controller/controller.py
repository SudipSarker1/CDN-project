# controller/controller.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import httpx, os, json, random, logging
from urllib.parse import quote

logger = logging.getLogger("controller")
logging.basicConfig(level=logging.INFO)

# ==== CORS config (frontend origin) ====
ALLOWED_ORIGINS = ["https://localhost:3000"]
EXPOSE_HEADERS = [
    "Accept-Ranges", "Content-Range", "ETag", "Last-Modified",
    "Cache-Control", "Content-Length", "Location"
]


def _corsify_headers(h: dict | None) -> dict:
    h = dict(h or {})
    h["Access-Control-Allow-Origin"] = ALLOWED_ORIGINS[0]
    h["Access-Control-Expose-Headers"] = ", ".join(EXPOSE_HEADERS)
    return h


app = FastAPI(title="Controller")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=EXPOSE_HEADERS,
)

# Alt-Svc middleware to advertise HTTP/3 on port 8000
@app.middleware("http")
async def add_alt_svc(request: Request, call_next):
    response = await call_next(request)
    # Advertise HTTP/3/QUIC on same port
    response.headers["Alt-Svc"] = 'h3=":8000"; ma=86400'
    return response


def load_replicas() -> list[str]:
    cfg = os.path.join("config", "replicas.json")
    with open(cfg, "r", encoding="utf-8") as f:
        data = json.load(f)
    reps = data if isinstance(data, list) else data.get("replicas", [])
    if not reps:
        raise RuntimeError("No replicas configured")
    logger.info("Loaded replicas: %s", reps)
    return reps


REPLICAS = load_replicas()

# ---------- utility endpoints ----------


@app.options("/videos/{video_id}")
def options_video(video_id: str):
    return Response(status_code=204, headers=_corsify_headers({}))


@app.get("/healthz")
def healthz():
    return JSONResponse({"ok": True, "replicas": REPLICAS}, headers=_corsify_headers({}))


@app.get("/debug/probe")
async def probe():
    """
    Small helper endpoint to check that replicas respond with partial content.
    This does NOT force HTTP/2 anymore; it uses default negotiation.
    """
    out: dict[str, dict] = {}
    async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
        for i, r in enumerate(REPLICAS, 1):
            url = f"{r}/videos/sample.mp4"
            try:
                res = await client.get(url, headers={"Range": "bytes=0-0"})
                out[f"replica{i}"] = {
                    "url": url,
                    "status": res.status_code,
                    "len": int(res.headers.get("content-length", 0) or 0),
                    "content-range": res.headers.get("content-range"),
                    "server": res.headers.get("server"),
                    "protocol": res.http_version,
                }
            except Exception as e:
                out[f"replica{i}"] = {"url": url, "error": str(e)}
    return JSONResponse(out, headers=_corsify_headers({}))


# ---------- main router ----------
@app.get("/videos/{video_id}")
async def route_video(video_id: str, request: Request):
    """
    Select a replica and redirect the browser there.
    The browser then talks directly to the replica (HTTP/1.1 / HTTP/2 / HTTP/3).
    """
    chosen = random.choice(REPLICAS)
    target = f"{chosen}/videos/{quote(video_id)}.mp4"
    return RedirectResponse(
        url=target,
        status_code=302,
        headers=_corsify_headers({"Location": target}),
    )
