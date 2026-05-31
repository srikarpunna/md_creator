import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas
from fastapi import HTTPException

SAS_EXPIRY_MINUTES = 10


def is_configured() -> bool:
    return bool(os.getenv("AZURE_STORAGE_CONNECTION_STRING"))


def _container() -> str:
    return os.getenv("AZURE_STORAGE_CONTAINER", "temp-uploads")


def _parse_connection_string() -> tuple[str, str]:
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    parts = dict(part.split("=", 1) for part in conn_str.split(";") if "=" in part)
    account_name = parts.get("AccountName")
    account_key = parts.get("AccountKey")
    if not account_name or not account_key:
        raise HTTPException(status_code=500, detail="Invalid Azure storage connection string")
    return account_name, account_key


def _client() -> BlobServiceClient:
    return BlobServiceClient.from_connection_string(os.environ["AZURE_STORAGE_CONNECTION_STRING"])


def create_upload_url(filename: str, size: int, max_size: int) -> dict[str, str]:
    if size <= 0:
        raise HTTPException(status_code=400, detail="File is empty")
    if size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {max_size // (1024 * 1024)} MB.",
        )

    ext = Path(filename).suffix.lower()
    blob_name = f"{uuid.uuid4().hex}{ext}"
    container = _container()
    account_name, account_key = _parse_connection_string()

    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=container,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(create=True, write=True),
        expiry=datetime.now(timezone.utc) + timedelta(minutes=SAS_EXPIRY_MINUTES),
    )

    upload_url = (
        f"https://{account_name}.blob.core.windows.net/"
        f"{container}/{blob_name}?{sas_token}"
    )
    return {"upload_url": upload_url, "blob_name": blob_name}


def download_blob(blob_name: str) -> bytes:
    if not blob_name or ".." in blob_name or "/" in blob_name or "\\" in blob_name:
        raise HTTPException(status_code=400, detail="Invalid blob name")

    blob_client = _client().get_blob_client(container=_container(), blob=blob_name)
    if not blob_client.exists():
        raise HTTPException(status_code=404, detail="Upload not found or expired")

    return blob_client.download_blob().readall()


def delete_blob(blob_name: str) -> None:
    blob_client = _client().get_blob_client(container=_container(), blob=blob_name)
    blob_client.delete_blob(delete_snapshots="include")
