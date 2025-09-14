import os
import json
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Modelos
from models.vesa_adapter import make_model as make_vesa_adapter
from models.router_mount import make_model as make_router_mount
from models.cable_tray import make_model as make_cable_tray

# Export STL
from trimesh.exchange import stl as stl_io

# Storage (Supabase)
from utils.storage import Storage


app = FastAPI()

# ---------------------------
# CORS
# ---------------------------
allow_origins = []
cors_env = os.environ.get("CORS_ALLOW_ORIGINS")
if cors_env:
    allow_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
else:
    # En prod puedes permitir sólo tu frontend (p.ej. https://teknovashop-app.vercel.app)
    default_frontend = os.environ.get("NEXT_PUBLIC_BACKEND_URL", "").strip()
    if default_frontend:
        allow_origins = [default_frontend]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins or ["*"],  # en dev acepta "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = Storage()

# ---------------------------
# Dispatcher de modelos
# ---------------------------
MODEL_BUILDERS = {
    # VESA
    "vesa-adapter": make_vesa_adapter,
    "vesa_adapter": make_vesa_adapter,
    "vesa": make_vesa_adapter,
    # Router mount
    "router-mount": make_router_mount,
    "router_mount": make_router_mount,
    "router": make_router_mount,
    # Cable tray
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
    Recibe JSON:
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
    model = (payload.get("model") or payload.get("model_slug") or "").strip().lower()
    if not model:
        model = "vesa-adapter"  # fallback razonable

    params = payload.get("params", {}) or {}

    builder = MODEL_BUILDERS.get(model)
    if not builder:
        return {"status": "error", "detail": f"Unknown model '{model}'"}

    # Nombre de archivo por modelo
    filename_map = {
        "vesa-adapter": "vesa-adapter.stl",
        "vesa_adapter": "vesa-adapter.stl",
        "vesa": "vesa-adapter.stl",
        "router-mount": "router-mount.stl",
        "router_mount": "router-mount.stl",
        "router": "router-mount.stl",
        "cable-tray": "cable-tray.stl",
        "cable_tray": "cable-tray.stl",
        "cable": "cable-tray.stl",
    }
    filename = filename_map.get(model, "forge-output.stl")

    try:
        # Crea la malla con el builder elegido
        mesh = builder(params)  # -> trimesh.Trimesh

        # Exporta a STL como bytes (sin kwargs problemáticos)
        stl_bytes = stl_io.export_stl(mesh)

        # Sube y saca URL firmada
        url = storage.upload_stl_and_sign(stl_bytes, filename=filename, expires_in=3600)
        return {"status": "ok", "stl_url": url}

    except Exception as e:
        return {"status": "error", "detail": f"Generation/Upload error: {e}"}
