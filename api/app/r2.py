import boto3
from botocore.config import Config
from .config import settings

def r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )

def presign_put(*, key: str, content_type: str, expires_seconds: int = 600) -> str:
    s3 = r2_client()
    return s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.R2_BUCKET_NAME, "Key": key, "ContentType": content_type},
        ExpiresIn=expires_seconds,
    )

def presign_get(*, key: str, expires_seconds: int = 1800) -> str:
    s3 = r2_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.R2_BUCKET_NAME, "Key": key},
        ExpiresIn=expires_seconds,
    )

