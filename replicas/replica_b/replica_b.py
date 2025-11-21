# replicas/replica_b/replica_b.py
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from hashlib import md5
import mimetypes
from email.utils import formatdate

ALLOWED_ORIGINS = ["https://localhost:3000"]
EXPOSE_HEADERS = [
    "Accept-Ranges", "Content-Range", "ETag", "Last-Modified",
    "Cache-Control", "Content-Length"
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
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=EXPOSE_HEADERS,
)

# Alt-Svc to advertise HTTP/3 on 9102
@app.middleware("http")
async def add_alt_svc(request: Request, call_next):
    response = await call_next(request)
    response.headers["Alt-Svc"] = 'h3=":9102"; ma=86400'
    return response


BASE_DIR = Path(__file__).resolve().parent
VIDEOS_DIR = BASE_DIR / "videos"


@app.options("/videos/{name}")
def options_video(name: str):
    return Response(status_code=204, headers=_corsify_headers({}))


@app.get("/healthz")
def healthz():
    return JSONResponse({"ok": True}, headers=_corsify_headers({}))


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
        raise HTTPException(404, "not found")

    h_base = _headers_for_file(p)
    size = p.stat().st_size
    rng = request.headers.get("range")

    if rng and rng.startswith("bytes="):
        try:
            part = rng.split("=")[1]
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
