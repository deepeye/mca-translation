import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {".txt", ".docx", ".pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("")
async def upload_file(file: UploadFile, user: User = Depends(get_current_user)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}. Supported: {', '.join(ALLOWED_EXTENSIONS)}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large ({len(content)} bytes). Maximum: {MAX_FILE_SIZE} bytes")

    file_id = str(uuid.uuid4())
    os.makedirs(settings.MCA_FILE_STORE_DIR, exist_ok=True)
    file_path = os.path.join(settings.MCA_FILE_STORE_DIR, f"{file_id}{ext}")
    with open(file_path, "wb") as f:
        f.write(content)

    return {"file_id": file_id, "filename": file.filename, "size": len(content)}
