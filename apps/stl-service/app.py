# apps/stl-service/app.py
import io
import os
import time
from typing import Optional, Dict, Any

from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware

from utils.storage import Storage
from models import MODEL_REGISTRY  # <- registro de generadores


app = FastAPI(title="Teknovashop Forge - STL Service")


# ---------- CORS ----------
allow_origins = []
cors_env = os.environ.get("CORS_ALLOW_ORIGINS")
if cors_env:
    allow_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
else:
    default_frontend = os.environ.get("NEXT_PUBLIC_BACKEND_URL", "").strip()
    if default_frontend:
        allow_origins = [default_frontend]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins or ["*"],  # en desarrollo puedes dejar "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = Storage()


# ---------- RUTAS ----------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate")
def generate(payload: Dict[str, Any] = Body(default={})):
    """
    Endpoint general de generación STL.

    Body esperado (ejemplos):
      { "model": "vesa", "params": { "width": 120, "height": 120, "thickness": 5 } }

    Si no se especifica 'model', genera el cubo mínimo anterior para mantener compatibilidad.
    """
    model: Optional[str] = payload.get("model")
    params: Dict[str, Any] = payload.get("params", {}) or {}

    try:
        if model:
            generator = MODEL_REGISTRY.get(model)
            if not generator:
                return {"status": "error", "detail": f"Unknown model '{model}'"}

            stl_bytes = generator(params)
            filename = f"{model}-{int(time.time())}.stl"
        else:
            # Compatibilidad con tu prueba anterior: cubo mínimo
            stl_bytes = b"solid cube\nendsolid cube\n"
            filename = f"forge-output-{int(time.time())}.stl"

        url = storage.upload_stl_and_sign(
            stl_bytes,
            filename=filename,
            expires_in=3600,
        )
        return {"status": "ok", "stl_url": url}

    except Exception as e:
        return {"status": "error", "detail": f"{type(e).__name__}: {e}"}
