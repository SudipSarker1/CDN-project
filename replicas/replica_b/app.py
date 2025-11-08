from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.responses import FileResponse
from pathlib import Path

app = FastAPI(title="replica_b")

VIDEO_DIR = Path(__file__).parent / "videos"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

@app.post("/upload")
async def upload(file: UploadFile = File(...), video_id: str | None = Header(None, alias="video-id")):
    name = f"{video_id}.mp4" if video_id else file.filename
    target = VIDEO_DIR / name
    with target.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    await file.close()
    return {"status": "ok", "stored": str(target)}

@app.get("/videos/{name}")
def get_video(name: str):
    path = VIDEO_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="video not found")
    return FileResponse(path, media_type="video/mp4")
