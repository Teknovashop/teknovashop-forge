from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import os
import time

from utils.storage import Storage

app = FastAPI()

# CORS
_allowed = os.getenv("CORS_ALLOW_ORIGINS", "")
ALLOWED_ORIGINS = [o.strip() for o in _allowed.split(",") if o.strip()]
if not ALLOWED_ORIGINS:
    # Por seguridad, si no hay variable, permite solo el propio dominio de Render
    # y localhost (útil en pruebas). Ajusta si quieres algo más estricto.
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://teknovashop-app.vercel.app",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- Schemas ---------
class GeneratePayload(BaseModel):
    order_id: str = "test-order-123"
    model_slug: str = "vase-adapter"
    # params aquí si los necesitas
    params: dict | None = None


# --------- Health ---------
@app.get("/health")
def health():
    return {"ok": True, "ts": int(time.time())}


# --------- Generar STL ---------
@app.post("/generate")
def generate(body: GeneratePayload):
    try:
        # TODO: aquí iría tu lógica real para crear el STL en memoria.
        # Para demo, genero bytes mínimos válidos para un STL binario vacío
        # (encabezado de 80 bytes + uint32 de 0 triángulos = 84 bytes).
        header = b"Teknovashop STL".ljust(80, b"\x00")
        tri_count = (0).to_bytes(4, "little")
        stl_bytes = header + tri_count

        # Nombre único
        object_path = f"forge-stl/{body.order_id}.stl"

        storage = Storage()
        signed_url = storage.upload_stl_and_get_signed_url(
            data=stl_bytes,
            object_path=object_path,
            content_type="application/sla",
            expires_in_seconds=3600,
            upsert=True,  # << esto ahora va dentro de FileOptions en utils.storage
        )

        return {"status": "ok", "stl_url": signed_url}

    except Exception as e:
        # Devuelve el error al frontend para poder ver rápido qué pasa
        raise HTTPException(status_code=500, detail=str(e))
