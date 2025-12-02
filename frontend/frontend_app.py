# frontend/frontend_app.py
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import (
    HTMLResponse,
    StreamingResponse,
    RedirectResponse,
    JSONResponse,
)
import httpx
import contextlib

# Controller base URL – right now we talk directly to uvicorn on 9000
CTRL_BASE = "http://127.0.0.1:9000"  # controller

app = FastAPI(title="CDN Frontend")

# Optional: advertise HTTP/3 on some future port (for your report / demo)
@app.middleware("http")
async def add_alt_svc(request: Request, call_next):
    response = await call_next(request)
    # later if you serve frontend over h3 (e.g. 3000) you can adjust this
    response.headers["Alt-Svc"] = 'h3=":3000"; ma=86400'
    return response


HOME_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Content Delivery Network Demo</title>
  <style>
    :root {
      color-scheme: dark;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      padding: 24px 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #020617;
      color: #e5e7eb;
      display: flex;
      min-height: 100vh;
      align-items: flex-start;
      justify-content: center;
      overflow-y: auto;
    }

    .page-title {
      text-align: center;
      width: 100%;
      margin: 0 0 18px;
      font-size: 1.8rem;
      font-weight: 700;
    }

    .window {
      position: relative;
      width: min(960px, 100% - 32px);
      background: #020617;
      border-radius: 16px;
      border: 1px solid #1f2937;
      box-shadow: 0 18px 40px rgba(0,0,0,0.65);
      overflow: hidden;
      display: flex;
      flex-direction: column;
      transition: all 0.25s ease;
    }

    /* Minimized state */
    .window.window-minimized {
      width: 260px;
      max-height: 52px;
      position: fixed;
      bottom: 16px;
      right: 16px;
      cursor: pointer;
    }

    .window.window-minimized .window-body {
      display: none;
    }

    .window-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 14px;
      background: linear-gradient(90deg, #0b1120, #020617);
      border-bottom: 1px solid #1f2937;
    }

    .window-title {
      font-size: 0.9rem;
      font-weight: 500;
      color: #d1d5db;
    }

    .window-controls {
      display: flex;
      gap: 6px;
    }

    .ctrl-btn {
      width: 20px;
      height: 20px;
      border-radius: 999px;
      border: none;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
      background: #111827;
      color: #e5e7eb;
      transition: background 0.15s ease, transform 0.1s ease;
    }

    .ctrl-btn:hover {
      background: #1f2937;
      transform: translateY(-1px);
    }

    .window-body {
      padding: 16px 18px 18px;
    }

    h1 {
      font-size: 1.5rem;
      margin: 0 0 4px;
    }

    .grid {
      display: grid;
      grid-template-columns: 1fr; /* single column */
      gap: 16px;
      align-items: flex-start;
      margin-top: 4px;
    }

    .card {
      border-radius: 14px;
      padding: 14px 16px;
      background: radial-gradient(circle at top left, #111827, #020617);
      border: 1px solid #111827;
    }

    label {
      display: block;
      font-size: 0.85rem;
      margin-bottom: 6px;
    }

    input[type="text"] {
      width: 100%;
      border-radius: 999px;
      border: 1px solid #374151;
      padding: 9px 13px;
      background: rgba(15,23,42,0.9);
      color: #f9fafb;
      outline: none;
      font-size: 0.9rem;
    }

    input[type="text"]:focus {
      border-color: #38bdf8;
      box-shadow: 0 0 0 1px #0ea5e9;
    }

    button.primary {
      margin-top: 10px;
      border-radius: 999px;
      border: none;
      padding: 8px 16px;
      background: linear-gradient(135deg, #22c55e, #14b8a6);
      color: white;
      font-weight: 600;
      cursor: pointer;
      font-size: 0.9rem;
    }

    button.primary:hover {
      filter: brightness(1.05);
    }

    .samples {
      margin-top: 10px;
      font-size: 0.85rem;
      color: #9ca3af;
    }

    .samples a {
      display: inline-block;
      margin-right: 8px;
      margin-top: 4px;
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid #374151;
      color: #e5e7eb;
      text-decoration: none;
    }

    .samples a:hover {
      border-color: #38bdf8;
    }

    footer {
      margin-top: 14px;
      font-size: 0.75rem;
      color: #6b7280;
      text-align: right;
    }

    /* --- YouTube-style video grid --- */
    .videos-section {
      margin-top: 22px;
    }

    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 10px;
      gap: 8px;
    }

    .section-title {
      font-size: 1rem;
      font-weight: 600;
    }

    .section-subtitle {
      font-size: 0.8rem;
      color: #9ca3af;
    }

    .video-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }

    @media (max-width: 900px) {
      .video-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    @media (max-width: 640px) {
      .grid {
        grid-template-columns: 1fr;
      }
      .video-grid {
        grid-template-columns: 1fr;
      }
    }

    .video-card {
      text-decoration: none;
      color: inherit;
      display: block;
      font-size: 0.85rem;
    }

    .video-thumb {
      position: relative;
      width: 100%;
      aspect-ratio: 16 / 9;
      border-radius: 12px;
      overflow: hidden;
      background: radial-gradient(circle at top left, #1d4ed8, #22c55e);
      display: flex;
      align-items: flex-end;
      padding: 8px 10px;
    }

    .video-thumb-label {
      font-size: 0.8rem;
      font-weight: 600;
      text-shadow: 0 2px 8px rgba(0,0,0,0.7);
    }

    .video-info {
      margin-top: 6px;
    }

    .video-title {
      font-weight: 600;
      margin-bottom: 2px;
    }

    .video-meta {
      font-size: 0.75rem;
      color: #9ca3af;
    }
  </style>
</head>
<body>
  <div id="cdn-window" class="window">
    <div class="window-header" id="window-header">
      <div class="window-title">CDN Demo · Origin → Controller → Replicas</div>
      <div class="window-controls">
        <button class="ctrl-btn" id="min-btn" title="Minimize">–</button>
        <button class="ctrl-btn" id="full-btn" title="Full screen">□</button>
      </div>
    </div>

    <div class="window-body">
      <h1 class="page-title">Content Delivery Network Demo</h1>

      <div class="grid">
        <section class="card">
          <form action="/play" method="get">
            <label for="id">Video ID (without <code>.mp4</code>)</label>
            <input id="id" name="id" type="text" placeholder="e.g. sample or Sunset" required />
            <button class="primary" type="submit">Play video</button>
          </form>
          <div class="samples">
            Quick links:
            <a href="/play?id=sample1">sample1</a>
            <a href="/play?id=sample2">sample2</a>
          </div>
        </section>
      </div>

      <!-- YouTube-style video grid -->
      <section class="videos-section">
        <div class="section-header">
          <div class="section-title">Videos</div>
          <div class="section-subtitle">Click a card to play via your CDN.</div>
        </div>
        <div class="video-grid">
          <!-- Row 1 -->
          <a class="video-card" href="/play?id=sample1">
            <div class="video-thumb">
              <div class="video-thumb-label">sample1.mp4</div>
            </div>
            <div class="video-info">
              <div class="video-title">Sample 1</div>
              <div class="video-meta">Demo clip · ~10 MB</div>
            </div>
          </a>

          <a class="video-card" href="/play?id=sample2">
            <div class="video-thumb" style="background: radial-gradient(circle at top left,#ec4899,#f97316);">
              <div class="video-thumb-label">sample2.mp4</div>
            </div>
            <div class="video-info">
              <div class="video-title">Sample 2</div>
              <div class="video-meta">Demo clip · ~15 MB</div>
            </div>
          </a>

          <a class="video-card" href="/play?id=sample3">
            <div class="video-thumb" style="background: radial-gradient(circle at top left,#22c55e,#0ea5e9);">
              <div class="video-thumb-label">sample3.mp4</div>
            </div>
            <div class="video-info">
              <div class="video-title">Sample 3</div>
              <div class="video-meta">Demo clip · ~20 MB</div>
            </div>
          </a>

          <!-- Row 2 -->
          <a class="video-card" href="/play?id=sample4">
            <div class="video-thumb" style="background: radial-gradient(circle at top left,#6366f1,#22c55e);">
              <div class="video-thumb-label">sample4.mp4</div>
            </div>
            <div class="video-info">
              <div class="video-title">Sample 4</div>
              <div class="video-meta">Demo clip · ~25 MB</div>
            </div>
          </a>

          <a class="video-card" href="/play?id=sample5">
            <div class="video-thumb" style="background: radial-gradient(circle at top left,#f97316,#22c55e);">
              <div class="video-thumb-label">sample5.mp4</div>
            </div>
            <div class="video-info">
              <div class="video-title">Sample 5</div>
              <div class="video-meta">Demo clip · ~30 MB</div>
            </div>
          </a>

          <a class="video-card" href="/play?id=sample6">
            <div class="video-thumb" style="background: radial-gradient(circle at top left,#0ea5e9,#ec4899);">
              <div class="video-thumb-label">sample6.mp4</div>
            </div>
            <div class="video-info">
              <div class="video-title">Sample 6</div>
              <div class="video-meta">Demo clip · ~35 MB</div>
            </div>
          </a>
        </div>
      </section>

      <footer>
        COEN 6861 · Student CDN prototype
      </footer>
    </div>
  </div>

  <script>
    // Minimize / full-screen behavior
    const win = document.getElementById("cdn-window");
    const header = document.getElementById("window-header");
    const minBtn = document.getElementById("min-btn");
    const fullBtn = document.getElementById("full-btn");

    let isMinimized = false;
    let isFull = false;

    function applyState() {
      if (isMinimized) {
        win.classList.add("window-minimized");
      } else {
        win.classList.remove("window-minimized");
      }

      if (isFull) {
        document.body.style.alignItems = "stretch";
        document.body.style.justifyContent = "stretch";
        win.style.width = "100%";
        win.style.borderRadius = "0";
      } else {
        document.body.style.alignItems = "flex-start";
        document.body.style.justifyContent = "center";
        win.style.width = "min(960px, 100% - 32px)";
        win.style.borderRadius = "16px";
      }
    }

    minBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      isMinimized = !isMinimized;
      applyState();
    });

    fullBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      isFull = !isFull;
      applyState();
    });

    // When minimized, clicking the header restores the window
    header.addEventListener("click", () => {
      if (isMinimized) {
        isMinimized = false;
        applyState();
      }
    });

    applyState();
  </script>
</body>
</html>
"""


def play_page(video_id: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{video_id} · CDN Demo</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
      padding: 0;
      background: #020617;
      color: #f9fafb;
      display: flex;
      min-height: 100vh;
      align-items: flex-start;
      justify-content: center;
      overflow-y: auto;  /* allow vertical scrolling */
    }}
    .page {{
      width: min(1360px, 100% - 32px);
      margin: 20px auto 32px;
    }}
    a {{
      color: #38bdf8;
      text-decoration: none;
      font-size: 0.9rem;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .back-link {{
      margin-bottom: 16px;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 3.8fr) minmax(260px, 1.2fr);  /* bigger main, slimmer sidebar */
      gap: 22px;
    }}
    @media (max-width: 900px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
    }}
    .main-card {{
      border-radius: 20px;
      padding: 18px 22px 24px;
      background: radial-gradient(circle at top left, #020617, #020617);
      box-shadow: 0 22px 50px rgba(0,0,0,0.65);
      border: 1px solid #111827;
    }}
    .video-wrapper {{
      position: relative;
      width: 100%;
      border-radius: 18px;
      overflow: hidden;
      background: #000;
    }}
    video {{
      width: 100%;
      height: auto;
      max-height: 80vh;
      display: block;
      background: #000;
    }}
    .fs-btn {{
      margin-top: 12px;
      border-radius: 999px;
      border: none;
      padding: 8px 18px;
      background: rgba(15,23,42,0.9);
      color: #e5e7eb;
      font-size: 0.85rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid #374151;
    }}
    .fs-btn:hover {{
      background: #111827;
    }}
    .title-block {{
      margin-top: 18px;
    }}
    .title-block h1 {{
      margin: 0 0 6px;
      font-size: 1.4rem;
      font-weight: 600;
    }}
    .title-meta {{
      font-size: 0.85rem;
      color: #9ca3af;
    }}
    .side-card {{
      border-radius: 20px;
      padding: 14px 16px;
      background: radial-gradient(circle at top left,#020617,#020617);
      border: 1px solid #111827;
      font-size: 0.9rem;
      box-shadow: 0 18px 42px rgba(0,0,0,0.6);
      max-height: 80vh;
      overflow-y: auto;  /* sidebar itself scrolls if list grows */
    }}
    .side-heading {{
      font-size: 1rem;
      font-weight: 600;
      margin-bottom: 10px;
    }}
    .upnext-list {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .upnext-item a {{
      display: flex;
      gap: 10px;
      align-items: center;
      color: inherit;
      text-decoration: none;
      padding: 6px 4px;
      border-radius: 10px;
    }}
    .upnext-item a:hover {{
      background: rgba(15,23,42,0.9);
    }}
    .upnext-thumb {{
      width: 120px;
      height: 72px;
      border-radius: 10px;
      background: radial-gradient(circle at top left,#1d4ed8,#22c55e);
      font-size: 0.75rem;
      display: flex;
      align-items: flex-end;
      justify-content: center;
      padding-bottom: 4px;
    }}
    .upnext-info-title {{
      font-size: 0.9rem;
      font-weight: 500;
      margin-bottom: 2px;
    }}
    .upnext-info-meta {{
      font-size: 0.8rem;
      color: #9ca3af;
    }}
    footer {{
      margin-top: 24px;
      font-size: 0.75rem;
      color: #6b7280;
      text-align: right;
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="back-link">
      <a href="/">&larr; Back to home</a>
    </div>

    <div class="layout">
      <!-- Main player column -->
      <div class="main-card">
        <div class="video-wrapper">
          <video id="player" controls preload="metadata" src="/api/videos/{video_id}"></video>
        </div>
        <button id="fullscreen-btn" class="fs-btn" type="button">
          <span>⤢</span>
          <span>Full screen</span>
        </button>

        <div class="title-block">
          <h1>Playing: {video_id}</h1>
          <div class="title-meta">
            Routed via CDN controller · Demo player
          </div>
        </div>
      </div>

      <!-- Right column: "Up next" sidebar -->
      <aside class="side-card">
        <div class="side-heading">Up next</div>
        <ul class="upnext-list">
          <li class="upnext-item">
            <a href="/play?id=sample1">
              <div class="upnext-thumb">sample1</div>
              <div>
                <div class="upnext-info-title">Sample 1</div>
                <div class="upnext-info-meta">Demo · ~10 MB</div>
              </div>
            </a>
          </li>
          <li class="upnext-item">
            <a href="/play?id=sample2">
              <div class="upnext-thumb" style="background: radial-gradient(circle at top left,#ec4899,#f97316);">sample2</div>
              <div>
                <div class="upnext-info-title">Sample 2</div>
                <div class="upnext-info-meta">Demo · ~15 MB</div>
              </div>
            </a>
          </li>
          <li class="upnext-item">
            <a href="/play?id=sample3">
              <div class="upnext-thumb" style="background: radial-gradient(circle at top left,#22c55e,#0ea5e9);">sample3</div>
              <div>
                <div class="upnext-info-title">Sample 3</div>
                <div class="upnext-info-meta">Demo · ~20 MB</div>
              </div>
            </a>
          </li>
          <li class="upnext-item">
            <a href="/play?id=sample4">
              <div class="upnext-thumb" style="background: radial-gradient(circle at top left,#6366f1,#22c55e);">sample4</div>
              <div>
                <div class="upnext-info-title">Sample 4</div>
                <div class="upnext-info-meta">Demo · ~25 MB</div>
              </div>
            </a>
          </li>
        </ul>
      </aside>
    </div>

    <footer>
      COEN 6861 · Content Delivery Network demo
    </footer>
  </div>

  <script>
    // Custom fullscreen toggle (in addition to the browser's own control)
    const video = document.getElementById("player");
    const fsBtn = document.getElementById("fullscreen-btn");

    fsBtn.addEventListener("click", () => {{
      if (!document.fullscreenElement) {{
        if (video.requestFullscreen) {{
          video.requestFullscreen();
        }}
      }} else {{
        if (document.exitFullscreen) {{
          document.exitFullscreen();
        }}
      }}
    }});
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return HOME_HTML


@app.get("/play", response_class=HTMLResponse)
def play(id: str):
    def play_page(video_id: str) -> str:
        return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <title>{video_id} · CDN Demo</title>
      <style>
        body {{
          font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          margin: 0;
          padding: 0;
          background: #020617;
          color: #f9fafb;
          display: flex;
          min-height: 100vh;
          align-items: flex-start;
          justify-content: center;
        }}
        .page {{
          width: min(1280px, 100% - 32px);
          margin: 20px auto 32px;
        }}
        a {{
          color: #38bdf8;
          text-decoration: none;
          font-size: 0.9rem;
        }}
        a:hover {{
          text-decoration: underline;
        }}
        .back-link {{
          margin-bottom: 14px;
        }}
        .layout {{
          display: grid;
          grid-template-columns: minmax(0, 3.3fr) minmax(280px, 1.3fr);
          gap: 20px;
        }}
        @media (max-width: 900px) {{
          .layout {{
            grid-template-columns: 1fr;
          }}
        }}
        .main-card {{
          border-radius: 18px;
          padding: 18px 20px 22px;
          background: radial-gradient(circle at top left, #020617, #020617);
          box-shadow: 0 20px 45px rgba(0,0,0,0.6);
          border: 1px solid #111827;
        }}
        .video-wrapper {{
          position: relative;
          width: 100%;
          border-radius: 16px;
          overflow: hidden;
          background: #000;
        }}
        video {{
          width: 100%;
          height: auto;
          max-height: 78vh;
          display: block;
          background: #000;
        }}
        .fs-btn {{
          margin-top: 10px;
          border-radius: 999px;
          border: none;
          padding: 8px 16px;
          background: rgba(15,23,42,0.9);
          color: #e5e7eb;
          font-size: 0.85rem;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 8px;
          border: 1px solid #374151;
        }}
        .fs-btn:hover {{
          background: #111827;
        }}
        .title-block {{
          margin-top: 16px;
        }}
        .title-block h1 {{
          margin: 0 0 6px;
          font-size: 1.35rem;
          font-weight: 600;
        }}
        .title-meta {{
          font-size: 0.85rem;
          color: #9ca3af;
        }}
        .side-card {{
          border-radius: 18px;
          padding: 14px 16px;
          background: radial-gradient(circle at top left,#020617,#020617);
          border: 1px solid #111827;
          font-size: 0.9rem;
          box-shadow: 0 16px 38px rgba(0,0,0,0.55);
        }}
        .side-heading {{
          font-size: 1rem;
          font-weight: 600;
          margin-bottom: 10px;
        }}
        .upnext-list {{
          list-style: none;
          padding: 0;
          margin: 0;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }}
        .upnext-item a {{
          display: flex;
          gap: 10px;
          align-items: center;
          color: inherit;
          text-decoration: none;
          padding: 6px 4px;
          border-radius: 10px;
        }}
        .upnext-item a:hover {{
          background: rgba(15,23,42,0.9);
        }}
        .upnext-thumb {{
          width: 115px;
          height: 68px;
          border-radius: 10px;
          background: radial-gradient(circle at top left,#1d4ed8,#22c55e);
          font-size: 0.75rem;
          display: flex;
          align-items: flex-end;
          justify-content: center;
          padding-bottom: 4px;
        }}
        .upnext-info-title {{
          font-size: 0.9rem;
          font-weight: 500;
          margin-bottom: 2px;
        }}
        .upnext-info-meta {{
          font-size: 0.8rem;
          color: #9ca3af;
        }}
        footer {{
          margin-top: 22px;
          font-size: 0.75rem;
          color: #6b7280;
          text-align: right;
        }}
      </style>
    </head>
    <body>
      <div class="page">
        <div class="back-link">
          <a href="/">&larr; Back to home</a>
        </div>

        <div class="layout">
          <!-- Main player column -->
          <div class="main-card">
            <div class="video-wrapper">
              <video id="player" controls preload="metadata" src="/api/videos/{video_id}"></video>
            </div>
            <button id="fullscreen-btn" class="fs-btn" type="button">
              <span>⤢</span>
              <span>Full screen</span>
            </button>

            <div class="title-block">
              <h1>Playing: {video_id}</h1>
              <div class="title-meta">
                Routed via CDN controller · Demo player
              </div>
            </div>
          </div>

          <!-- Right column: simple "Up next" list -->
          <aside class="side-card">
            <div class="side-heading">Up next</div>
            <ul class="upnext-list">
              <li class="upnext-item">
                <a href="/play?id=sample1">
                  <div class="upnext-thumb">sample1</div>
                  <div>
                    <div class="upnext-info-title">Sample 1</div>
                    <div class="upnext-info-meta">Demo · ~10 MB</div>
                  </div>
                </a>
              </li>
              <li class="upnext-item">
                <a href="/play?id=sample2">
                  <div class="upnext-thumb" style="background: radial-gradient(circle at top left,#ec4899,#f97316);">sample2</div>
                  <div>
                    <div class="upnext-info-title">Sample 2</div>
                    <div class="upnext-info-meta">Demo · ~15 MB</div>
                  </div>
                </a>
              </li>
              <li class="upnext-item">
                <a href="/play?id=sample3">
                  <div class="upnext-thumb" style="background: radial-gradient(circle at top left,#22c55e,#0ea5e9);">sample3</div>
                  <div>
                    <div class="upnext-info-title">Sample 3</div>
                    <div class="upnext-info-meta">Demo · ~20 MB</div>
                  </div>
                </a>
              </li>
              <li class="upnext-item">
                <a href="/play?id=sample4">
                  <div class="upnext-thumb" style="background: radial-gradient(circle at top left,#6366f1,#22c55e);">sample4</div>
                  <div>
                    <div class="upnext-info-title">Sample 4</div>
                    <div class="upnext-info-meta">Demo · ~25 MB</div>
                  </div>
                </a>
              </li>
            </ul>
          </aside>
        </div>

        <footer>
          COEN 6861 · Content Delivery Network demo
        </footer>
      </div>

      <script>
        // Custom fullscreen toggle (in addition to the browser's own control)
        const video = document.getElementById("player");
        const fsBtn = document.getElementById("fullscreen-btn");

        fsBtn.addEventListener("click", () => {{
          if (!document.fullscreenElement) {{
            if (video.requestFullscreen) {{
              video.requestFullscreen();
            }}
          }} else {{
            if (document.exitFullscreen) {{
              document.exitFullscreen();
            }}
          }}
        }});
      </script>
    </body>
    </html>
    """

    return play_page(id)


@app.get("/meta")
async def meta():
    """
    Helper for the UI: ask the controller for its configured replicas.
    """
    try:
        async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
            res = await client.get(f"{CTRL_BASE}/healthz")
            data = res.json()
    except Exception as e:
        return {"controller": CTRL_BASE, "replicas": [], "error": str(e)}
    return {
        "controller": CTRL_BASE,
        "replicas": data.get("replicas", []),
    }


@app.get("/api/videos/{video_id}")
async def api_video(request: Request, video_id: str):
    """
    Ask controller. If it replies 302 -> forward that 302 to the browser (best path).
    If not, resolve the final URL ourselves and stream from the controller (fallback path).
    """
    ctrl_url = f"{CTRL_BASE}/videos/{video_id}"

    # forward key headers
    fwd_headers = {}
    for h in ("range", "if-none-match", "if-modified-since", "accept"):
        v = request.headers.get(h)
        if v:
            fwd_headers[h] = v

    try:
        async with httpx.AsyncClient(verify=False, timeout=None) as client:
            # 1) Hit controller WITHOUT following redirects so we can detect 302
            head = await client.get(
                ctrl_url, headers=fwd_headers, follow_redirects=False
            )
            if head.status_code in (301, 302, 303, 307, 308):
                loc = head.headers.get("location")
                if not loc:
                    return JSONResponse(
                        {"error": "controller sent redirect with no Location"},
                        status_code=502,
                    )
                # Let the browser follow the redirect to replica
                return RedirectResponse(url=loc, status_code=head.status_code)

            if head.status_code in (200, 206, 304):
                # 2) Controller is serving directly — stream it
                async with client.stream("GET", ctrl_url, headers=fwd_headers) as r:
                    if r.status_code not in (200, 206, 304):
                        err = ""
                        with contextlib.suppress(Exception):
                            raw = await r.aread()
                            err = raw.decode("utf-8", "ignore")[:400]
                        raise HTTPException(
                            status_code=502,
                            detail=(
                                f"controller stream status {r.status_code}. "
                                f"{err or ''}"
                            ).strip(),
                        )

                    hop_by_hop = {
                        "connection",
                        "keep-alive",
                        "transfer-encoding",
                        "proxy-authenticate",
                        "proxy-authorization",
                        "te",
                        "trailers",
                        "upgrade",
                    }
                    passthrough = {}
                    for k, v in r.headers.items():
                        lk = k.lower()
                        if lk in hop_by_hop:
                            continue
                        if lk in {
                            "content-type",
                            "content-length",
                            "accept-ranges",
                            "content-range",
                            "etag",
                            "last-modified",
                            "cache-control",
                            "expires",
                        }:
                            passthrough[k] = v

                    return StreamingResponse(
                        r.aiter_bytes(),
                        status_code=r.status_code,
                        headers=passthrough,
                    )

            # Anything else from controller => error
            body = ""
            with contextlib.suppress(Exception):
                body = head.text[:400]
            raise HTTPException(
                status_code=502,
                detail=(
                    f"controller status {head.status_code}. "
                    f"{body if body else ''}"
                ).strip(),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"frontend proxy error: {e!s}"
        )
