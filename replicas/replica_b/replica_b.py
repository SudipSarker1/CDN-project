from __future__ import annotations

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, Response
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import os
import json
import email.utils as eut  # RFC 1123 http-date formatting

app = FastAPI(title="Replica B")

# Storage
BASE = Path(__file__).resolve().parent
VIDEOS_DIR = BASE / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# Per-file version ledger (for ETag busts)
VERSIONS_FILE = VIDEOS_DIR / ".versions.json"

# TTL in seconds
DEFAULT_TTL = 3600  # 1 hour

def _load_versions() -> dict:
    if VERSIONS_FILE.exists():
        try:
            return json.loads(VERSIONS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_versions(d: dict) -> None:
    VERSIONS_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")

def _httpdate(ts: float) -> str:
    return eut.formatdate(ts, usegmt=True)

def _resolve_path(name: str) -> Path:
    p = VIDEOS_DIR / name
    if p.suffix.lower() != ".mp4":
        p = p.with_suffix(".mp4")
    return p

def _etag_for(path: Path, extra_version: int = 0) -> str:
    st = path.stat()
    h = hashlib.md5()
    h.update(str(st.st_size).encode())
    h.update(str(st.st_mtime_ns).encode())
    h.update(str(extra_version).encode())
    return '"' + h.hexdigest() + '"'

def _headers_common(path: Path, ttl: int, extra_version: int) -> dict:
    st = path.stat()
    return {
        "Accept-Ranges": "bytes",
        "Content-Type": "video/mp4",
        "Cache-Control": f"public, max-age={ttl}",
        "Last-Modified": _httpdate(st.st_mtime),
        "ETag": _etag_for(path, extra_version),
    }

@app.get("/healthz")
def healthz():
    return {"ok": True, "replica": "B", "videos_dir": str(VIDEOS_DIR), "ttl": DEFAULT_TTL}

@app.post("/upload")
async def upload_video(request: Request, video_id: str = Header(..., alias="video-id")):
    if not video_id:
        raise HTTPException(status_code=400, detail="Missing video-id header")
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="Empty body")
    safe_id = os.path.basename(video_id)
    out_path = _resolve_path(safe_id)
    out_path.write_bytes(data)

    # Reset per-file version (mtime already changes -> new ETag)
    versions = _load_versions()
    versions.pop(out_path.name, None)
    _save_versions(versions)

    return JSONResponse({"ok": True, "saved": out_path.name}, status_code=201)

@app.post("/purge/{name}")
def purge(name: str):
    path = _resolve_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="not found")
    path.unlink()
    versions = _load_versions()
    versions.pop(path.name, None)
    _save_versions(versions)
    return {"ok": True, "purged": path.name}

@app.post("/bust/{name}")
def bust(name: str):
    path = _resolve_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="not found")
    versions = _load_versions()
    versions[path.name] = int(versions.get(path.name, 0)) + 1
    _save_versions(versions)
    return {"ok": True, "busted": path.name, "version": versions[path.name]}

@app.get("/videos/{name}")
def get_video(
    name: str,
    range: str | None = Header(None),
    if_none_match: str | None = Header(None, alias="If-None-Match"),
    if_modified_since: str | None = Header(None, alias="If-Modified-Since"),
):
    path = _resolve_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="video not found")

    versions = _load_versions()
    extra_ver = int(versions.get(path.name, 0))
    headers_common = _headers_common(path, DEFAULT_TTL, extra_ver)
    size = path.stat().st_size

    # Conditional GET (ETag preferred)
    if if_none_match:
        client_etags = [t.strip() for t in if_none_match.split(",")]
        if headers_common["ETag"] in client_etags or "*" in client_etags:
            return Response(status_code=304, headers=headers_common)

    if if_modified_since:
        try:
            ims = datetime(*eut.parsedate(if_modified_since)[:6], tzinfo=timezone.utc)
            file_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if file_dt <= ims:
                return Response(status_code=304, headers=headers_common)
        except Exception:
            pass

    # Range
    if range:
        try:
            units, rng = range.split("=")
            if units.strip().lower() != "bytes":
                raise ValueError
            start_s, end_s = (rng.split("-") + [""])[:2]
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else size - 1
        except Exception:
            raise HTTPException(status_code=416, detail="invalid range")

        start = max(0, start); end = min(size - 1, end)
        if start > end:
            raise HTTPException(status_code=416, detail="invalid range")
        length = end - start + 1

        def iter_range():
            with path.open("rb") as f:
                f.seek(start)
                remaining = length
                chunk = 64 * 1024
                while remaining > 0:
                    data = f.read(min(chunk, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        headers = {**headers_common, "Content-Range": f"bytes {start}-{end}/{size}", "Content-Length": str(length)}
        return StreamingResponse(iter_range(), status_code=206, headers=headers, media_type="video/mp4")

    # Full content
    def iter_full():
        with path.open("rb") as f:
            while True:
                data = f.read(64 * 1024)
                if not data:
                    break
                yield data

    headers = {**headers_common, "Content-Length": str(size)}
    return StreamingResponse(iter_full(), status_code=200, headers=headers, media_type="video/mp4")
