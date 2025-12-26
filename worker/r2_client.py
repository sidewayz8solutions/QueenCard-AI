import boto3
import os

# Normalize endpoint: allow either the full URL or just the account ID
_endpoint_raw = os.environ.get("R2_ENDPOINT", "").strip()
if _endpoint_raw and not _endpoint_raw.startswith("http"):
    # Treat as Cloudflare account ID and build the URL
    _endpoint_url = f"https://{_endpoint_raw}.r2.cloudflarestorage.com"
else:
    _endpoint_url = _endpoint_raw

s3 = boto3.client(
    "s3",
    endpoint_url=_endpoint_url,
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",
)

# Accept either R2_BUCKET or R2_BUCKET_NAME
BUCKET = os.environ.get("R2_BUCKET") or os.environ.get("R2_BUCKET_NAME")

def download(key, local_path):
    s3.download_file(BUCKET, key, local_path)

def upload(local_path, key):
    s3.upload_file(local_path, BUCKET, key)

