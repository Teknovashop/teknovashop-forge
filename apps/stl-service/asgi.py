"""
Wrapper ASGI para exponer `app` a Uvicorn / Render.
"""
from app import app  # noqa: F401  (exporta `app`)
