from __future__ import annotations
import os
import uuid

from app.config import get_settings

settings = get_settings()


def save_upload(content: bytes, filename: str, subdir: str = "kyc") -> str:
    """Persist an uploaded file; returns a URL/path the API can serve back."""
    safe = f"{uuid.uuid4().hex}_{os.path.basename(filename)}"
    if settings.STORAGE_BACKEND == "s3":
        import boto3

        s3 = boto3.client(
            "s3",
            region_name=settings.S3_REGION or None,
            endpoint_url=settings.S3_ENDPOINT or None,
        )
        key = f"{subdir}/{safe}"
        s3.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=content)
        return f"s3://{settings.S3_BUCKET}/{key}"
    dest_dir = os.path.join(settings.STORAGE_DIR, subdir)
    os.makedirs(dest_dir, exist_ok=True)
    with open(os.path.join(dest_dir, safe), "wb") as fh:
        fh.write(content)
    return f"/files/{subdir}/{safe}"
