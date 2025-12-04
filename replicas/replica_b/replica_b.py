# replicas/replica_b/replica_b.py
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from hashlib import md5
import mimetypes
from email.utils import formatdate

ALLOWED_ORIGINS = ["https://localhost:3443"] # UPDATED to 3443
EXPOSE_HEADERS = [
    "Accept-Ranges",
    "Content-Range",
    "ETag",
    "Last-Modified",
    "Cache-Control",
    "Content-Length",
]


def _corsify_headers(h: dict | None) -> dict:
    h = dict(h or {})
    h["Access-Control-Allow-Origin"] = ALLOWED_ORIGINS[0]
    h["Access-Control-Expose-Headers"] = ", ".join(EXPOSE_HEADERS)
    return h


app = FastAPI(title="Replica B")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "HEAD", "OPTIONS", "POST"],
    allow_headers=["*"],
    expose_headers=EXPOSE_HEADERS,
)


@app.middleware("http")
async def add_alt_svc(request: Request, call_next):
    # Advertise HTTP/3 on :9442 (UPDATED from 9102)
    response = await call_next(request)
    response.headers["Alt-Svc"] = 'h3=":9442"; ma=86400'
    return response


BASE_DIR = Path(__file__).resolve().parent
VIDEOS_DIR = BASE_DIR / "videos"


@app.options("/videos/{name}")
def options_video(name: str):
    return Response(status_code=204, headers=_corsify_headers({}))


@app.get("/healthz")
def healthz():
    """Used by controller + origin to check if this replica is healthy."""
    return JSONResponse({"ok": True}, headers=_corsify_headers({}))


# ---------- ORIGIN PUSH ENTRYPOINT ----------

@app.post("/upload")
async def upload_video(
    request: Request,
    video_id: str = Header(..., alias="video-id"),
):
    """
    Called by the origin. Saves the uploaded video as videos/{video_id}.mp4
    """
    try:
        data = await request.body()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"failed to read body: {e!s}")

    if not data:
        raise HTTPException(status_code=400, detail="empty upload body")

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    target = (VIDEOS_DIR / f"{video_id}.mp4").resolve()

    if not str(target).startswith(str(VIDEOS_DIR)):
        raise HTTPException(status_code=400, detail="invalid video-id")

    with target.open("wb") as f:
        f.write(data)

    return {"ok": True, "stored_as": target.name, "size": len(data)}


# ---------- VIDEO STREAMING TO CLIENTS ----------

def _headers_for_file(p: Path) -> dict:
    st = p.stat()
    etag = '"' + md5(f"{st.st_mtime_ns}-{st.st_size}".encode()).hexdigest() + '"'
    last_mod = formatdate(st.st_mtime, usegmt=True)
    ct, _ = mimetypes.guess_type(p.name)
    h = {
        "Content-Type": ct or "application/octet-stream",
        "Accept-Ranges": "bytes",
        "ETag": etag,
        "Last-Modified": last_mod,
        "Cache-Control": "public, max-age=3600",
    }
    return _corsify_headers(h)


def _iter_file(p: Path, start: int, end: int, chunk: int = 512 * 1024):
    with p.open("rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            data = f.read(min(chunk, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


@app.get("/videos/{name}")
async def get_video(name: str, request: Request):
    p = (VIDEOS_DIR / name).resolve()
    if not p.exists() or not str(p).startswith(str(VIDEOS_DIR)):
        raise HTTPException(status_code=404, detail="not found")

    h_base = _headers_for_file(p)
    size = p.stat().st_size
    rng = request.headers.get("range")

    if rng and rng.startswith("bytes="):
        try:
            part = rng.split("=", 1)[1]
            s, e = part.split("-", 1)
            start = int(s) if s else 0
            end = int(e) if e else size - 1
            start = max(0, start)
            end = min(size - 1, end)
            headers = dict(h_base)
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
            headers["Content-Length"] = str(end - start + 1)
            return StreamingResponse(
                _iter_file(p, start, end),
                status_code=206,
                headers=headers,
            )
        except Exception:
            pass

    headers = dict(h_base)
    headers["Content-Length"] = str(size)
    return StreamingResponse(
        _iter_file(p, 0, size - 1),
        status_code=200,
        headers=headers,
    )