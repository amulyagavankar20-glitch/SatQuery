import uuid
import os
from typing import Any
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.api.v1.auth import get_current_user
from backend.models import User, Asset
from backend.config import settings

router = APIRouter(prefix="/api/v1/assets", tags=["Assets"])

@router.post("/upload")
async def upload_asset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Ensure directory exists
    os.makedirs(settings.full_data_dir / "uploads", exist_ok=True)
    
    asset_id = uuid.uuid4()
    file_path = settings.full_data_dir / "uploads" / f"{asset_id}_{file.filename}"
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
        
    # We would normally parse metadata via rasterio here, mocked for now
    new_asset = Asset(
        id=asset_id,
        file_path=str(file_path),
        filename=file.filename,
        format=file.content_type or "unknown",
        modality="optical" # Mock
    )
    # The actual relation to a job would happen when the job is created.
    
    return {"asset_id": str(asset_id), "message": "Asset uploaded successfully"}
