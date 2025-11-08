import json, pathlib, time
from typing import Dict, List
import httpx

VIDEOS_DIR = pathlib.Path("videos")
CONFIG_PATH = pathlib.Path("config/replicas.json")

def load_replicas() -> List[Dict]:
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        reps = data.get("replicas", [])
    else:
        reps = []
    if not reps:
        # default to A/B on HTTP (aligns with controller fallback)
        reps = [
            {"name": "ReplicaA", "url": "http://127.0.0.1:9101"},
            {"name": "ReplicaB", "url": "http://127.0.0.1:9102"},
        ]
    return reps

def upload_one(client: httpx.Client, url: str, video_path: pathlib.Path, video_id: str, who: str, retries: int = 3):
    tries = 0
    while True:
        tries += 1
        try:
            with video_path.open("rb") as f:
                files = {"file": (video_path.name, f, "video/mp4")}
                headers = {"video-id": video_id}  # matches replicas' Header(alias="video-id")
                resp = client.post(url, headers=headers, files=files)
            if resp.status_code == 200:
                print(f"  OK -> {who}: {resp.json()}")
            else:
                print(f"  ERROR {resp.status_code} -> {who}: {resp.text}")
            break
        except (httpx.WriteError, httpx.TransportError) as e:
            if tries <= retries:
                print(f"  WARN -> {who}: {e!s} — retry {tries}/{retries}")
                time.sleep(0.5 * tries)
                continue
            print(f"  FAIL -> {who}: {e!s}")
            break

def main():
    replicas = load_replicas()
    mp4s = sorted(VIDEOS_DIR.glob("*.mp4"))
    if not mp4s:
        print("No .mp4 files found in ./videos. Add a small test file first.")
        return

    # Use HTTP/1.1 on Windows to avoid occasional h2 reset quirks
    limits = httpx.Limits(max_keepalive_connections=2, max_connections=5)
    with httpx.Client(http2=False, timeout=None, limits=limits) as client:
        for video_path in mp4s:
            vid = video_path.stem
            print(f"Uploading {vid} ({video_path.name})")
            for r in replicas:
                url = r["url"].rstrip("/") + "/upload"
                upload_one(client, url, video_path, vid, r["name"])

if __name__ == "__main__":
    main()
