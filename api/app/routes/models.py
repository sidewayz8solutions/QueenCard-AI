from fastapi import APIRouter, HTTPException
import httpx

from ..config import settings

router = APIRouter(prefix="/models", tags=["models"])


def _rest_base() -> str:
    return f"{settings.SUPABASE_URL}/rest/v1"


def _headers_service() -> dict:
    return {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


@router.get("")
async def list_models(model_type: str = None):
    """List available base models"""
    params = {
        "select": "*",
        "order": "name.asc",
    }
    
    if model_type:
        params["model_type"] = f"eq.{model_type}"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_rest_base()}/base_models",
            headers=_headers_service(),
            params=params,
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to fetch models: {resp.text}")

    return resp.json()


@router.get("/{slug}")
async def get_model(slug: str):
    """Get a specific model by slug"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_rest_base()}/base_models",
            headers=_headers_service(),
            params={"slug": f"eq.{slug}", "select": "*", "limit": "1"},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to fetch model: {resp.text}")

    rows = resp.json()
    if not rows:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return rows[0]

