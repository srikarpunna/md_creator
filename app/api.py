import io
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from markitdown import MarkItDown, StreamInfo
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app import storage

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "25")) * 1024 * 1024

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
    ".csv", ".json", ".xml", ".html", ".htm", ".txt", ".md",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff",
    ".wav", ".mp3", ".m4a", ".epub", ".zip",
}

app = FastAPI(title="MD Creator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class NoStoreMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-No-Storage"] = "true"
        return response


app.add_middleware(NoStoreMiddleware)

_converter: MarkItDown | None = None


def get_converter() -> MarkItDown:
    global _converter
    if _converter is None:
        _converter = MarkItDown(enable_plugins=False)
    return _converter


class ConvertResponse(BaseModel):
    markdown: str
    filename: str


class FormatsResponse(BaseModel):
    extensions: list[str]
    max_size_mb: int
    blob_upload: bool


class UploadUrlResponse(BaseModel):
    upload_url: str
    blob_name: str


class BlobConvertRequest(BaseModel):
    blob_name: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    size: int = Field(gt=0)


def _validate_file_meta(filename: str, size: int) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )
    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )
    return ext


def _convert_bytes(content: bytes, filename: str, ext: str) -> str:
    stream = io.BytesIO(content)
    stream_info = StreamInfo(extension=ext, filename=filename)
    try:
        result = get_converter().convert_stream(stream, stream_info=stream_info)
        return result.text_content or ""
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Conversion failed: {exc}",
        ) from exc
    finally:
        stream.close()


@app.get("/")
async def index():
    return RedirectResponse("/index.html", status_code=307)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "platform": "vercel" if os.getenv("VERCEL") else "local",
        "no_storage": True,
        "blob_upload": storage.azure_configured(),
    }


@app.get("/api/formats", response_model=FormatsResponse)
def formats():
    return FormatsResponse(
        extensions=sorted(SUPPORTED_EXTENSIONS),
        max_size_mb=MAX_FILE_SIZE // (1024 * 1024),
        blob_upload=storage.azure_configured(),
    )


@app.get("/api/upload-url", response_model=UploadUrlResponse)
def upload_url(filename: str, size: int):
    if not storage.azure_configured():
        raise HTTPException(status_code=501, detail="Blob upload is not configured")

    _validate_file_meta(filename, size)

    try:
        upload_url_value, blob_name = storage.create_upload_url(filename)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not create upload URL: {exc}",
        ) from exc

    return UploadUrlResponse(upload_url=upload_url_value, blob_name=blob_name)


@app.post("/api/convert", response_model=ConvertResponse)
async def convert(file: UploadFile = File(...)):
    if storage.azure_configured():
        raise HTTPException(
            status_code=400,
            detail="Use blob upload: GET /api/upload-url, PUT to Azure, POST /api/convert-blob",
        )
    return await _convert_from_upload(file)


@app.post("/api/convert-blob", response_model=ConvertResponse)
async def convert_blob(payload: BlobConvertRequest):
    return await _convert_from_blob(payload)


async def _convert_from_upload(file: UploadFile) -> ConvertResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    ext = _validate_file_meta(file.filename, len(content))
    markdown = _convert_bytes(content, file.filename, ext)
    base_name = Path(file.filename).stem
    return ConvertResponse(markdown=markdown, filename=f"{base_name}.md")


async def _convert_from_blob(payload: BlobConvertRequest) -> ConvertResponse:
    if not storage.azure_configured():
        raise HTTPException(status_code=501, detail="Blob upload is not configured")

    if not payload.blob_name.startswith("uploads/"):
        raise HTTPException(status_code=400, detail="Invalid blob name")

    ext = _validate_file_meta(payload.filename, payload.size)

    try:
        content = storage.download_blob(payload.blob_name)
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Could not read uploaded file: {exc}",
        ) from exc

    if len(content) != payload.size:
        raise HTTPException(status_code=400, detail="Uploaded file size mismatch")

    try:
        markdown = _convert_bytes(content, payload.filename, ext)
    finally:
        try:
            storage.delete_blob(payload.blob_name)
        except Exception:
            pass

    base_name = Path(payload.filename).stem
    return ConvertResponse(markdown=markdown, filename=f"{base_name}.md")
