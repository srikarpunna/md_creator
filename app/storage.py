import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

SAS_EXPIRY_MINUTES = 10


def _clean_connection_string() -> str:
    raw = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    return raw.strip().strip('"').strip("'").strip()


def azure_configured() -> bool:
    conn = _clean_connection_string()
    return conn.startswith("DefaultEndpointsProtocol=") and "AccountKey=" in conn


def container_name() -> str:
    return os.getenv("AZURE_STORAGE_CONTAINER", "temp-uploads").strip()


def _account_credentials() -> tuple[str, str]:
    conn_str = _clean_connection_string()
    if not azure_configured():
        raise ValueError(
            "AZURE_STORAGE_CONNECTION_STRING must be the full connection string "
            "from Azure Portal → Storage account → Access keys → Connection string"
        )

    client = BlobServiceClient.from_connection_string(conn_str)
    cred = client.credential
    account_key = getattr(cred, "account_key", None)
    if not client.account_name or not account_key:
        raise ValueError("Connection string is missing AccountName or AccountKey")

    return client.account_name, account_key


def _client() -> BlobServiceClient:
    return BlobServiceClient.from_connection_string(_clean_connection_string())


def create_upload_url(filename: str) -> tuple[str, str]:
    ext = Path(filename).suffix.lower()
    blob_name = f"uploads/{uuid.uuid4()}{ext}"
    account_name, account_key = _account_credentials()
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
