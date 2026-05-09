"""FastAPI server for Rico AI.

Additive server layer that does not modify existing scripts.
Run locally:

    uvicorn src.rico_server:app --reload --port 8000
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, File, UploadFile, Request
from pydantic import BaseModel

from src.cv_parser import CVParser
from src.rico_chat_api import RicoChatAPI
from src.rico_db import RicoDB, init_rico_db
from src.rico_env import get_rico_env_report, safe_feature_defaults
from src.rico_jotform_webhook import handle_jotform_submission
from src.rico_telegram_webhook import process_telegram_update

app = FastAPI(title="Rico AI API", version="0.2.0")
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
        # Keep startup non-fatal so the legacy repo can still run without DB in dev.
        pass


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "product": "Rico AI",
        "status": "online",
        "description": "Your AI-native UAE career companion.",
        "feature_defaults": safe_feature_defaults(),
    }


@app.post("/api/chat")
def chat(payload: ChatRequest) -> Dict[str, Any]:
    return chat_api.process_message(payload.user_id, payload.message)


@app.post("/api/upload-cv")
async def upload_cv(user_id: str, file: UploadFile = File(...)) -> Dict[str, Any]:
    data = await file.read()
    parsed = cv_parser.parse_bytes(data, filename=file.filename or "cv.pdf")

    try:
        db = RicoDB()
        bundle = db.get_user_bundle(user_id)
        if bundle:
            db.upsert_profile(
                user_id=str(bundle["id"]),
                profile={"cv_uploaded": True},
                cv_text=parsed.text,
                cv_structured=parsed.to_dict(),
            )
    except Exception:
        pass

    return {
        "user_id": user_id,
        "filename": file.filename,
        "parsed": parsed.to_dict(),
    }


@app.post("/api/webhooks/jotform")
async def jotform_webhook(request: Request) -> Dict[str, Any]:
    payload = await request.json()
    return handle_jotform_submission(payload)


@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request) -> Dict[str, Any]:
    update = await request.json()
    return process_telegram_update(update)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "rico": get_rico_env_report().to_dict(),
    }
