from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import httpx

from ..config import settings
from ..auth import get_user_id

router = APIRouter(prefix="/loras", tags=["loras"])


def _rest_base() -> str:
    return f"{settings.SUPABASE_URL}/rest/v1"


def _headers_service() -> dict:
    return {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


class LoraResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str]
    preview_url: Optional[str]
    category: str
    tags: list[str]
    trigger_words: list[str]
    base_model: str
    is_nsfw: bool


@router.get("")
async def list_loras(
    category: Optional[str] = None,
    is_nsfw: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, le=100),
    offset: int = 0,
):
    """List available LoRAs"""
    params = {
        "select": "id,name,slug,description,preview_url,category,tags,trigger_words,base_model,is_nsfw,download_count",
        "is_public": "eq.true",
        "order": "download_count.desc",
        "limit": str(limit),
        "offset": str(offset),
    }
    
    if category:
        params["category"] = f"eq.{category}"
    if is_nsfw is not None:
        params["is_nsfw"] = f"eq.{str(is_nsfw).lower()}"
    if search:
        params["name"] = f"ilike.%{search}%"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_rest_base()}/loras",
            headers=_headers_service(),
            params=params,
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to fetch loras: {resp.text}")

    return resp.json()


@router.get("/categories")
async def list_categories():
    """List all LoRA categories"""
    return [
        {"slug": "realistic", "name": "Realistic", "description": "Photorealistic styles"},
        {"slug": "anime", "name": "Anime", "description": "Anime and manga styles"},
        {"slug": "celebrity", "name": "Celebrity", "description": "Celebrity likenesses"},
        {"slug": "character", "name": "Character", "description": "Fictional characters"},
        {"slug": "style", "name": "Style", "description": "Art styles and aesthetics"},
        {"slug": "clothing", "name": "Clothing", "description": "Outfits and fashion"},
        {"slug": "pose", "name": "Pose", "description": "Specific poses and positions"},
    ]


@router.get("/{slug}")
async def get_lora(slug: str):
    """Get a specific LoRA by slug"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_rest_base()}/loras",
            headers=_headers_service(),
            params={"slug": f"eq.{slug}", "select": "*", "limit": "1"},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to fetch lora: {resp.text}")

    rows = resp.json()
    if not rows:
        raise HTTPException(status_code=404, detail="LoRA not found")
    
    return rows[0]


@router.post("/{slug}/download")
async def increment_download(slug: str, user_id: str = Depends(get_user_id)):
    """Increment download count for a LoRA"""
    async with httpx.AsyncClient(timeout=10) as client:
        # Get current count
        resp = await client.get(
            f"{_rest_base()}/loras",
            headers=_headers_service(),
            params={"slug": f"eq.{slug}", "select": "id,download_count,r2_key"},
        )
        
        if resp.status_code != 200 or not resp.json():
            raise HTTPException(status_code=404, detail="LoRA not found")
        
        lora = resp.json()[0]
        new_count = (lora.get("download_count") or 0) + 1
        
        # Update count
        await client.patch(
            f"{_rest_base()}/loras",
            headers=_headers_service(),
            params={"id": f"eq.{lora['id']}"},
            json={"download_count": new_count},
        )
    
    return {"r2_key": lora["r2_key"], "download_count": new_count}

