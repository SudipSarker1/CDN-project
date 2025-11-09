# origin/origin.py
from __future__ import annotations
import json, sys
from pathlib import Path
from typing import List
import httpx  # sync client

# Paths
BASE_DIR   = Path(__file__).resolve().parents[1]
CONFIG     = BASE_DIR / "config" / "replicas.json"
VIDEOS_DIR = BASE_DIR / "videos"
UPLOAD_PATH = "/upload"  # replicas expect POST /upload with header: video-id

def load_replicas() -> List[str]:
    if not CONFIG.exists():
        print(f"[origin] ERROR: missing config file: {CONFIG}", file=sys.stderr)
        sys.exit(2)
    # tolerate BOM if present
    data = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        reps = data.get("replicas", [])
    elif isinstance(data, list):
        reps = data
    else:
        print("[origin] ERROR: replicas.json must be a list or an object with 'replicas'", file=sys.stderr)
        sys.exit(2)
    reps = [str(r).rstrip("/") for r in reps]
    if not reps:
        print("[origin] ERROR: replicas list is empty", file=sys.stderr)
        sys.exit(2)
    return reps

def find_videos() -> List[Path]:
    if not VIDEOS_DIR.exists():
        print(f"[origin] ERROR: missing videos dir: {VIDEOS_DIR}", file=sys.stderr)
        sys.exit(2)
    files = sorted(VIDEOS_DIR.glob("*.mp4"))
    if not files:
        print(f"[origin] ERROR: no .mp4 files found in {VIDEOS_DIR}", file=sys.stderr)
        sys.exit(2)
    return files

def upload_one(replica: str, path: Path) -> tuple[bool, str]:
    vid = path.stem
    url = f"{replica}{UPLOAD_PATH}"
    headers = {"video-id": vid, "content-type": "application/octet-stream"}
    try:
        with path.open("rb") as f:
            r = httpx.post(url, headers=headers, content=f, timeout=60.0, verify=False)
        if r.status_code in (200, 201, 204, 409):
            return True, f"OK ({r.status_code})"
        return False, f"HTTP {r.status_code} {r.text[:120]}"
    except Exception as e:
        return False, f"EXC {type(e).__name__}: {e}"

def main():
    reps = load_replicas()
    files = find_videos()

    print(f"[origin] Using replicas: {', '.join(reps)}")
    print(f"[origin] Videos dir    : {VIDEOS_DIR}")
    print(f"[origin] Files to send : {', '.join(p.name for p in files)}")
    print("--------------------------------------------------")

    ok = 0
    fail = 0
    for rep in reps:
        for p in files:
            success, msg = upload_one(rep, p)
            status = "SUCCESS" if success else "FAIL"
            print(f"[origin] {status}: {rep} <- {p.name}  [{msg}]")
            ok += 1 if success else 0
            fail += 0 if success else 1

    print("\n[origin] Upload summary")
    print("--------------------------------------------------")
    print(f"  Success: {ok}")
    print(f"  Failed : {fail}")

    if fail:
        sys.exit(2)

if __name__ == "__main__":
    main()
