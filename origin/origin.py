# origin/origin.py
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Tuple

import httpx

# Paths relative to project root
BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG = BASE_DIR / "config" / "replicas.json"
VIDEOS_DIR = BASE_DIR / "videos"
UPLOAD_PATH = "/upload"  # replicas expect POST /upload with header: video-id


def load_replicas() -> List[str]:
    """
    Load replica URLs from config/replicas.json

    Supports either:
      ["https://localhost:9101", "https://localhost:9102"]
    or:
      {"replicas": ["https://localhost:9101", "https://localhost:9102"]}
    """
    if not CONFIG.exists():
        print(f"[origin] ERROR: missing config file: {CONFIG}", file=sys.stderr)
        sys.exit(1)

    with CONFIG.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        replicas = data
    else:
        replicas = data.get("replicas", [])

    if not replicas:
        print("[origin] ERROR: no replicas configured in replicas.json", file=sys.stderr)
        sys.exit(1)

    # Make a pretty display string: "url1, url2, url3"
    display = ", ".join(replicas)
    print(f"[origin] Using replicas: {display}")
    return replicas


def load_videos() -> list[Path]:
    """
    Find all .mp4 files in the project-level videos/ folder.
    """
    if not VIDEOS_DIR.exists():
        print(f"[origin] ERROR: videos directory not found: {VIDEOS_DIR}", file=sys.stderr)
        sys.exit(1)

    files = sorted(
        p for p in VIDEOS_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".mp4"
    )
    if not files:
        print(f"[origin] ERROR: no .mp4 files in {VIDEOS_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"[origin] Videos dir    : {VIDEOS_DIR}")
    print("[origin] Files to send : " + ", ".join(p.name for p in files))
    return files


def upload_to_replica(replica: str, video: Path) -> Tuple[bool, str]:
    """
    POST raw bytes of 'video' to '{replica}/upload' with header video-id.

    video-id = filename without extension, e.g. "sample" for "sample.mp4".
    """
    video_id = video.stem  # "sample" from "sample.mp4"
    url = replica.rstrip("/") + UPLOAD_PATH

    # Read file contents
    try:
        data = video.read_bytes()
    except Exception as e:
        return False, f"could not read video file: {e!r}"

    headers = {
        "video-id": video_id,
        "content-type": "application/octet-stream",
    }

    # Generous timeout (important for Windows + large files)
    timeout = httpx.Timeout(
        connect=10.0,
        read=60.0,
        write=60.0,
        pool=None,
    )

    try:
        with httpx.Client(verify=False, timeout=timeout) as client:
            r = client.post(url, headers=headers, content=data)
        if r.status_code == 200:
            return True, f"status={r.status_code} {r.text}"
        else:
            return False, f"status={r.status_code} body={r.text}"
    except Exception as e:
        return False, f"EXC {e.__class__.__name__}: {e}"


def main() -> None:
    replicas = load_replicas()
    videos = load_videos()

    print("--------------------------------------------------")

    total_success = 0
    total_fail = 0

    for video in videos:
        for rep in replicas:
            ok, msg = upload_to_replica(rep, video)
            status = "SUCCESS" if ok else "FAIL"
            print(f"[origin] {status}: {rep} <- {video.name}  [{msg}]")
            if ok:
                total_success += 1
            else:
                total_fail += 1

    print("\n[origin] Upload summary")
    print("--------------------------------------------------")
    print(f"  Success: {total_success}")
    print(f"  Failed : {total_fail}")

    if total_fail:
        sys.exit(2)


if __name__ == "__main__":
    main()
