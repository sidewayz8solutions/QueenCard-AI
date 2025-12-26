#!/usr/bin/env python3
"""
Download popular NSFW LoRAs from CivitAI and upload to R2.
Run: python scripts/download_loras.py
"""

import os
import requests
import boto3
from pathlib import Path
from dotenv import load_dotenv

# Load .env from api directory
load_dotenv("api/.env")

R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")

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
    
    # Download and upload each LoRA
    for slug, version_id, filename in LORAS:
        r2_key = f"loras/{filename}"
        print(f"\n[{slug}]")
        
        try:
            # Check if already exists in R2
            s3 = get_s3_client()
            try:
                s3.head_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
                print(f"  Already exists in R2, skipping...")
                continue
            except:
                pass  # Doesn't exist, proceed to download
            
            # Download from CivitAI
            local_path = download_from_civitai(version_id, filename)
            
            # Upload to R2
            upload_to_r2(local_path, r2_key)
            
            # Cleanup
            local_path.unlink()
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue
    
    print("\n" + "=" * 50)
    print("Done!")
    print("=" * 50)


if __name__ == "__main__":
    main()

