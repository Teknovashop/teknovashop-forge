import io
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from utils.storage import Storage

import os

app = FastAPI()

# CORS
allow_origins = []
cors_env = os.environ.get("CORS_ALLOW_ORIGINS")
if cors_env:
    # Permite coma separada o un solo valor
    allow_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
else:
    # Por defecto, permite tu app de Vercel (ajústalo si usas otro dominio)
    # Ejemplo: https://teknovashop-app.vercel.app
    default_frontend = os.environ.get("NEXT_PUBLIC_BACKEND_URL", "").strip()
    if default_frontend:
        allow_origins = [default_frontend]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins or ["*"],   # en desarrollo puedes dejar "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = Storage()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate")
def generate():
    """
    Endpoint de prueba: genera un "STL" mínimo en memoria y lo sube.
    Sustituye por tu lógica real de generación.
    """
    # STL mínimo (o usa tu binario real)
    fake_stl = b"solid cube\nendsolid cube\n"
    try:
        url = storage.upload_stl_and_sign(fake_stl, filename="forge-output.stl", expires_in=3600)
        return {"status": "ok", "stl_url": url}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
