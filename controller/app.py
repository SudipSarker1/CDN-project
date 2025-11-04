from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse

app = FastAPI(title="controller")

# >>> change ports here if you used different ones
replicas = [
    "http://127.0.0.1:9101",
    "http://127.0.0.1:9102"
    "http://127.0.0.1:9103",
]

_rr = 0  # round-robin index

@app.get("/videos/{video_name}")
def route_video(video_name: str):
    global _rr
    if not video_name:
        raise HTTPException(status_code=400, detail="video name required")

    target = replicas[_rr % len(replicas)]
    _rr += 1

    # 302 redirect to the chosen replica
    return RedirectResponse(url=f"{target}/videos/{video_name}", status_code=302)
