from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx

from ..config import settings
from ..auth import get_user_id

router = APIRouter(prefix="/training", tags=["training"])


def _rest_base() -> str:
    return f"{settings.SUPABASE_URL}/rest/v1"


def _headers_service() -> dict:
    return {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


class CreateTrainingJobRequest(BaseModel):
    training_type: str = "lora"  # lora or dreambooth
    base_model: str = "sd15"
    lora_name: str
    trigger_word: str
    config: dict = {}


class TrainingJobResponse(BaseModel):
    id: str
    status: str
    training_type: str
    base_model: str
    progress: int
    error: Optional[str]


@router.post("/create")
async def create_training_job(req: CreateTrainingJobRequest, user_id: str = Depends(get_user_id)):
    """Create a new LoRA training job"""
    payload = {
        "user_id": user_id,
        "status": "queued",
        "training_type": req.training_type,
        "base_model": req.base_model,
        "config": {
            "lora_name": req.lora_name,
            "trigger_word": req.trigger_word,
            **req.config,
        },
        "input_images": [],
        "progress": 0,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{_rest_base()}/training_jobs",
            headers=_headers_service(),
            params={"select": "*"},
            json=payload,
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Failed to create training job: {resp.text}")

    return resp.json()[0]


@router.get("")
async def list_training_jobs(user_id: str = Depends(get_user_id)):
    """List user's training jobs"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_rest_base()}/training_jobs",
            headers=_headers_service(),
            params={
                "user_id": f"eq.{user_id}",
                "select": "*",
                "order": "created_at.desc",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to fetch jobs: {resp.text}")

    return resp.json()


@router.get("/{job_id}")
async def get_training_job(job_id: str, user_id: str = Depends(get_user_id)):
    """Get a specific training job"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_rest_base()}/training_jobs",
            headers=_headers_service(),
            params={
                "id": f"eq.{job_id}",
                "user_id": f"eq.{user_id}",
                "select": "*",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to fetch job: {resp.text}")

    rows = resp.json()
    if not rows:
        raise HTTPException(status_code=404, detail="Training job not found")
    
    return rows[0]


@router.post("/{job_id}/upload-image")
async def add_training_image(job_id: str, image_key: str, user_id: str = Depends(get_user_id)):
    """Add an uploaded image to training job"""
    # Get existing job
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_rest_base()}/training_jobs",
            headers=_headers_service(),
            params={
                "id": f"eq.{job_id}",
                "user_id": f"eq.{user_id}",
                "select": "*",
            },
        )
        
        if resp.status_code != 200 or not resp.json():
            raise HTTPException(status_code=404, detail="Training job not found")
        
        job = resp.json()[0]
        images = job.get("input_images") or []
        images.append({"key": image_key})
        
        # Update
        resp = await client.patch(
            f"{_rest_base()}/training_jobs",
            headers=_headers_service(),
            params={"id": f"eq.{job_id}"},
            json={"input_images": images},
        )

    return {"image_count": len(images)}


@router.post("/{job_id}/start")
async def start_training(job_id: str, user_id: str = Depends(get_user_id)):
    """Start the training job on RunPod"""
    # Get job
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_rest_base()}/training_jobs",
            headers=_headers_service(),
            params={"id": f"eq.{job_id}", "user_id": f"eq.{user_id}", "select": "*"},
        )
        
        if not resp.json():
            raise HTTPException(status_code=404, detail="Job not found")
        
        job = resp.json()[0]
        
        if job["status"] != "queued":
            raise HTTPException(status_code=400, detail="Job already started")
        
        if len(job.get("input_images", [])) < 5:
            raise HTTPException(status_code=400, detail="Need at least 5 training images")

    # TODO: Dispatch to RunPod training endpoint
    # For now, just update status
    async with httpx.AsyncClient(timeout=10) as client:
        await client.patch(
            f"{_rest_base()}/training_jobs",
            headers=_headers_service(),
            params={"id": f"eq.{job_id}"},
            json={"status": "processing"},
        )

    return {"status": "processing", "message": "Training job started"}

