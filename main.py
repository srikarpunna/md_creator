"""Vercel entrypoint — API routes only; static files served from public/."""
from app.api import app  # noqa: F401
