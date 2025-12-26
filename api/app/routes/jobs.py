# api/app/routes/jobs.py

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..config import settings
from ..auth import get_user_id
from ..supabase_db import (
    create_job,
    get_job_owned,
    set_job_status,
    append_job_outputs,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


class CreateJobRequest(BaseModel):
    prompt: str = ""
    job_type: str = "img2img"  # img2img, img2vid, txt2img
    model_name: str = "realistic-vision-v5"
    lora_names: list[str] = []
    params: dict = {}


class JobStatusResponse(BaseModel):
    id: str
    status: str
    job_type: str
    prompt: str
    model_name: str
    lora_names: list[str]
    input_urls: list[dict]
    output_urls: list[dict]
    error: Optional[str] = None


@router.post("/create")
async def create_new_job(req: CreateJobRequest, user_id: str = Depends(get_user_id)):
    """Create a new job in the database (status: queued)"""
    job = await create_job(
        user_id=user_id,
        prompt=req.prompt,
        params=req.params,
        model_name=req.model_name,
        lora_names=req.lora_names,
        job_type=req.job_type,
    )
    return {"job_id": job["id"], "status": job["status"], "job_type": job.get("job_type", "img2img")}


@router.post("/{job_id}/dispatch")
async def dispatch_job(job_id: str, user_id: str = Depends(get_user_id)):
    """Dispatch a job to RunPod for processing"""
    job = await get_job_owned(job_id=job_id, user_id=user_id)

    if job["status"] != "queued":
        raise HTTPException(status_code=400, detail=f"Job status is {job['status']}, expected 'queued'")

    if not job.get("input_urls"):
        raise HTTPException(status_code=400, detail="No input files uploaded")

    # Build RunPod payload
    input_keys = [entry["key"] for entry in job["input_urls"]]
    output_prefix = f"users/{user_id}/jobs/{job_id}/outputs/"

    runpod_payload = {
        "input": {
            "job_id": job_id,
            "user_id": user_id,
            "input_keys": input_keys,
            "output_prefix": output_prefix,
            "job_type": job.get("job_type", "img2img"),
            "model_name": job["model_name"],
            "lora_names": job.get("lora_names", []),
            "params": job.get("params", {}),
            "prompt": job.get("prompt", ""),
        }
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"https://api.runpod.ai/v2/{settings.RUNPOD_ENDPOINT_ID}/run",
            headers={
                "Authorization": f"Bearer {settings.RUNPOD_API_KEY}",
                "Content-Type": "application/json",
            },
            json=runpod_payload,
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"RunPod error: {resp.text}")

    runpod_data = resp.json()
    return {"runpod_job_id": runpod_data.get("id"), "status": "dispatched"}


@router.get("/{job_id}/status")
async def get_job_status(job_id: str, user_id: str = Depends(get_user_id)):
    """Get the status of a job"""
    job = await get_job_owned(job_id=job_id, user_id=user_id)
    return JobStatusResponse(
        id=job["id"],
        status=job["status"],
        job_type=job.get("job_type", "img2img"),
        prompt=job.get("prompt", ""),
        model_name=job.get("model_name", ""),
        lora_names=job.get("lora_names", []),
        input_urls=job.get("input_urls", []),
        output_urls=job.get("output_urls", []),
        error=job.get("error"),
    )


@router.get("/{job_id}/runpod-status")
async def get_runpod_status(job_id: str, runpod_job_id: str, user_id: str = Depends(get_user_id)):
    """Check RunPod job status"""
    # Verify user owns the job
    job = await get_job_owned(job_id=job_id, user_id=user_id)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"https://api.runpod.ai/v2/{settings.RUNPOD_ENDPOINT_ID}/status/{runpod_job_id}",
            headers={"Authorization": f"Bearer {settings.RUNPOD_API_KEY}"},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"RunPod error: {resp.text}")
    data = resp.json()

    # Opportunistically persist results to DB when completed/failed
    try:
        status = data.get("status") or data.get("execution", {}).get("status")
        # RunPod returns output from our worker under `output`
        output = data.get("output") or {}
        worker_status = None
        if isinstance(output, dict):
            worker_status = output.get("status")
        
        if status == "COMPLETED" or worker_status == "completed":
            # Append outputs (if present) and mark as completed
            outputs = []
            if isinstance(output, dict):
                outputs = output.get("outputs") or []
            if outputs:
                await append_job_outputs(job_id=job_id, user_id=user_id, outputs=outputs)
            if job.get("status") != "completed":
                await set_job_status(job_id=job_id, user_id=user_id, status="completed", error=None)
        elif status == "FAILED" or worker_status == "failed":
            err_msg = None
            if isinstance(output, dict):
                err_msg = output.get("error")
            await set_job_status(job_id=job_id, user_id=user_id, status="failed", error=err_msg)
    except Exception as e:
        # Don't break the status endpoint if DB update fails
        print(f"runpod-status side-effect failed for job {job_id}: {e}")

    return data

