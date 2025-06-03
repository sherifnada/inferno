from fastapi import FastAPI, HTTPException, Request
import httpx, os

app = FastAPI()

SERVICE_MAP = {
    "tinyllama/tinyllama-1.1b-chat-v1.0": "http://tinyllama:8000",
    "qwen/qwen2.5-vl-7b-instruct":        "http://qwen2-5-vl-7b:8000",
}

@app.post("/v1/chat/completions")
async def proxy(request: Request):
    body  = await request.json()
    model = body.get("model", "").lower()
    if not model or model == "":
        raise HTTPException(400, "model field required")

    target = SERVICE_MAP.get(model)
    if not target:
        raise HTTPException(400, f"unknown model {model}")

    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{target}/v1/chat/completions",
                                 json=body, timeout=None)
    return resp.json()