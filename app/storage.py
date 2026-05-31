import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

SAS_EXPIRY_MINUTES = 10


def azure_configured() -> bool:
    return bool(os.getenv("AZURE_STORAGE_CONNECTION_STRING"))


def container_name() -> str:
    return os.getenv("AZURE_STORAGE_CONTAINER", "temp-uploads")


def _parse_connection_string(conn_str: str) -> tuple[str, str]:
    parts = dict(item.split("=", 1) for item in conn_str.split(";") if "=" in item)
    account = parts.get("AccountName")
    key = parts.get("AccountKey")
    if not account or not key:
        raise ValueError("Invalid Azure storage connection string")
    return account, key


def _client() -> BlobServiceClient:
    conn_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    return BlobServiceClient.from_connection_string(conn_str)


def create_upload_url(filename: str) -> tuple[str, str]:
    ext = Path(filename).suffix.lower()
    blob_name = f"uploads/{uuid.uuid4()}{ext}"
    conn_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    account_name, account_key = _parse_connection_string(conn_str)
    container = container_name()

    sas = generate_blob_sas(
        account_name=account_name,
        container_name=container,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(create=True, write=True),
        expiry=datetime.now(timezone.utc) + timedelta(minutes=SAS_EXPIRY_MINUTES),
        protocol="https",
    )

    upload_url = (
        f"https://{account_name}.blob.core.windows.net/"
        f"{container}/{blob_name}?{sas}"
    )
    return upload_url, blob_name


def download_blob(blob_name: str) -> bytes:
    client = _client()
    blob = client.get_blob_client(container=container_name(), blob=blob_name)
    return blob.download_blob().readall()


def delete_blob(blob_name: str) -> None:
    client = _client()
    blob = client.get_blob_client(container=container_name(), blob=blob_name)
    blob.delete_blob(delete_snapshots="include")
