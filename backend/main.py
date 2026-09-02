from fastapi import FastAPI
from backend.api import jobs

app = FastAPI(
    title="SatQuery AI API",
    description="SIH26167 SatQuery backend for Agentic Orchestration",
    version="1.0.0"
)

app.include_router(jobs.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
