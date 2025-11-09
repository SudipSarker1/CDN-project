from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
import os, pathlib, re

VIDEOS_DIR = pathlib.Path("videos")
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Replica")

# ... your /upload stays the same ...

@app.get("/videos/{video_id}")
def get_video(video_id: str, request: Request):
    path = VIDEOS_DIR / f"{video_id}.mp4"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    def file_iterator(start: int, end: int, chunk_size: int = 1024 * 1024):
        with path.open("rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    # If no Range header -> return whole file (200)
    if not range_header:
        headers = {
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
            "Content-Type": "video/mp4",
        }
        return StreamingResponse(file_iterator(0, file_size - 1), headers=headers, media_type="video/mp4")

    # Parse Range: bytes=start-end
    m = re.match(r"bytes=(\d*)-(\d*)", range_header)
    if not m:
        # invalid range -> respond with 416
        raise HTTPException(status_code=416, detail="Invalid Range header")

    start_str, end_str = m.groups()
    if start_str == "":
        # suffix range: bytes=-N
        length = int(end_str)
        if length <= 0:
            raise HTTPException(status_code=416, detail="Invalid Range")
        start = max(file_size - length, 0)
        end = file_size - 1
    else:
        start = int(start_str)
        end = int(end_str) if end_str else file_size - 1

    if start > end or start >= file_size:
        raise HTTPException(status_code=416, detail="Requested Range Not Satisfiable")

    content_length = end - start + 1
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": "video/mp4",
    }
    return StreamingResponse(
        file_iterator(start, end),
        status_code=206,
        headers=headers,
        media_type="video/mp4",
    )
