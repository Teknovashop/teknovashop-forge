# apps/stl-service/asgi.py
import os
from typing import List

from starlette.middleware.cors import CORSMiddleware

# Importa TU app existente sin tocarla
# Debe existir en apps/stl-service/app.py una variable `app = FastAPI()`
from app import app as base_app


def _parse_allowlist() -> List[str]:
    """
    Lee CORS_ALLOW_ORIGINS del entorno y devuelve una lista de orígenes permitidos.
    - ""  (vacío)  -> lista vacía => no se permite ningún origen (seguro por defecto)
    - "*"          -> permite todos (NO recomendado en producción)
    - "https://a.com, https://b.com" -> lista de orígenes exactos
    """
    raw = (os.getenv("CORS_ALLOW_ORIGINS") or "").strip()
    if not raw:
        return []  # cerrado por defecto
    if raw == "*":
        return ["*"]
    # normaliza, sin barra final
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def _configure_cors():
    allowlist = _parse_allowlist()

    # NOTA DE SEGURIDAD:
    # - Si allowlist == ["*"] => abierto (solo para pruebas). Evita esto en producción.
    # - Si allowlist == []    => cerrado (ningún origen del navegador puede llamar)
    # - En prod, usa dominios exactos: ["https://tu-frontend.vercel.app"]

    base_app.add_middleware(
        CORSMiddleware,
        allow_origins=allowlist if allowlist != ["*"] else ["*"],
        allow_credentials=True,
        allow_methods=["POST", "OPTIONS"],          # solo lo que usas
        allow_headers=["content-type", "authorization"],
        expose_headers=[],                           # ajusta si necesitas exponer alguno
        max_age=86400,                               # cache del preflight
    )


# Aplica CORS sobre tu app existente
_configure_cors()

# Expone `app` para Uvicorn
app = base_app
