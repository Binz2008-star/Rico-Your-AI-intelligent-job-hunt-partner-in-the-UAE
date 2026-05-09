"""FastAPI server for Rico AI.

Additive server layer that does not modify existing scripts.
Run locally:

    uvicorn src.rico_server:app --reload --port 8000
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel

from src.cv_parser import CVParser
from src.rico_chat_api import RicoChatAPI
from src.rico_db import init_rico_db

app = FastAPI(title="Rico AI API", version="0.1.0")
chat_api = RicoChatAPI()
cv_parser = CVParser()


class ChatRequest(BaseModel):
    user_id: str
    message: str


@app.on_event("startup")
def startup_event() -> None:
    try:
        init_rico_db()
    except Exception:
        pass


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "product": "Rico AI",
        "status": "online",
        "description": "Your autonomous UAE career agent.",
    }


@app.post("/api/chat")
def chat(payload: ChatRequest) -> Dict[str, Any]:
    return chat_api.process_message(payload.user_id, payload.message)


@app.post("/api/upload-cv")
async def upload_cv(user_id: str, file: UploadFile = File(...)) -> Dict[str, Any]:
    data = await file.read()
    parsed = cv_parser.parse_bytes(data, filename=file.filename or "cv.pdf")
    return {
        "user_id": user_id,
        "filename": file.filename,
        "parsed": parsed.to_dict(),
    }


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "healthy"}
