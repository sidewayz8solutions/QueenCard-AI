from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import uuid

from ..auth import get_user_id
from ..r2 import presign_put, presign_get
from ..supabase_db import get_job_owned, append_job_input

router = APIRouter(prefix="/storage", tags=["storage"])

ALLOWED_MIME = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}

MAX_BYTES = 25 * 1024 * 1024  # 25 MB

class UploadUrlReq(BaseModel):
    job_id: str
    filename: str
    mime: str
    bytes: int

class DownloadUrlReq(BaseModel):
    key: str

def _make_input_key(*, user_id: str, job_id: str, ext: str) -> str:
    file_id = str(uuid.uuid4())
    return f"users/{user_id}/jobs/{job_id}/inputs/{file_id}.{ext}"

@router.post("/upload-url")
async def generateUploadUrl(req: UploadUrlReq, user_id: str = Depends(get_user_id)):
    job = await get_job_owned(job_id=req.job_id, user_id=user_id)

    if job.get("status") != "queued":
        raise HTTPException(status_code=400, detail="Job not in 'queued' state")

    if req.bytes <= 0 or req.bytes > MAX_BYTES:
        raise HTTPException(status_code=400, detail="File size not allowed")

    if req.mime not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="MIME type not allowed")

    ext = ALLOWED_MIME[req.mime]
    key = _make_input_key(user_id=user_id, job_id=req.job_id, ext=ext)

    put_url = presign_put(key=key, content_type=req.mime, expires_seconds=600)

    input_entry = {"key": key, "mime": req.mime, "bytes": req.bytes}
    await append_job_input(job_id=req.job_id, user_id=user_id, input_entry=input_entry)

    return {"key": key, "put_url": put_url}

@router.post("/download-url")
async def generateDownloadUrl(req: DownloadUrlReq, user_id: str = Depends(get_user_id)):
    prefix = f"users/{user_id}/"
    if not req.key.startswith(prefix):
        raise HTTPException(status_code=403, detail="Not allowed")

    get_url = presign_get(key=req.key, expires_seconds=1800)
    return {"get_url": get_url}

