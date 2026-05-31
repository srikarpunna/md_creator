import io
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from markitdown import MarkItDown, StreamInfo
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Vercel caps request bodies at ~4.5 MB on the free tier
DEFAULT_MAX_MB = "4" if os.getenv("VERCEL") else "25"
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", DEFAULT_MAX_MB)) * 1024 * 1024

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


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "platform": "vercel" if os.getenv("VERCEL") else "local",
        "no_storage": True,
    }


@app.get("/api/formats", response_model=FormatsResponse)
def formats():
    return FormatsResponse(
        extensions=sorted(SUPPORTED_EXTENSIONS),
        max_size_mb=MAX_FILE_SIZE // (1024 * 1024),
    )


@app.post("/api/convert", response_model=ConvertResponse)
async def convert(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    stream = io.BytesIO(content)
    stream_info = StreamInfo(
        extension=ext,
        filename=file.filename,
    )

    try:
        result = get_converter().convert_stream(stream, stream_info=stream_info)
        markdown = result.text_content or ""
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Conversion failed: {exc}",
        ) from exc
    finally:
        stream.close()
        del content

    base_name = Path(file.filename).stem
    return ConvertResponse(markdown=markdown, filename=f"{base_name}.md")
