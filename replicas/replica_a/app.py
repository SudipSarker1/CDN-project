from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

app = FastAPI(title="replica_a")

VIDEO_DIR = Path(__file__).parent / "videos"

@app.get("/videos/{name}")
def get_video(name: str):
    path = VIDEO_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="video not found")
    return FileResponse(path)  # will serve replicas/replica_a/videos/<name>
