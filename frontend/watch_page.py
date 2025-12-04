from typing import List, Dict, Optional
import html

from fastapi.responses import HTMLResponse


def render_watch_page(
    current: Dict[str, str],
    others: List[Dict[str, str]],
    comments: List[Dict[str, str]],
    current_user: Optional[str] = None,
) -> HTMLResponse:
    """Render the /watch/{video_id} page."""

    # sidebar (other videos) cards
    sidebar_cards = []
    for v in others:
        sidebar_cards.append(
            f"""
            <a class="video-card" href="/watch/{v['id']}">
              <video
                class="thumb"
                src="/api/videos/{v['id']}"
                preload="metadata"
                muted
              ></video>
              <div class="video-title" title="{html.escape(v['title'])}">
                {html.escape(v['title'])}
              </div>
            </a>
            """
        )
    sidebar_html = (
        "\n".join(sidebar_cards)
        if sidebar_cards
        else "<div class='empty'>No other videos available.</div>"
    )

    # user header snippet (top-right)
    if current_user:
        safe_name = html.escape(current_user)
        user_html = f"""
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
        user_html = """
    <div class="user-area">
      <a class="user-btn" href="/login">
        <span class="user-icon">👤</span>
        <span class="user-name">Log in</span>
      </a>
    </div>
"""

    # comments
    comment_items = []
    for c in comments:
        author = html.escape(c.get("author", "Anonymous"))
        text = html.escape(c.get("text", ""))

        ts_raw = c.get("timestamp", "")
        date_part = ts_raw
        time_part = ""

        if "T" in ts_raw:
            d, t = ts_raw.split("T", 1)
            date_part = d
            time_part = t.rstrip("Z")

        date_part = html.escape(date_part)
        time_part = html.escape(time_part)
        if time_part:
            ts_label = f"Date: {date_part};  Time: {time_part}"
        else:
            ts_label = f"Date: {date_part}"

        delete_button = ""
        cid = c.get("id")
        if current_user and cid is not None and c.get("author") == current_user:
            delete_button = f"""
            <form class="comment-delete-form"
                  action="/api/watch/{current['id']}/comment/{cid}/delete"
                  method="post">
              <button type="submit" class="comment-delete-btn">Delete</button>
            </form>
            """

        comment_items.append(
            f"""
            <div class="comment">
              <div class="comment-meta">
                <span class="comment-author">{author}</span>
                <span class="comment-time">{ts_label}</span>
              </div>
              <div class="comment-text">{text}</div>
              {delete_button}
            </div>
            """
        )

    comments_html = (
        "\n".join(comment_items)
        if comment_items
        else "<div class='no-comments'>No comments yet. Be the first to comment!</div>"
    )

    video_id = current["id"]

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{html.escape(current['title'])} – CDN Frontend</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b0b0b;
      --bg-elevated: #18181b;
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

    .watch-layout {{
      display: grid;
      grid-template-columns: minmax(0, 2.4fr) minmax(320px, 1.1fr);
      gap: 24px;
      margin-top: 12px;
    }}

    .player-column {{
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}

    .player-card {{
      background: var(--bg-elevated);
      border-radius: 18px;
      padding: 14px;
      border: 1px solid #1f2933;
      box-shadow: 0 18px 40px rgba(0, 0, 0, 0.8);
    }}

    .player-card > video {{
      width: 100%;
      border-radius: 14px;
      max-height: 75vh;
      aspect-ratio: 16 / 9;
      object-fit: contain;
      display: block;
      background-color: #020617;
    }}

    .current-title {{
      font-size: 1.15rem;
      font-weight: 600;
      line-height: 1.35;
    }}

    .sidebar {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}

    .sidebar-header {{
      font-size: 1.35rem;
      font-weight: 750;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #e5e7eb;
      border-bottom: 2px solid #27272a;
      padding-bottom: 4px;
      margin-bottom: 8px;
    }}

    .sidebar-list {{
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}

    .video-card {{
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}

    .thumb {{
      width: 100%;
      aspect-ratio: 16 / 9;
      border-radius: 14px;
      background-color: #000000;
      object-fit: cover;
      display: block;
      box-shadow: 0 10px 26px rgba(0, 0, 0, 0.55);
    }}

    .video-title {{
      font-size: 1.15rem;
      font-weight: 500;
      line-height: 1.35;
    }}

    .empty {{
      font-size: 0.8rem;
      color: var(--muted);
      margin-top: 6px;
    }}

    .comments {{
      margin-top: 8px;
      padding: 16px 18px;
      background: #111827;
      border-radius: 14px;
      border: 1px solid #1f2937;
    }}

    .comments-header {{
      font-size: 1.0rem;
      font-weight: 600;
      margin-bottom: 10px;
    }}

    .comment-form {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-bottom: 14px;
    }}

    .comment-textarea {{
      width: 100%;
      min-height: 70px;
      padding: 8px 10px;
      border-radius: 10px;
      border: 1px solid #374151;
      background-color: #020617;
      color: var(--text);
      font-size: 0.9rem;
      resize: vertical;
    }}

    .comment-textarea::placeholder {{
      color: #6b7280;
    }}

    .comment-submit {{
      align-self: flex-end;
      margin-top: 2px;
      padding: 7px 16px;
      border-radius: 999px;
      border: 1px solid #f97373;
      background: #b91c1c;
      color: white;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
    }}

    .comment-submit:hover {{
      background: #dc2626;
    }}

    .comment-list {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin-top: 6px;
    }}

    .comment {{
      padding: 8px 10px;
      border-radius: 10px;
      background: #020617;
      border: 1px solid #111827;
    }}

    .comment-meta {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.78rem;
      color: #9ca3af;
      margin-bottom: 4px;
      gap: 8px;
    }}

    .comment-author {{
      font-weight: 500;
    }}

    .comment-time {{
      font-size: 0.78rem;
      opacity: 0.95;
    }}

    .comment-text {{
      font-size: 0.9rem;
      white-space: pre-wrap;
    }}

    .no-comments {{
      font-size: 0.85rem;
      color: #9ca3af;
      margin-top: 4px;
    }}

    .comment-delete-form {{
      margin-top: 6px;
      text-align: right;
    }}

    .comment-delete-btn {{
      padding: 3px 10px;
      border-radius: 999px;
      border: 1px solid #f97373;
      background: #7f1d1d;
      color: #fee2e2;
      font-size: 0.75rem;
      cursor: pointer;
    }}

    .comment-delete-btn:hover {{
      background: #b91c1c;
    }}

    @media (max-width: 900px) {{
      .watch-layout {{
        grid-template-columns: minmax(0, 1fr);
      }}
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
        autocomplete="off"
      />
      <button class="search-btn" type="submit">
        🔍 <span>Search</span>
      </button>
    </form>
    {user_html}
  </header>

  <main>
    <div class="watch-layout">
      <section class="player-column">
        <div class="player-card">
          <video controls autoplay src="/api/videos/{video_id}"></video>
        </div>
        <div class="current-title">{html.escape(current['title'])}</div>

        <section class="comments">
          <div class="comments-header">Comments</div>
          <form id="comment-form" class="comment-form" action="/api/watch/{video_id}/comment" method="post">
            <textarea
              class="comment-textarea"
              name="text"
              placeholder="Add a public comment..."
              required
            ></textarea>
            <button class="comment-submit" type="submit">Post comment</button>
          </form>

          <div class="comment-list">
            {comments_html}
          </div>
        </section>
      </section>

      <aside class="sidebar">
        <div class="sidebar-header">Other videos</div>
        <div class="sidebar-list">
          {sidebar_html}
        </div>
      </aside>
    </div>
  </main>

  <script>
    (function () {{
      const videoId = {video_id!r};

      const form = document.getElementById('comment-form');
      if (!form) return;

      const list = document.querySelector('.comment-list');

      // POST COMMENT (AJAX)
      form.addEventListener('submit', async function (e) {{
        e.preventDefault();

        const textarea = form.querySelector('textarea[name="text"]');
        const text = textarea.value.trim();
        if (!text) return;

        const formData = new FormData(form);

        try {{
          const resp = await fetch(form.action, {{
            method: 'POST',
            body: formData
          }});

          const data = await resp.json().catch(() => ({{}}));

          if (!resp.ok) {{
            if (data && data.redirect) {{
              window.location.href = data.redirect;
            }}
            return;
          }}

          // Remove "no comments" message if present
          if (list) {{
            const empty = list.querySelector('.no-comments');
            if (empty) empty.remove();
          }}

          const commentDiv = document.createElement('div');
          commentDiv.className = 'comment';
          commentDiv.innerHTML = `
            <div class="comment-meta">
              <span class="comment-author"></span>
              <span class="comment-time"></span>
            </div>
            <div class="comment-text"></div>
            <form class="comment-delete-form"
                  method="post">
              <button type="submit" class="comment-delete-btn">Delete</button>
            </form>
          `;

          commentDiv.querySelector('.comment-author').textContent = data.author || '';
          commentDiv.querySelector('.comment-time').textContent =
            'Date: ' + (data.date || '') + ';  Time: ' + (data.time || '');
          commentDiv.querySelector('.comment-text').textContent = data.text || '';

          const deleteForm = commentDiv.querySelector('.comment-delete-form');
          deleteForm.action = '/api/watch/' + encodeURIComponent(videoId) +
                              '/comment/' + encodeURIComponent(data.id) + '/delete';

          if (list) {{
            list.appendChild(commentDiv);
          }}

          textarea.value = '';
        }} catch (err) {{
          console.error('comment error', err);
        }}
      }});

      // DELETE COMMENT (AJAX) using event delegation on the list
      if (list) {{
        list.addEventListener('submit', async function (e) {{
          const formEl = e.target;
          if (!formEl.classList.contains('comment-delete-form')) return;

          e.preventDefault();

          try {{
            const resp = await fetch(formEl.action, {{
              method: 'POST'
            }});

            const data = await resp.json().catch(() => ({{}}));

            if (!resp.ok) {{
              if (data && data.redirect) {{
                window.location.href = data.redirect;
              }}
              return;
            }}

            if (data.ok) {{
              const commentDiv = formEl.closest('.comment');
              if (commentDiv) commentDiv.remove();
            }}
          }} catch (err) {{
            console.error('delete error', err);
          }}
        }});
      }}
    }})();
  </script>
</body>
</html>
"""
    return HTMLResponse(content=page)
