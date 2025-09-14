import os
import json
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from utils.storage import Storage
from utils.stl_writer import triangles_to_stl
from models.vesa_adapter import make_model as make_vesa_adapter
from models.router_mount import make_model as make_router_mount
from models.cable_tray import make_model as make_cable_tray


app = FastAPI(title="Teknovashop Forge")

# ---------------------------
# CORS
# ---------------------------
allow_origins: list[str] = []
cors_env = os.environ.get("CORS_ALLOW_ORIGINS")
if cors_env:
    allow_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
else:
    # En producción puedes fijarlo a tu frontend, p.ej.:
    # https://teknovashop-app.vercel.app
    default_frontend = os.environ.get("NEXT_PUBLIC_BACKEND_URL", "").strip()
    if default_frontend:
        allow_origins = [default_frontend]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins or ["*"],  # en dev, "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = Storage()  # Supabase Storage helper


# ---------------------------
# Model registry
# ---------------------------
MODEL_BUILDERS = {
    "vesa-adapter": make_vesa_adapter,
    "vesa_adapter": make_vesa_adapter,
    "vesa": make_vesa_adapter,
    "router-mount": make_router_mount,
    "router_mount": make_router_mount,
    "router": make_router_mount,
    "cable-tray": make_cable_tray,
    "cable_tray": make_cable_tray,
    "cable": make_cable_tray,
}


# ---------------------------
# Rutas
# ---------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate")
async def generate(request: Request):
    """
    Espera JSON:
    {
      "model": "vesa-adapter" | "router-mount" | "cable-tray",
      "params": { ... },
      "order_id": "...",
      "license": "personal" | "commercial"
    }
    """
    try:
        payload = await request.json()
    except Exception:
        return {"status": "error", "detail": "Invalid JSON"}

    # Permitir 'model' o 'model_slug'
    model_slug = (payload.get("model") or payload.get("model_slug") or "").strip().lower()
    if not model_slug:
        return {"status": "error", "detail": "Missing 'model'."}

    params: Dict[str, Any] = payload.get("params", {}) or {}
    order_id = (payload.get("order_id") or "").strip()
    license_type = (payload.get("license") or "personal").strip().lower()

    builder = MODEL_BUILDERS.get(model_slug)
    if not builder:
        return {"status": "error", "detail": f"Unknown model '{model_slug}'"}

    try:
        # Construir triangulación (lista de triángulos), cada triángulo = ((x,y,z),(x,y,z),(x,y,z))
        triangles = builder(params)

        # Pasar a STL ASCII
        stl_bytes = triangles_to_stl(triangles, solid_name=model_slug)

        # Nombre de fichero
        filename = f"{model_slug}.stl"

        # Subir y firmar URL (1h)
        url = storage.upload_stl_and_sign(stl_bytes, filename=filename, expires_in=3600)

        return {
            "status": "ok",
            "stl_url": url,
            "meta": {
                "model": model_slug,
                "order_id": order_id or None,
                "license": license_type,
            },
        }

    except Exception as e:
        return {"status": "error", "detail": f"Upload error: {e}"}
