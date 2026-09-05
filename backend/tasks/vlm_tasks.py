import json
import time
import redis
from backend.worker import celery_app
from backend.config import settings

r = redis.from_url(settings.REDIS_URL)

@celery_app.task(name="vlm_tasks.process_multimodal_query")
def process_multimodal_query(task_id: str, prompt: str, image_path: str, user_id: str):
    # Simulate processing and publishing updates to Redis
    channel = f"task_updates:{task_id}"
    
    r.publish(channel, json.dumps({"status": "processing", "message": "Loading image..."}))
    time.sleep(2)
    
    r.publish(channel, json.dumps({"status": "processing", "message": "Running VLM inference..."}))
    time.sleep(5)
    
    # Mock result
    result = {
        "status": "completed",
        "result": "The image shows a large urban area with a park in the center.",
        "confidence": 0.95
    }
    r.publish(channel, json.dumps(result))
    
    return result
