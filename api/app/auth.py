from fastapi import Header, HTTPException
import httpx
from .config import settings

async def get_user_id(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty Bearer token")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.SUPABASE_ANON_KEY,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")

    data = resp.json()
    user_id = data.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token valid but user id missing")

    return user_id

