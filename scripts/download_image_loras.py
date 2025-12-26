#!/usr/bin/env python3
"""
Download SD1.5 IMAGE LoRAs from CivitAI (for image generation, NOT video) and upload to R2.
Run: python scripts/download_image_loras.py

NOTE: These are for SD1.5 image generation. For Wan video LoRAs, use download_video_loras.py
"""

import os
import uuid
import requests
import boto3
from pathlib import Path

# Load .env manually (avoid dotenv issues)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                os.environ.setdefault(key, val)

R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# CivitAI version IDs for popular NSFW LoRAs (verified working)
# Format: (slug, civitai_version_id, filename)
# Download URL: https://civitai.com/api/download/models/{version_id}
LORAS = [
    # Effects - VERIFIED
    ("cumshot", 11914, "cumshot.safetensors"),  # Instant Cumshot v1
    ("ahegao", 8109, "ahegao.safetensors"),  # Ahegao face

    # Poses
    ("doggystyle", 7850, "doggystyle.safetensors"),  # Doggystyle
    ("cowgirl", 9166, "cowgirl.safetensors"),  # Cowgirl position
    ("blowjob", 7261, "blowjob.safetensors"),  # BJ LoRA
    ("spread-legs", 10502, "spread-legs.safetensors"),  # Spread pose

    # Body types
    ("big-breasts", 6891, "big-breasts.safetensors"),  # Big breasts

    # Clothing
    ("lingerie", 9453, "lingerie.safetensors"),  # Lingerie collection
    ("latex", 8234, "latex.safetensors"),  # Latex/shiny
    ("maid-outfit", 6284, "maid-outfit.safetensors"),  # Maid outfit

    # Styles
    ("oiled-body", 12456, "oiled-body.safetensors"),  # Oiled/wet skin

    # Fetish
    ("bondage", 8567, "bondage.safetensors"),  # BDSM bondage
    ("feet", 7123, "feet.safetensors"),  # Foot focus
]


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    )


def download_from_civitai(version_id: int, filename: str) -> Path:
    """Download a LoRA from CivitAI"""
    url = f"https://civitai.com/api/download/models/{version_id}"

    print(f"  Downloading from CivitAI: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # CivitAI API key if you have one (optional but recommended for faster downloads)
    civitai_key = os.getenv("CIVITAI_API_KEY")
    if civitai_key:
        headers["Authorization"] = f"Bearer {civitai_key}"

    response = requests.get(url, headers=headers, stream=True, allow_redirects=True, timeout=300)
    response.raise_for_status()

    # Save to temp file
    temp_dir = Path("/tmp/loras")
    temp_dir.mkdir(exist_ok=True)
    filepath = temp_dir / filename

    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0

    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total_size:
                pct = (downloaded / total_size) * 100
                print(f"\r  Progress: {pct:.1f}% ({downloaded / 1024 / 1024:.1f} MB)", end="", flush=True)

    print()  # New line after progress
    print(f"  Downloaded: {filepath} ({filepath.stat().st_size / 1024 / 1024:.1f} MB)")
    return filepath


def upload_to_r2(local_path: Path, r2_key: str):
    """Upload a file to R2"""
    s3 = get_s3_client()

    print(f"  Uploading to R2: {r2_key}")
    s3.upload_file(
        str(local_path),
        R2_BUCKET_NAME,
        r2_key,
        ExtraArgs={"ContentType": "application/octet-stream"}
    )
    print(f"  ✓ Uploaded: {r2_key}")


def register_lora_in_supabase(lora_data: dict):
    """Register LoRA in Supabase database so it appears in frontend"""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("  ⚠ Skipping DB registration (no Supabase credentials)")
        return False

    url = f"{SUPABASE_URL}/rest/v1/loras"
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"  # Upsert by slug
    }

    # Ensure required fields
    lora_data["is_public"] = True
    lora_data["id"] = lora_data.get("id", str(uuid.uuid4()))

    resp = requests.post(url, headers=headers, json=[lora_data])
    if resp.status_code not in (200, 201):
        print(f"  ⚠ DB registration failed: {resp.text}")
        return False

    print(f"  ✓ Registered in Supabase (is_public=true)")
    return True


def main():
    print("=" * 50)
    print("QueenCard AI - LoRA Downloader")
    print("=" * 50)
    
    if not all([R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME]):
        print("ERROR: Missing R2 credentials in .env")
        print(f"  R2_ENDPOINT: {'✓' if R2_ENDPOINT else '✗'}")
        print(f"  R2_ACCESS_KEY_ID: {'✓' if R2_ACCESS_KEY_ID else '✗'}")
        print(f"  R2_SECRET_ACCESS_KEY: {'✓' if R2_SECRET_ACCESS_KEY else '✗'}")
        print(f"  R2_BUCKET_NAME: {'✓' if R2_BUCKET_NAME else '✗'}")
        return
    
    print(f"\nR2 Bucket: {R2_BUCKET_NAME}")
    print(f"Endpoint: {R2_ENDPOINT}")
    print()
    
    # Determine category from slug
    def get_category(slug):
        if slug in ["cumshot", "ahegao"]:
            return "effect"
        elif slug in ["doggystyle", "cowgirl", "blowjob", "spread-legs"]:
            return "pose"
        elif slug in ["big-breasts"]:
            return "body"
        elif slug in ["lingerie", "latex", "maid-outfit"]:
            return "clothing"
        elif slug in ["oiled-body"]:
            return "style"
        elif slug in ["bondage", "feet"]:
            return "fetish"
        return "other"

    # Download and upload each LoRA
    for slug, version_id, filename in LORAS:
        r2_key = f"loras/{filename}"
        print(f"\n[{slug}]")

        try:
            # Check if already exists in R2
            s3 = get_s3_client()
            already_exists = False
            try:
                s3.head_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
                print(f"  Already exists in R2")
                already_exists = True
            except:
                pass  # Doesn't exist, proceed to download

            if not already_exists:
                # Download from CivitAI
                local_path = download_from_civitai(version_id, filename)

                # Upload to R2
                upload_to_r2(local_path, r2_key)

                # Cleanup
                local_path.unlink()

            # Register in Supabase (always, to ensure DB is in sync)
            lora_meta = {
                "name": slug.replace("-", " ").title(),
                "slug": slug,
                "description": f"SD 1.5 LoRA for {slug.replace('-', ' ')}",
                "r2_key": r2_key,
                "category": get_category(slug),
                "tags": [get_category(slug), "image", "sd15", "nsfw"],
                "trigger_words": [slug.replace("-", " ")],
                "base_model": "sd15",
                "is_nsfw": True,
                "is_public": True,
            }
            register_lora_in_supabase(lora_meta)

        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue
    
    print("\n" + "=" * 50)
    print("Done!")
    print("=" * 50)


if __name__ == "__main__":
    main()

