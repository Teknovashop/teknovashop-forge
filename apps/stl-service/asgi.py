# apps/stl-service/asgi.py
import os
from starlette.middleware.cors import CORSMiddleware

# Importa tu FastAPI ya existente
from app import app as fastapi_app


def _parse_origins(val: str | None) -> list[str]:
    """
    Convierte la env CORS_ALLOW_ORIGINS en lista.
    - Admite una URL o varias separadas por coma.
    - Recorta espacios y elimina '/' final.
    """
    if not val:
        return []
    return [o.strip().rstrip('/') for o in val.split(',') if o.strip()]


# Lee la variable de entorno (en Render)
ALLOWED_ORIGINS = _parse_origins(os.getenv("CORS_ALLOW_ORIGINS"))

# Aplica CORS a la app que ya tienes
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],     # necesario para que el preflight no falle
    allow_headers=["*"],     # idem
)

# Uvicorn servirá este `app`
app = fastapi_app
