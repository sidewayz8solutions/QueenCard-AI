from fastapi import HTTPException
import httpx
from .config import settings

def _rest_base() -> str:
    return f"{settings.SUPABASE_URL}/rest/v1"

def _headers_service() -> dict:
    return {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Ensure PostgREST returns the inserted/updated row in the body
        "Prefer": "return=representation",
    }

async def create_job(*, user_id: str, prompt: str, params: dict, model_name: str, lora_names: list[str], job_type: str = "img2img") -> dict:
    payload = {
        "user_id": user_id,
        "status": "queued",
        "job_type": job_type,
        "prompt": prompt,
        "params": params,
        "model_name": model_name,
        "lora_names": lora_names,
        "input_urls": [],
        "output_urls": [],
        "error": None,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{_rest_base()}/jobs",
            headers=_headers_service(),
            params={"select": "*"},
            json=payload,
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Failed to create job: {resp.text}")

    return resp.json()[0]

async def get_job_owned(*, job_id: str, user_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_rest_base()}/jobs",
            headers=_headers_service(),
            params={
                "id": f"eq.{job_id}",
                "user_id": f"eq.{user_id}",
                "select": "*",
                "limit": "1",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to fetch job: {resp.text}")

    rows = resp.json()
    if not rows:
        raise HTTPException(status_code=404, detail="Job not found")
    return rows[0]

async def append_job_input(*, job_id: str, user_id: str, input_entry: dict) -> dict:
    job = await get_job_owned(job_id=job_id, user_id=user_id)
    inputs = job.get("input_urls") or []
    inputs.append(input_entry)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.patch(
            f"{_rest_base()}/jobs",
            headers=_headers_service(),
            params={"id": f"eq.{job_id}", "user_id": f"eq.{user_id}", "select": "*"},
            json={"input_urls": inputs},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to update inputs: {resp.text}")

    return resp.json()[0]


async def update_job_fields(*, job_id: str, user_id: str, fields: dict) -> dict:
    """Patch arbitrary fields on a job row and return the updated row."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.patch(
            f"{_rest_base()}/jobs",
            headers=_headers_service(),
            params={"id": f"eq.{job_id}", "user_id": f"eq.{user_id}", "select": "*"},
            json=fields,
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to update job: {resp.text}")

    return resp.json()[0]


async def set_job_status(*, job_id: str, user_id: str, status: str, error: str | None = None) -> dict:
    payload = {"status": status}
    # Explicitly set/clear error if provided
    if error is not None:
        payload["error"] = error
    return await update_job_fields(job_id=job_id, user_id=user_id, fields=payload)


async def append_job_outputs(*, job_id: str, user_id: str, outputs: list[dict]) -> dict:
    """Append output entries to a job's output_urls array."""
    job = await get_job_owned(job_id=job_id, user_id=user_id)
    existing = job.get("output_urls") or []
    updated = existing + outputs
    return await update_job_fields(job_id=job_id, user_id=user_id, fields={"output_urls": updated})

