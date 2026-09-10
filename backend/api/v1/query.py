import uuid
from typing import Any
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.api.v1.auth import get_current_user
from backend.models import User

router = APIRouter(prefix="/api/v1/query", tags=["Query"])

@router.post("/submit")
async def submit_query(
    prompt: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submits a query for analysis.
    Canonical LangGraph workflow runs via POST /ingest and POST /run.
    """
    task_id = str(uuid.uuid4())
    return {
        "task_id": task_id,
        "status": "queued",
        "message": "Query received. Use POST /ingest and POST /run for LangGraph multi-stage execution.",
    }


@router.websocket("/stream/{task_id}")
async def stream_query_updates(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        await websocket.send_json({"task_id": task_id, "status": "completed", "message": "Stream simulation complete."})
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()
