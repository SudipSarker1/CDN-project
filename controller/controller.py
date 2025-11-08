from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
import itertools, json, pathlib, httpx

app = FastAPI(title="controller")
conf = pathlib.Path("config/replicas.json")
replicas = (json.loads(conf.read_text())["replicas"] if conf.exists() else
            [{"name":"ReplicaA","url":"http://127.0.0.1:9101"},
             {"name":"ReplicaB","url":"http://127.0.0.1:9102"}])
_cycle = itertools.cycle(replicas)

@app.get("/videos/{name}")
async def proxy(name: str, request: Request):
    target = next(_cycle)["url"].rstrip("/") + f"/videos/{name}"
    headers = {}
    if "range" in request.headers:
        headers["range"] = request.headers["range"]
    async with httpx.AsyncClient(http2=False, timeout=None) as client:
        try:
            r = await client.stream("GET", target, headers=headers)
        except httpx.HTTPError as e:
            raise HTTPException(502, f"replica error: {e}")
        if r.status_code not in (200, 206):
            detail = await r.aread()
            raise HTTPException(r.status_code, detail.decode("utf-8", "ignore"))
        passthrough = {h: r.headers[h] for h in
                       ("content-type","content-length","content-range","accept-ranges")
                       if h in r.headers}
        return StreamingResponse(r.aiter_bytes(), status_code=r.status_code, headers=passthrough)
