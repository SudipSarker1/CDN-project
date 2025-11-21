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

CTRL_BASE = "https://localhost:8000"  # controller

app = FastAPI(title="CDN Frontend")

# Alt-Svc to advertise HTTP/3 on 3000
@app.middleware("http")
async def add_alt_svc(request: Request, call_next):
    response = await call_next(request)
    response.headers["Alt-Svc"] = 'h3=":3000"; ma=86400'
    return response


HOME_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>CDN Video Demo</title>
  <style>
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
      padding: 0;
      background: #020617;
      color: #f9fafb;
    }
    .page {
      max-width: 960px;
      margin: 0 auto;
      padding: 24px 16px 40px;
    }
    header {
      margin-bottom: 24px;
    }
    h1 {
      font-size: 2rem;
      margin-bottom: 4px;
    }
    header p {
      margin: 0;
      color: #9ca3af;
      font-size: 0.95rem;
    }
    .grid {
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 16px;
      align-items: flex-start;
    }
    .card {
      border-radius: 16px;
      padding: 16px 18px;
      background: radial-gradient(circle at top left, #111827, #020617);
      box-shadow: 0 18px 40px rgba(0,0,0,0.55);
    }
    label {
      display: block;
      font-size: 0.9rem;
      margin-bottom: 6px;
    }
    input[type="text"] {
      width: 100%;
      border-radius: 999px;
      border: 1px solid #374151;
      padding: 10px 14px;
      background: rgba(15,23,42,0.85);
      color: #f9fafb;
      outline: none;
    }
    input[type="text"]:focus {
      border-color: #38bdf8;
      box-shadow: 0 0 0 1px #0ea5e9;
    }
    button {
      margin-top: 12px;
      border-radius: 999px;
      border: none;
      padding: 9px 18px;
      background: linear-gradient(135deg, #22c55e, #14b8a6);
      color: white;
      font-weight: 600;
      cursor: pointer;
    }
    button:hover {
      filter: brightness(1.05);
    }
    .samples a {
      display: inline-block;
      margin-right: 8px;
      margin-bottom: 6px;
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid #374151;
      color: #e5e7eb;
      font-size: 0.85rem;
      text-decoration: none;
    }
    .samples a:hover {
      border-color: #38bdf8;
    }
    .meta-list {
      font-size: 0.85rem;
      color: #9ca3af;
      list-style: none;
      padding-left: 0;
    }
    .meta-list li {
      margin-bottom: 4px;
    }
    footer {
      margin-top: 24px;
      font-size: 0.75rem;
      color: #6b7280;
    }
    @media (max-width: 800px) {
      .grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="page">
    <header>
      <h1>Content Delivery Network Demo</h1>
      <p>Origin → Controller → Replica servers (HTTP/3 / QUIC on the streaming path).</p>
    </header>

    <div class="grid">
      <section class="card">
        <form action="/play" method="get">
          <label for="id">Video ID (without <code>.mp4</code>)</label>
          <input id="id" name="id" type="text" placeholder="e.g. sample or Sunset" required />
          <button type="submit">Play video</button>
        </form>
        <div class="samples">
          <p style="margin-top:12px;margin-bottom:4px;font-size:0.85rem;color:#9ca3af;">Quick links:</p>
          <a href="/play?id=sample">sample</a>
          <a href="/play?id=Sunset">Sunset</a>
        </div>
      </section>

      <aside class="card">
        <h3 style="margin-top:0;font-size:1rem;">CDN status</h3>
        <ul id="cdn-meta" class="meta-list">
          <li>Loading controller &amp; replicas…</li>
        </ul>
        <p style="margin-top:10px;font-size:0.8rem;">
          Tip: In DevTools → Network, enable the <strong>Protocol</strong> column.
          For video requests you should see <code>h3</code> when HTTP/3 is used.
        </p>
      </aside>
    </div>

    <footer>
      COEN 6861 · Student CDN prototype
    </footer>
  </div>

  <script>
    fetch("/meta")
      .then(r => r.json())
      .then(data => {
        const ul = document.getElementById("cdn-meta");
        ul.innerHTML = "";
        const liCtrl = document.createElement("li");
        liCtrl.textContent = "Controller: " + (data.controller || "n/a");
        ul.appendChild(liCtrl);
        if (data.replicas && data.replicas.length) {
          data.replicas.forEach((r, idx) => {
            const li = document.createElement("li");
            li.textContent = "Replica " + (idx + 1) + ": " + r;
            ul.appendChild(li);
          });
        } else {
          const li = document.createElement("li");
          li.textContent = "No replicas reported by controller.";
          ul.appendChild(li);
        }
      })
      .catch(() => {
        const ul = document.getElementById("cdn-meta");
        ul.innerHTML = "<li>Controller not reachable.</li>";
      });
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
  <title>Playing {video_id} · CDN Demo</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
      padding: 0;
      background: #020617;
      color: #f9fafb;
    }}
    .page {{
      max-width: 960px;
      margin: 0 auto;
      padding: 24px 16px 40px;
    }}
    a {{
      color: #38bdf8;
    }}
    .card {{
      border-radius: 16px;
      padding: 16px 18px;
      background: radial-gradient(circle at top left, #111827, #020617);
      box-shadow: 0 18px 40px rgba(0,0,0,0.55);
    }}
    video {{
      width: 100%;
      max-height: 540px;
      border-radius: 12px;
      background: black;
    }}
    footer {{
      margin-top: 24px;
      font-size: 0.75rem;
      color: #6b7280;
    }}
  </style>
</head>
<body>
  <div class="page">
    <p><a href="/">← Back to home</a></p>
    <div class="card">
      <h2 style="margin-top:0;">Playing: {video_id}</h2>
      <video controls preload="metadata" src="/api/videos/{video_id}"></video>
      <p style="font-size:0.85rem;color:#9ca3af;margin-top:8px;">
        The <code>/api/videos/{video_id}</code> endpoint asks the controller to
        select a replica and then redirects the browser to that replica.
      </p>
    </div>
    <footer>
      COEN 6861 · Content Delivery Network demo
    </footer>
  </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return HOME_HTML


@app.get("/play", response_class=HTMLResponse)
def play(id: str):
    return play_page(id)


@app.get("/meta")
async def meta():
    """
    Small helper for the UI: ask the controller for its configured replicas.
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
        # we DO NOT force HTTP/2 here; Hypercorn/QUIC negotiates protocol
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
                # simplest & most robust: let the BROWSER follow the redirect
                return RedirectResponse(url=loc, status_code=head.status_code)

            if head.status_code in (200, 206, 304):
                # 2) Controller is serving directly — stream it
                async with client.stream("GET", ctrl_url, headers=fwd_headers) as r:
                    if r.status_code not in (200, 206, 304):
                        with contextlib.suppress(Exception):
                            err = await r.aread()
                            err = err.decode("utf-8", "ignore")[:400]
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
