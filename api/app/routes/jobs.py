# api/app/routes/jobs.py

import httpx
import uuid
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
from ..r2 import upload_base64

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

    # Build payload for our custom worker (worker/worker.py)
    # Worker expects full job context and uploads results to R2
    input_keys = [entry["key"] for entry in job.get("input_urls", [])]
    output_prefix = f"users/{user_id}/jobs/{job_id}/outputs/"

    # Merge job-level params with any stored params
    params = job.get("params", {})
    params["prompt"] = job.get("prompt", "")
    params["lora_names"] = job.get("lora_names", [])

    runpod_input = {
        "job_id": job_id,
        "user_id": user_id,
        "input_keys": input_keys,
        "output_prefix": output_prefix,
        "job_type": job.get("job_type", "img2img"),
        "model_name": job.get("model_name", "realistic-vision-v5"),
        "params": params,
    }

    runpod_payload = {"input": runpod_input}

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
        status = data.get("status")
        output = data.get("output")

        if status == "COMPLETED" and job.get("status") != "completed":
            # Our custom worker returns: {"status": "success", "outputs": [...]}
            # Each output has {"key": "r2-key", "type": "video"/"image"}
            outputs = []

            if isinstance(output, dict):
                worker_status = output.get("status")
                worker_outputs = output.get("outputs", [])

                if worker_status == "success" and worker_outputs:
                    # Worker already uploaded to R2, just save the keys
                    outputs = worker_outputs
                elif "video" in output:
                    # Fallback: pre-built worker returns base64 video
                    video_key = f"users/{user_id}/jobs/{job_id}/output_{uuid.uuid4()}.mp4"
                    try:
                        upload_base64(key=video_key, data=output["video"], content_type="video/mp4")
                        outputs.append({"type": "video", "key": video_key})
                    except Exception as upload_err:
                        print(f"Failed to upload video to R2: {upload_err}")

            if outputs:
                await append_job_outputs(job_id=job_id, user_id=user_id, outputs=outputs)
            await set_job_status(job_id=job_id, user_id=user_id, status="completed", error=None)

            # Return clean response
            data["output"] = {"status": "completed", "outputs": outputs}

        elif status == "FAILED":
            err_msg = "Generation failed"
            if "error" in data:
                err_msg = data["error"]
            elif isinstance(output, dict):
                err_msg = output.get("error") or output.get("message") or str(output)
            await set_job_status(job_id=job_id, user_id=user_id, status="failed", error=err_msg)
    except Exception as e:
        # Don't break the status endpoint if DB update fails
        print(f"runpod-status side-effect failed for job {job_id}: {e}")
        import traceback
        traceback.print_exc()

    return data

