from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
from typing import Any, Dict, Optional

from supabase import create_client, Client


# ------------------------------
# Config FastAPI + CORS
# ------------------------------
app = FastAPI()

origins_raw = os.getenv("CORS_ALLOW_ORIGINS", "*")
ALLOWED_ORIGINS = [o.strip() for o in origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# Supabase
# ------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL y/o SUPABASE_SERVICE_KEY no están definidos.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def _first_of(d: Dict[str, Any], *keys: str) -> Optional[Any]:
    """
    Utilidad para extraer el primer valor disponible entre distintas claves,
    soportando respuestas de distintas versiones (ej: 'signedUrl', 'signedURL', 'publicUrl', etc.).
    """
    if not isinstance(d, dict):
        return None
    for k in keys:
        if k in d:
            return d[k]
    return None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/generate")
async def generate(request: Request):
    """
    Genera un STL de prueba y lo sube a Supabase. Devuelve una URL firmada por 1 hora.
    """
    # Si quieres leer parámetros del body (modelo, medidas, etc.)
    # data = await request.json()

    # STL de prueba (dummy)
    fake_stl = b"""solid cube
  facet normal 0 0 0
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 0 1 0
    endloop
  endfacet
endsolid cube
"""

    # Nombre único
    filename = f"{uuid.uuid4()}.stl"

    # ---- Subida al bucket ----
    # En v2, upload(path, file, file_options)
    # Nota: algunas versiones aceptan 'x-upsert': 'true' para sobrescribir.
    file_options = {"content-type": "model/stl", "x-upsert": "true"}

    upload_res = supabase.storage.from_(SUPABASE_BUCKET).upload(
        filename, fake_stl, file_options=file_options
    )

    # Manejo de error según v2 (atributo .error)
    if getattr(upload_res, "error", None):
        # Estructura típica: upload_res.error.message
        msg = getattr(upload_res.error, "message", str(upload_res.error))
        return {"status": "error", "message": f"Upload failed: {msg}"}

    # ---- URL de descarga ----
    # Opción A: URL firmada (recomendado) -> válida 3600s
    signed_res = supabase.storage.from_(SUPABASE_BUCKET).create_signed_url(
        filename, 3600
    )
    if getattr(signed_res, "error", None):
        # Fallback: intenta URL pública si el bucket es público
        public_res = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)
        if getattr(public_res, "error", None):
            msg = getattr(signed_res.error, "message", str(signed_res.error))
            return {
                "status": "error",
                "message": f"Signed URL failed: {msg}",
            }

        # Estructuras posibles:
        #   python v2: public_res.data -> {'publicUrl': '...'} o similar
        stl_url = None
        if hasattr(public_res, "data"):
            stl_url = _first_of(
                public_res.data, "publicUrl", "publicURL", "url", "signedUrl", "signedURL"
            )
        if not stl_url:
            # último intento por si la lib devuelve string
            stl_url = str(getattr(public_res, "data", "")) or str(public_res)

        return {"status": "ok", "stl_url": stl_url}

    # signed_res.data puede traer distintas claves según versión
    stl_url = None
    if hasattr(signed_res, "data"):
        stl_url = _first_of(
            signed_res.data, "signedUrl", "signedURL", "publicUrl", "publicURL", "url"
        )
    if not stl_url:
        # último intento por si la lib devuelve string
        stl_url = str(getattr(signed_res, "data", "")) or str(signed_res)

    return {"status": "ok", "stl_url": stl_url}
