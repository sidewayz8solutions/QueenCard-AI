"""
LoRA Registry - Register trained/downloaded LoRAs in Supabase.

This module allows the worker to register new LoRAs in the database
after training completes, making them visible in the frontend.
"""
import os
import uuid
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


def register_lora(
    name: str,
    slug: str,
    r2_key: str,
    description: str = "",
    category: str = "custom",
    tags: list = None,
    trigger_words: list = None,
    base_model: str = "sd15",
    is_nsfw: bool = True,
    owner_id: str = None,
) -> bool:
    """
    Register a LoRA in Supabase database.
    
    Args:
        name: Display name (e.g., "My Custom LoRA")
        slug: URL-safe identifier (e.g., "my-custom-lora")
        r2_key: R2 storage key (e.g., "loras/my-lora.safetensors")
        description: Optional description
        category: Category (custom, style, character, etc.)
        tags: List of tags
        trigger_words: List of trigger words
        base_model: Base model (sd15, wan21, etc.)
        is_nsfw: Whether the LoRA is NSFW
        owner_id: Optional owner user ID (for private LoRAs)
    
    Returns:
        True if registration succeeded, False otherwise
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print(f"[lora_registry] No Supabase credentials, skipping DB registration")
        return False
    
    url = f"{SUPABASE_URL}/rest/v1/loras"
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    
    lora_data = {
        "id": str(uuid.uuid4()),
        "name": name,
        "slug": slug,
        "description": description,
        "r2_key": r2_key,
        "category": category,
        "tags": tags or [],
        "trigger_words": trigger_words or [],
        "base_model": base_model,
        "is_nsfw": is_nsfw,
        "is_public": owner_id is None,  # Public if no owner
    }
    
    if owner_id:
        lora_data["owner_id"] = owner_id
    
    try:
        resp = requests.post(url, headers=headers, json=[lora_data], timeout=10)
        if resp.status_code in (200, 201):
            print(f"[lora_registry] Registered '{slug}' in Supabase")
            return True
        else:
            print(f"[lora_registry] Failed to register '{slug}': {resp.text}")
            return False
    except Exception as e:
        print(f"[lora_registry] Error registering '{slug}': {e}")
        return False


def register_trained_lora(
    user_id: str,
    lora_name: str,
    r2_key: str,
    base_model: str = "sd15",
    trigger_words: list = None,
) -> bool:
    """
    Register a user-trained LoRA after training completes.
    
    Args:
        user_id: The user who trained the LoRA
        lora_name: Name given by user
        r2_key: R2 key where the LoRA was uploaded
        base_model: Base model it was trained on
        trigger_words: Trigger words for the LoRA
    
    Returns:
        True if registration succeeded
    """
    slug = lora_name.lower().replace(" ", "-").replace("_", "-")
    # Make slug unique with user prefix
    slug = f"user-{user_id[:8]}-{slug}"
    
    return register_lora(
        name=lora_name,
        slug=slug,
        r2_key=r2_key,
        description=f"Custom trained LoRA by user",
        category="custom",
        tags=["custom", "trained", base_model],
        trigger_words=trigger_words or [],
        base_model=base_model,
        is_nsfw=True,
        owner_id=user_id,
    )

