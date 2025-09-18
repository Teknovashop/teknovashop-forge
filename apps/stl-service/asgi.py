# teknovashop-forge/asgi.py
"""
ASGI entrypoint para Uvicorn/Render.
Permite usar `uvicorn asgi:app` o `uvicorn asgi:fastapi_app`.
"""
from app import app as fastapi_app
app = fastapi_app
