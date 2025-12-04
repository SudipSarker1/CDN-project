from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, Query, Form
from fastapi.responses import (
    HTMLResponse,
    StreamingResponse,
    RedirectResponse,
    JSONResponse,
)
import httpx
import contextlib
import json
import datetime as dt
import time
import html as html_escape

from .watch_page import render_watch_page
from .auth import router as auth_router

# URL of the controller
CTRL_BASE = "https://localhost:8443"

# Paths
BASE_DIR = Path(__file__).resolve().parents[1]
VIDEOS_DIR = BASE_DIR / "videos"
COMMENTS_FILE = BASE_DIR / "config" / "comments.json"

app = FastAPI(title="CDN Frontend")
app.include_router(auth_router)

# Alt-Svc to advertise HTTP/3 on 3443 (Frontend) and 9441/9442 (Replicas)
ALT_SVC_VALUE = 'h3=":3443"; ma=86400, h3=":9441"; ma=86400, h3=":9442"; ma=86400'


@app.middleware("http")
async def add_alt_svc_header(request: Request, call_next):
    """Attach Alt-Svc header to all responses."""
    response = await call_next(request)
    existing = response.headers.get("Alt-Svc")
    if existing:
        response.headers["Alt-Svc"] = existing + ", " + ALT_SVC_VALUE
    else:
        response.headers["Alt-Svc"] = ALT_SVC_VALUE
    return response


# ---------------------------------------------------------------------------
# Helpers: videos
# ---------------------------------------------------------------------------

def list_videos() -> List[Dict[str, str]]:
    """List .mp4 files in ./videos, oldest first."""
    if not VIDEOS_DIR.exists():
        return []

    paths = list(VIDEOS_DIR.glob("*.mp4"))
    paths.sort(key=lambda p: p.stat().st_mtime)

    videos: List[Dict[str, str]] = []
    for p in paths:
        vid_id = p.stem
        title = p.stem.replace("_", " ")
        videos.append(
            {"id": vid_id, "title": title, "filename": p.name}
        )
    return videos


# ---------------------------------------------------------------------------
# Helpers: comments
# ---------------------------------------------------------------------------

def _load_comments_data() -> Dict[str, List[Dict[str, str]]]:
    """Load the full comments JSON mapping video_id -> list[comment]."""
    if not COMMENTS_FILE.exists():
        return {}
    try:
        with COMMENTS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save_comments_data(data: Dict[str, List[Dict[str, str]]]) -> None:
    """Persist the comments mapping."""
    COMMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with COMMENTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_comments_for(video_id: str) -> List[Dict[str, str]]:
    data = _load_comments_data()
    comments = data.get(video_id, [])
    comments.sort(key=lambda c: c.get("timestamp", ""))
    return comments


def add_comment(video_id: str, author: str, text: str) -> Dict[str, str]:
    """Add a comment and return the created comment dict."""
    data = _load_comments_data()
    comments = data.setdefault(video_id, [])
    comment_id = int(time.time() * 1000)

    comment = {
        "id": comment_id,
        "author": author,
        "text": text,
        "timestamp": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    comments.append(comment)
    _save_comments_data(data)
    return comment


def delete_comment_for_user(video_id: str, comment_id: int, username: str) -> bool:
    """Delete a comment for this user and return True if something was removed."""
    data = _load_comments_data()
    comments = data.get(video_id, [])
    before = len(comments)

    filtered = [
        c
        for c in comments
        if not (c.get("id") == comment_id and c.get("author") == username)
    ]
    data[video_id] = filtered
    _save_comments_data(data)
    return len(filtered) < before


# ---------------------------------------------------------------------------
# Page rendering helpers
# ---------------------------------------------------------------------------

def _render_video_cards(videos: List[Dict[str, str]]) -> str:
    """HTML cards for the home page grid."""
    parts: List[str] = []
    for v in videos:
        parts.append(
            f"""
            <a class="video-card" href="/watch/{v['id']}">
              <video
                class="thumb"
                src="/api/videos/{v['id']}"
                preload="metadata"
                muted
              ></video>
              <div class="video-title" title="{v['title']}">
                {v['title']}
              </div>
            </a>
            """
        )
    return "\n".join(parts)


def _user_header_html(username: Optional[str]) -> str:
    """Small user/login button area shown in the top bar (right side)."""
    if username:
        safe_name = html_escape.escape(username)
        return f"""
    <div class="user-area">
      <details class="user-menu">
        <summary class="user-btn">
          <span class="user-icon">👤</span>
          <span class="user-name">{safe_name}</span>
        </summary>
        <div class="user-dropdown">
          <form class="user-form" action="/logout" method="get">
            <button type="submit" class="user-dropdown-item">Log out</button>
          </form>
        </div>
      </details>
    </div>
"""
    else:
        return """
    <div class="user-area">
      <a class="user-btn" href="/login">
        <span class="user-icon">👤</span>
        <span class="user-name">Log in</span>
      </a>
    </div>
"""


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    q: Optional[str] = Query(default=None, description="Search query"),
):
    """Home page: search bar, logo, 3 big video boxes per row."""
    all_videos = list_videos()
    query = (q or "").strip()

    if query:
        q_lower = query.lower()
        videos = [
            v for v in all_videos
            if q_lower in v["title"].lower() or q_lower in v["id"].lower()
        ]
    else:
        videos = all_videos

    video_cards_html = _render_video_cards(videos)
    username = request.cookies.get("username")
    user_html = _user_header_html(username)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>CDN Frontend – Home</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0f0f0f;
      --bg-elevated: #181818;
      --text: #f9fafb;
      --muted: #9ca3af;
      --accent: #ef4444;
      --border: #27272a;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont,
                   "Segoe UI", sans-serif;
      background-color: var(--bg);
      color: var(--text);
    }}

    a {{ color: inherit; text-decoration: none; }}

    .top-bar {{
      position: sticky;
      top: 0;
      z-index: 50;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 22px;
      padding: 18px 36px;
      background: linear-gradient(to bottom, #000000ee, #000000cc 45%, #0000);
      backdrop-filter: blur(20px);
    }}

    .logo {{
      position: absolute;
      left: 32px;
      display: flex;
      align-items: center;
      gap: 12px;
      text-transform: none;
      font-family: "Trebuchet MS", "Segoe UI Semibold", "Segoe UI",
                   system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    }}

    .logo-badge {{
      width: 52px;
      height: 40px;
      border-radius: 12px;
      background: #ffffff;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow:
        0 0 0 1px rgba(148, 163, 184, 0.3),
        0 12px 24px rgba(0, 0, 0, 0.75);
      overflow: hidden;
    }}

    .logo-cdn {{
      font-size: 1.25rem;
      font-weight: 900;
      letter-spacing: 0.08em;
      color: #ef4444;
    }}

    .logo-text {{
      display: flex;
      align-items: baseline;
      gap: 3px;
      letter-spacing: 0.09em;
    }}

    .logo-main {{
      font-size: 1.18rem;
      font-weight: 700;
      text-transform: lowercase;
      color: #e5e7eb;
    }}

    .logo-sub {{
      font-size: 1.35rem;
      font-weight: 800;
      text-transform: uppercase;
      color: #f9fafb;
    }}

    .search-form {{
      display: flex;
      align-items: center;
      max-width: 900px;
      width: 100%;
      gap: 12px;
    }}

    .search-input {{
      flex: 1;
      padding: 12px 18px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background-color: #020617;
      color: var(--text);
      font-size: 1.05rem;
      outline: none;
    }}

    .search-input::placeholder {{ color: var(--muted); }}

    .search-input:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.35);
    }}

    .search-btn {{
      border-radius: 999px;
      border: 1px solid var(--border);
      background: #18181b;
      color: var(--text);
      padding: 11px 24px;
      font-size: 1rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .search-btn:hover {{ background: #27272f; }}

    .user-area {{
      position: absolute;
      right: 32px;
      display: flex;
      align-items: center;
    }}

    .user-form {{
      margin: 0;
    }}

    .user-btn {{
      padding: 9px 22px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: #111827;
      color: var(--text);
      font-size: 0.95rem;
      font-weight: 500;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }}

    .user-btn:hover {{
      background: #1f2937;
    }}

    .user-menu {{
      position: relative;
    }}

    .user-menu > summary {{
      list-style: none;
      cursor: pointer;
    }}

    .user-menu > summary::-webkit-details-marker {{
      display: none;
    }}

    .user-icon {{
      font-size: 1rem;
    }}

    .user-name {{
      font-size: 1.05rem;
      font-weight: 600;
    }}

    .user-dropdown {{
      position: absolute;
      right: 0;
      margin-top: 6px;
      padding: 6px;
      background: #020617;
      border-radius: 12px;
      border: 1px solid #1f2937;
      min-width: 120px;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.75);
    }}

    .user-dropdown-item {{
      width: 100%;
      padding: 6px 10px;
      border-radius: 8px;
      border: none;
      background: transparent;
      color: #f9fafb;
      text-align: left;
      font-size: 0.9rem;
      cursor: pointer;
    }}

    .user-dropdown-item:hover {{
      background: #111827;
    }}

    main {{
      padding: 18px 40px 40px;
      max-width: 1600px;
      margin: 0 auto;
    }}

    .section-header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 16px;
      margin-top: 4px;
      gap: 12px;
    }}

    .section-title {{
      font-size: 1.35rem;
      font-weight: 750;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #e5e7eb;
      border-bottom: 2px solid #27272a;
      padding-bottom: 4px;
    }}

    .section-sub {{
      font-size: 1.0rem;
      font-weight: 600;
      color: var(--muted);
    }}

    .video-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 26px 26px;
    }}

    @media (max-width: 1280px) {{
      .video-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}

    @media (max-width: 800px) {{
      .video-grid {{
        grid-template-columns: repeat(1, minmax(0, 1fr));
      }}
    }}

    .video-card {{
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}

    .thumb {{
      width: 100%;
      aspect-ratio: 16 / 9;
      border-radius: 18px;
      background-color: #000000;
      object-fit: cover;
      display: block;
      box-shadow: 0 18px 40px rgba(0, 0, 0, 0.8);
    }}

    .video-title {{
      font-size: 1.15rem;
      font-weight: 500;
      line-height: 1.35;
    }}

    .empty {{
      margin-top: 40px;
      text-align: center;
      color: var(--muted);
      font-size: 0.9rem;
    }}

    @media (max-width: 640px) {{
      .logo {{ display: none; }}
      main {{ padding-inline: 12px; }}
    }}
  </style>
</head>
<body>
  <header class="top-bar">
    <a href="/" class="logo">
      <div class="logo-badge">
        <span class="logo-cdn">CDN</span>
      </div>
      <div class="logo-text">
        <span class="logo-main">mini</span><span class="logo-sub">TUBE</span>
      </div>
    </a>
    <form class="search-form" action="/" method="get">
      <input
        class="search-input"
        type="text"
        name="q"
        placeholder="Search videos"
        value="{query}"
        autocomplete="off"
      />
      <button class="search-btn" type="submit">
        🔍 <span>Search</span>
      </button>
    </form>
    {user_html}
  </header>

  <main>
    <div class="section-header">
      <div class="section-title">All videos</div>
      <div class="section-sub">
        {len(videos)} video(s){' · filtered' if query else ''}
      </div>
    </div>

    {("<div class='video-grid'>" + video_cards_html + "</div>") if videos else "<div class='empty'>No videos found. Put some .mp4 files in the project 'videos' folder.</div>"}
  </main>
</body>
</html>
"""
    return HTMLResponse(content=html)


@app.get("/watch/{video_id}", response_class=HTMLResponse)
async def watch(video_id: str, request: Request):
    """Watch page: delegate HTML rendering to watch_page module."""
    all_videos = list_videos()
    current = next((v for v in all_videos if v["id"] == video_id), None)
    if current is None:
        raise HTTPException(status_code=404, detail="Video not found")

    others = [v for v in all_videos if v["id"] != video_id]
    comments = get_comments_for(video_id)
    username = request.cookies.get("username")
    return render_watch_page(current, others, comments, current_user=username)


@app.post("/watch/{video_id}/comment")
async def post_comment(
    video_id: str,
    request: Request,
    text: str = Form(...),
):
    """Handle comment form submission, save to JSON, then redirect back.

    Kept for non-JS browsers; JS uses /api/watch/{video_id}/comment.
    """
    text = (text or "").strip()
    if not text:
        return RedirectResponse(url=f"/watch/{video_id}", status_code=303)

    username = request.cookies.get("username")
    if not username:
        # must be logged in to comment
        return RedirectResponse(
            url=f"/login?next=/watch/{video_id}",
            status_code=303,
        )

    add_comment(video_id, username, text)
    return RedirectResponse(url=f"/watch/{video_id}", status_code=303)


@app.post("/api/watch/{video_id}/comment")
async def api_post_comment(
    video_id: str,
    request: Request,
    text: str = Form(...),
):
    """AJAX comment endpoint – returns JSON so the page doesn't reload."""
    text = (text or "").strip()
    if not text:
        return JSONResponse({"error": "empty"}, status_code=400)

    username = request.cookies.get("username")
    if not username:
        return JSONResponse(
            {"error": "unauthenticated", "redirect": f"/login?next=/watch/{video_id}"},
            status_code=401,
        )

    comment = add_comment(video_id, username, text)

    ts_raw = comment.get("timestamp", "")
    date_part = ts_raw
    time_part = ""
    if "T" in ts_raw:
        d, t = ts_raw.split("T", 1)
        date_part = d
        time_part = t.rstrip("Z")

    return JSONResponse(
        {
            "id": comment["id"],
            "author": username,
            "text": comment["text"],
            "date": date_part,
            "time": time_part,
        }
    )


@app.post("/watch/{video_id}/comment/{comment_id}/delete")
async def delete_comment(
    video_id: str,
    comment_id: int,
    request: Request,
):
    """Delete a comment if it belongs to the logged-in user (HTML fallback)."""
    username = request.cookies.get("username")
    if not username:
        return RedirectResponse(
            url=f"/login?next=/watch/{video_id}",
            status_code=303,
        )

    delete_comment_for_user(video_id, comment_id, username)
    return RedirectResponse(url=f"/watch/{video_id}", status_code=303)


@app.post("/api/watch/{video_id}/comment/{comment_id}/delete")
async def api_delete_comment(
    video_id: str,
    comment_id: int,
    request: Request,
):
    """AJAX delete endpoint – returns JSON, no redirect."""
    username = request.cookies.get("username")
    if not username:
        return JSONResponse(
            {"error": "unauthenticated", "redirect": f"/login?next=/watch/{video_id}"},
            status_code=401,
        )

    ok = delete_comment_for_user(video_id, comment_id, username)
    return JSONResponse({"ok": ok})


@app.get("/play", response_class=RedirectResponse)
async def legacy_play(id: str = Query(..., description="Video ID (without .mp4)")):
    """Backwards-compatible route: /play?id=sample -> /watch/sample"""
    return RedirectResponse(url=f"/watch/{id}", status_code=307)


@app.get("/api/videos/{video_id}")
async def api_video(video_id: str, request: Request):
    """Proxy endpoint used by <video> tags.

    It asks the controller for the selected replica. If the controller
    responds with a redirect, we forward that redirect so the browser
    fetches directly from the replica. Otherwise, we stream the data
    through this frontend.
    """
    forward_headers = {}
    rng = request.headers.get("range")
    if rng:
        forward_headers["Range"] = rng

    timeout = httpx.Timeout(connect=10.0, read=120.0, write=120.0, pool=None)

    try:
        async with httpx.AsyncClient(
            verify=False, timeout=timeout, http2=True, follow_redirects=False
        ) as client:
            ctrl_resp = await client.get(
                f"{CTRL_BASE}/videos/{video_id}",
                headers=forward_headers,
            )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"error contacting controller: {e!s}")

    if ctrl_resp.status_code in (301, 302, 303, 307, 308):
        location = ctrl_resp.headers.get("location")
        if not location:
            raise HTTPException(status_code=502, detail="controller redirect missing Location header")
        return RedirectResponse(url=location, status_code=ctrl_resp.status_code)

    headers = {
        "Content-Type": ctrl_resp.headers.get("content-type", "video/mp4"),
    }
    for h in (
        "Content-Length",
        "Accept-Ranges",
        "Content-Range",
        "ETag",
        "Last-Modified",
        "Cache-Control",
    ):
        if h in ctrl_resp.headers:
            headers[h] = ctrl_resp.headers[h]

    async def stream_body():
        with contextlib.aclosing(ctrl_resp):
            async for chunk in ctrl_resp.aiter_bytes():
                yield chunk

    return StreamingResponse(
        stream_body(),
        status_code=ctrl_resp.status_code,
        headers=headers,
    )


@app.get("/healthz", response_class=JSONResponse)
async def healthz():
    """Simple health endpoint."""
    return JSONResponse({"status": "ok", "videos": len(list_videos())})
