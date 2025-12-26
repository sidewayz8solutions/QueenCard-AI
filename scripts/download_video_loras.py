#!/usr/bin/env python3
"""
Download NSFW Video LoRAs for Wan 2.1/2.2 from CivitAI and upload to R2.
These are VIDEO LoRAs specifically trained for Wan video generation models.

REQUIRES: CivitAI API key for NSFW content downloads.
Get your API key at: https://civitai.com/user/account (Settings > API Keys)

Run: CIVITAI_API_KEY=your_key python scripts/download_video_loras.py
Or add CIVITAI_API_KEY to your .env file
"""

import os
import sys
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
CIVITAI_API_KEY = os.getenv("CIVITAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# VERIFIED Wan 2.1/2.2 VIDEO LoRAs from CivitAI
# Format: (slug, civitai_version_id, filename, expected_size_mb, trigger_words)

VIDEO_LORAS = [
    # === GENERAL NSFW (CubeyAI) ===
    # Model: https://civitai.com/models/1307155
    ("nsfw-22-high", "2073605", "NSFW-22-H-e8.safetensors", 585,
     "nsfwsks, descriptive prompting for sex acts"),
    ("nsfw-22-low", "2083303", "NSFW-22-L-e8.safetensors", 585,
     "nsfwsks, descriptive prompting for sex acts"),
    ("nsfw-21", "1475095", "wan-nsfw-e14-fixed.safetensors", 585,
     "nsfwsks, missionary, doggy, cowgirl, blowjob"),
    
    # === CUMSHOT LoRAs (dtwr434) ===
    # Model: https://civitai.com/models/1350447
    ("cumshot-22-high", "2077123", "wan2.2_highnoise_cumshot_v.1.0.safetensors", 293,
     "cum shoots out of the man's penis and lands on her face/chest/pussy"),
    ("cumshot-22-low", "2077119", "wan2.2_lownoise_cumshot_v1.0.safetensors", 293,
     "cum shoots out of the man's penis and lands on her face/chest/pussy"),
    ("cumshot-21-t2v", "1525363", "wan_cumshot.safetensors", 293,
     "cum shoots out, man stroking his penis"),
    ("cumshot-21-i2v", "1602715", "wan_cumshot_i2v.safetensors", 343,
     "cum shoots from off screen, I2V cumshot"),
    
    # === FACIAL / BUKKAKE LoRA (aipinups69) ===
    # Model: https://civitai.com/models/1364982
    ("facial-21", "1542133", "facials_epoch_50.safetensors", 293,
     "thick whitish translucent semen, cum on face, bukkake"),
]


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    )


def download_from_civitai(version_id: str, filename: str, expected_mb: int) -> Path:
    """Download a LoRA from CivitAI with API key authentication"""
    url = f"https://civitai.com/api/download/models/{version_id}"
    print(f"  Downloading: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Authorization": f"Bearer {CIVITAI_API_KEY}",
    }
    
    response = requests.get(url, headers=headers, stream=True, allow_redirects=True, timeout=600)
    response.raise_for_status()
    
    # Check content type - should NOT be HTML
    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type:
        raise ValueError("CivitAI returned HTML instead of file. Check your API key or model access.")
    
    temp_dir = Path("/tmp/video_loras")
    temp_dir.mkdir(exist_ok=True)
    filepath = temp_dir / filename
    
    total_size = int(response.headers.get("content-length", 0))
    downloaded = 0
    
    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total_size:
                pct = (downloaded / total_size) * 100
                print(f"\r  Progress: {pct:.1f}% ({downloaded/1024/1024:.1f}MB)", end="", flush=True)
    
    actual_mb = filepath.stat().st_size / 1024 / 1024
    print(f"\n  Downloaded: {actual_mb:.1f}MB")
    
    # Validate file size (should be close to expected)
    if actual_mb < expected_mb * 0.5:
        raise ValueError(f"File too small ({actual_mb:.1f}MB vs expected ~{expected_mb}MB). Likely HTML error page.")
    
    # Validate it's a safetensors file (starts with specific bytes)
    with open(filepath, "rb") as f:
        header = f.read(8)
        if header[:1] == b"<" or b"<!DOCTYPE" in header:
            raise ValueError("Downloaded file is HTML, not a safetensors model")
    
    return filepath


def upload_to_r2(local_path: Path, r2_key: str):
    """Upload to R2"""
    s3 = get_s3_client()
    print(f"  Uploading to R2: {r2_key}")
    s3.upload_file(str(local_path), R2_BUCKET_NAME, r2_key)
    print(f"  ✓ Uploaded!")


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
    print("=" * 60)
    print("QueenCard AI - Wan 2.1/2.2 Video LoRA Downloader")
    print("=" * 60)
    
    if not CIVITAI_API_KEY:
        print("\n❌ ERROR: CIVITAI_API_KEY is required for NSFW downloads!")
        print("\nTo get an API key:")
        print("1. Go to https://civitai.com/user/account")
        print("2. Click 'Add API Key' under Settings")
        print("3. Add to .env: CIVITAI_API_KEY=your_key_here")
        print("\nOr run with: CIVITAI_API_KEY=your_key python scripts/download_video_loras.py")
        sys.exit(1)
    
    if not all([R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME]):
        print("❌ ERROR: Missing R2 credentials in .env")
        sys.exit(1)
    
    print(f"\nR2 Bucket: {R2_BUCKET_NAME}")
    print("Downloading VIDEO LoRAs for Wan 2.1/2.2 (NOT SD image LoRAs)\n")
    
    registry = []
    
    for slug, version_id, filename, expected_mb, triggers in VIDEO_LORAS:
        r2_key = f"video-loras/{filename}"
        print(f"\n[{slug}] (version: {version_id})")

        # Parse trigger words into list
        trigger_list = [t.strip() for t in triggers.split(",") if t.strip()]

        try:
            s3 = get_s3_client()
            already_exists = False
            try:
                obj = s3.head_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
                size_mb = obj["ContentLength"] / 1024 / 1024
                if size_mb > expected_mb * 0.5:
                    print(f"  Already in R2 ({size_mb:.1f}MB)")
                    already_exists = True
                else:
                    print(f"  Invalid file in R2 ({size_mb:.1f}MB), re-downloading...")
                    s3.delete_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
            except:
                pass

            if not already_exists:
                local_path = download_from_civitai(version_id, filename, expected_mb)
                upload_to_r2(local_path, r2_key)
                local_path.unlink()

            # Register in Supabase (always, to ensure DB is in sync)
            lora_meta = {
                "name": slug.replace("-", " ").title(),
                "slug": slug,
                "description": f"Wan 2.1/2.2 video LoRA: {triggers}",
                "r2_key": r2_key,
                "category": "video",
                "tags": ["video", "wan", "nsfw"],
                "trigger_words": trigger_list,
                "base_model": "wan21",
                "is_nsfw": True,
                "is_public": True,
            }
            register_lora_in_supabase(lora_meta)
            registry.append((slug, r2_key, triggers))

        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("LORA_REGISTRY for worker/video_inference.py:")
    print("=" * 60)
    print("LORA_REGISTRY = {")
    for slug, key, triggers in registry:
        print(f'    "{slug}": "{key}",  # {triggers}')
    print("}")


if __name__ == "__main__":
    main()
