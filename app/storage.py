import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

SAS_EXPIRY_MINUTES = 10


def _clean(value: str) -> str:
    return value.strip().strip('"').strip("'").strip()


def _connection_string() -> str:
    return _clean(os.getenv("AZURE_STORAGE_CONNECTION_STRING", ""))


def _account_name() -> str:
    return _clean(os.getenv("AZURE_STORAGE_ACCOUNT_NAME", ""))


def _account_key() -> str:
    return _clean(os.getenv("AZURE_STORAGE_ACCOUNT_KEY", ""))


def azure_configured() -> bool:
    conn = _connection_string()
    if conn.startswith("DefaultEndpointsProtocol=") and "AccountKey=" in conn:
        return True
    return bool(_account_name() and _account_key())


def container_name() -> str:
    return _clean(os.getenv("AZURE_STORAGE_CONTAINER", "temp-uploads"))


def _account_credentials() -> tuple[str, str]:
    conn = _connection_string()
    if conn:
        client = BlobServiceClient.from_connection_string(conn)
        cred = client.credential
        account_key = getattr(cred, "account_key", None)
        if client.account_name and account_key:
            return client.account_name, account_key
        raise ValueError("Connection string is missing AccountName or AccountKey")

    name, key = _account_name(), _account_key()
    if name and key:
        return name, key

    raise ValueError(
        "Set AZURE_STORAGE_CONNECTION_STRING or both "
        "AZURE_STORAGE_ACCOUNT_NAME and AZURE_STORAGE_ACCOUNT_KEY in Vercel"
    )


def _client() -> BlobServiceClient:
    conn = _connection_string()
    if conn:
        return BlobServiceClient.from_connection_string(conn)
    name, key = _account_credentials()
    return BlobServiceClient(
        account_url=f"https://{name}.blob.core.windows.net",
        credential=key,
    )


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
