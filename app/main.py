from pathlib import Path

from fastapi.responses import FileResponse

from app.api import app

PUBLIC_DIR = Path(__file__).parent.parent / "public"


@app.get("/")
async def index():
    return FileResponse(PUBLIC_DIR / "index.html")


@app.get("/style.css")
async def stylesheet():
    return FileResponse(PUBLIC_DIR / "style.css", media_type="text/css")


@app.get("/app.js")
async def script():
    return FileResponse(PUBLIC_DIR / "app.js", media_type="application/javascript")
