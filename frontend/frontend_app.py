# frontend/frontend_app.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from urllib.parse import quote

app = FastAPI(title="Frontend (direct-to-controller)")

# Use TLS on the controller so the browser negotiates HTTP/2 (“latest HTTP technology”).
# If you also run an HTTP dev port with --insecure-bind 8001, you can switch this to http://127.0.0.1:8001
CONTROLLER_BASE = "https://localhost:8000".rstrip("/")


@app.get("/", response_class=HTMLResponse)
def home():
    # super minimal UI
    return """
    <h1>CDN Demo</h1>
    <form action="/play" method="get">
      <input name="id" placeholder="video id (without .mp4)" />
      <button type="submit">Play</button>
    </form>
    """


@app.get("/play", response_class=HTMLResponse)
def play(id: str):
    # Encode “Wind Turbine” → Wind%20Turbine so spaces and special chars work
    safe_id = quote(id.strip(), safe="")
    video_url = f"{CONTROLLER_BASE}/videos/{safe_id}"
    # Point the <video> directly to the controller (browser → h2 → controller; controller → replicas)
    return f"""
    <h2>Playing: {id}</h2>
    <video width="640" controls preload="metadata" src="{video_url}"></video>
    <p style="font-family: monospace">src = {video_url}</p>
    """
