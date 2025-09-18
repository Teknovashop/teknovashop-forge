# asgi.py
"""
ASGI entrypoint para Uvicorn/Render.

Exportamos tanto `fastapi_app` (importado desde app.py) como `app`
para que funcionen indistintamente los comandos:
  - uvicorn asgi:fastapi_app ...
  - uvicorn asgi:app ...
"""
from app import app as fastapi_app

# Alias que usan algunos comandos/plantillas (p.ej. uvicorn asgi:app)
app = fastapi_app
