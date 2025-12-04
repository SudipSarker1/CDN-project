from typing import Dict

from fastapi import APIRouter, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()

# Simple in-memory user "database"
USERS: Dict[str, str] = {
    "sudip": "1234",
    "admin": "admin123",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_page_html(
    title: str,
    heading: str,
    description: str,
    submit_label: str,
    action: str,
    active_tab: str,
    next_value: str,
) -> str:
    """Return shared HTML for login/signup page with tabs."""
    login_active = "tab-active" if active_tab == "login" else ""
    signup_active = "tab-active" if active_tab == "signup" else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{title} – CDN Frontend</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    :root {{
      color-scheme: dark;
      --bg: #020617;
      --panel: #0f172a;
      --border: #1f2937;
      --text: #f9fafb;
      --muted: #9ca3af;
      --accent: #ef4444;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: radial-gradient(circle at top, #111827, #020617 55%);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
    }}
    .card {{
      width: 100%;
      max-width: 440px;
      padding: 26px 26px 22px;
      border-radius: 20px;
      background: var(--panel);
      border: 1px solid var(--border);
      box-shadow: 0 22px 50px rgba(0, 0, 0, 0.8);
    }}
    .tabs {{
      display: flex;
      gap: 6px;
      margin-bottom: 18px;
      border-radius: 999px;
      padding: 3px;
      background: #020617;
    }}
    .tab {{
      flex: 1;
      font-size: 0.95rem;
      text-align: center;
      padding: 8px 0;
      border-radius: 999px;
      border: 1px solid transparent;
      color: var(--muted);
      text-decoration: none;
      cursor: pointer;
    }}
    .tab-active {{
      color: var(--text);
      background: #111827;
      border-color: #1f2937;
      font-weight: 600;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 1.7rem;
      font-weight: 700;
    }}
    p {{
      margin: 0 0 20px;
      font-size: 1rem;
      color: var(--muted);
    }}
    label {{
      display: block;
      margin-bottom: 4px;
      font-size: 0.9rem;
      color: var(--muted);
    }}
    input[type="text"],
    input[type="password"] {{
      width: 100%;
      padding: 11px 13px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: #020617;
      color: var(--text);
      font-size: 1rem;
      margin-bottom: 12px;
    }}
    button {{
      margin-top: 10px;
      width: 100%;
      padding: 11px 0;
      border-radius: 999px;
      border: 1px solid #f97373;
      background: #b91c1c;
      color: #fff;
      font-size: 1rem;
      font-weight: 600;
      cursor: pointer;
    }}
    button:hover {{
      background: #dc2626;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="tabs">
      <a class="tab {login_active}" href="/login">Sign in</a>
      <a class="tab {signup_active}" href="/signup">Sign up</a>
    </div>
    <h1>{heading}</h1>
    <p>{description}</p>
    <form action="{action}" method="post">
      <input type="hidden" name="next" value="{next_value}">
      <label for="username">Username</label>
      <input id="username" name="username" type="text" required />

      <label for="password">Password</label>
      <input id="password" name="password" type="password" required />

      <button type="submit">{submit_label}</button>
    </form>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
async def login_page(next: str = Query("/", description="Redirect destination after login")):
    """Sign-in page."""
    html = _auth_page_html(
        title="Login",
        heading="Sign in",
        description="Sign in to continue to CDN miniTUBE.",
        submit_label="Sign in",
        action="/login",
        active_tab="login",
        next_value=next,
    )
    return HTMLResponse(content=html)


@router.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    """Handle login form, set username cookie."""
    if USERS.get(username) == password:
        response = RedirectResponse(url=next or "/", status_code=303)
        response.set_cookie("username", username, httponly=True)
        return response

    # invalid login → back to login page
    return RedirectResponse(url="/login", status_code=303)


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------

@router.get("/signup", response_class=HTMLResponse)
async def signup_page(next: str = Query("/", description="Redirect destination after signup")):
    """Sign-up page."""
    html = _auth_page_html(
        title="Sign up",
        heading="Create an account",
        description="Create an account to post comments on CDN miniTUBE.",
        submit_label="Sign up",
        action="/signup",
        active_tab="signup",
        next_value=next,
    )
    return HTMLResponse(content=html)


@router.post("/signup")
async def signup(
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    """Handle sign-up form: create user if not exists, then log in."""
    username = username.strip()
    if not username or not password:
        return RedirectResponse(url="/signup", status_code=303)

    if username in USERS:
        # Username already taken → go back to sign in
        return RedirectResponse(url="/login", status_code=303)

    # Register new user (in-memory)
    USERS[username] = password

    response = RedirectResponse(url=next or "/", status_code=303)
    response.set_cookie("username", username, httponly=True)
    return response


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@router.get("/logout")
async def logout(next: str = Query("/", description="Redirect destination after logout")):
    """Clear username cookie."""
    response = RedirectResponse(url=next or "/", status_code=303)
    response.delete_cookie("username")
    return response
