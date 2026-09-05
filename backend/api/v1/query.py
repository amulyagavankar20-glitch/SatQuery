import uuid
from typing import Any
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.api.v1.auth import get_current_user
from backend.models import User
from backend.worker import celery_app

from fastapi_limiter.depends import RateLimiter

router = APIRouter(prefix="/api/v1/query", tags=["Query"])

@router.post("/submit", dependencies=[Depends(RateLimiter(times=10, minutes=1))])
async def submit_query(
    prompt: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # This endpoint receives the prompt and image, saves the image,
    # generates a task UUID, and pushes to Celery.
    task_id = str(uuid.uuid4())
    
    # Normally we would save the image to disk or cloud storage here and get a path
    # For now we'll just mock the path
    image_path = f"data/uploads/{task_id}_{image.filename}"
    
    # Push the task to the Celery queue
    celery_app.send_task("vlm_tasks.process_multimodal_query", args=[task_id, prompt, image_path, current_user.id], task_id=task_id)
    
    return {"task_id": task_id, "status": "queued"}


@router.websocket("/stream/{task_id}")
async def stream_query_updates(websocket: WebSocket, task_id: str):
    await websocket.accept()
    # In a real scenario, this would subscribe to a Redis Pub/Sub channel based on task_id
    # where the Celery worker pushes updates.
    # We will mock the pubsub listen loop.
    try:
        import redis.asyncio as redis
        from backend.config import settings
        
        r = redis.from_url(settings.REDIS_URL)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"task_updates:{task_id}")
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"].decode("utf-8")
                await websocket.send_text(data)
                if "status" in data and "completed" in data or "error" in data:
                    break
    except WebSocketDisconnect:
        print(f"Client disconnected for task {task_id}")
    finally:
        await websocket.close()
