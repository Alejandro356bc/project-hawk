"""Hawk API: runs web debates for the Next.js frontend.

Start it with:  python -m uvicorn backend.main:app --port 8787
The frontend reaches it server-to-server (frontend/src/app/api/debate), so it
only needs to listen on localhost.
"""

import json
import logging
import os
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.debate import RoundRequest, run_round

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Hawk API", description="Backend for Hawk multi-LLM debates")

# HAWK_CORS_ORIGINS: comma-separated list of allowed origins.
# In production (Render), set this to your frontend URL, e.g.:
#   https://project-hawk.onrender.com
_raw_origins = os.environ.get("HAWK_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "Hawk API is running"}


@app.post("/debate/round")
async def debate_round(req: RoundRequest) -> StreamingResponse:
    """Stream one debate round as server-sent events (one JSON object per event)."""

    async def events() -> AsyncGenerator[str, None]:
        async for event in run_round(req):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
