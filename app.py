import os, subprocess, threading, time, httpx, uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
FILES_DIR = os.path.join(PROJECT_ROOT, "output_files")
os.makedirs(FILES_DIR, exist_ok=True)
open(os.path.join(FILES_DIR, ".keep"), "a").close()

PORT     = int(os.environ.get("PORT", 8000))
ADK_PORT = 8001

app = FastAPI()
app.mount("/files", StaticFiles(directory=FILES_DIR, html=True), name="files")

@app.get("/health")
async def health(): return {"ok": True}

@app.api_route("/{path:path}", methods=["GET","POST","PUT","DELETE","PATCH","OPTIONS","HEAD"])
async def proxy(request: Request, path: str):
    url = f"http://127.0.0.1:{ADK_PORT}/{path}"
    headers = {k:v for k,v in request.headers.items() if k.lower() not in ("host","content-length")}
    headers["host"] = f"127.0.0.1:{ADK_PORT}"
    async with httpx.AsyncClient(timeout=120) as c:
        try:
            r = await c.request(request.method, url, headers=headers,
                                content=await request.body(),
                                params=dict(request.query_params),
                                follow_redirects=False)
            h = {k:v for k,v in r.headers.items() if k.lower() not in ("transfer-encoding","content-encoding")}
            if "location" in h:
                h["location"] = h["location"].replace(f"http://127.0.0.1:{ADK_PORT}","")
            return StreamingResponse(r.aiter_bytes(), status_code=r.status_code, headers=h)
        except httpx.ConnectError:
            return JSONResponse({"error":"ADK starting, retry in seconds"}, status_code=503)

def run_adk():
    time.sleep(4)
    subprocess.Popen(["adk","web","market_scout_agent",
                      "--host","127.0.0.1","--port",str(ADK_PORT)],
                     cwd=PROJECT_ROOT)

threading.Thread(target=run_adk, daemon=True).start()
uvicorn.run(app, host="0.0.0.0", port=PORT)