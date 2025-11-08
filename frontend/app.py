# frontend/app.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
import httpx

app = FastAPI(title="Frontend")

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <h1>CDN Demo</h1>
    <form action="/play" method="get">
      <input name="id" placeholder="video id (without .mp4)" />
      <button type="submit">Play</button>
    </form>
    """

@app.get("/play", response_class=HTMLResponse)
def play(id: str):
    return f"""
    <h2>Playing: {id}</h2>
    <video width="640" controls src="/api/videos/{id}"></video>
    """

@app.get("/api/videos/{video_id}")
async def api_video(video_id: str):
    ctrl = "https://localhost:8000/videos/" + video_id
    async with httpx.AsyncClient(http2=True, verify=False, timeout=None) as client:
        r = await client.stream("GET", ctrl)
        if r.status_code != 200:
            await r.aclose()
            raise HTTPException(status_code=502, detail=f"Controller status {r.status_code}")

        headers = {}
        ct = r.headers.get("content-type")
        if ct: headers["content-type"] = ct
        cl = r.headers.get("content-length")
        if cl: headers["content-length"] = cl

        return StreamingResponse(r.aiter_bytes(), headers=headers)
