import os
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

import trimesh

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
    default_frontend = os.environ.get("NEXT_PUBLIC_BACKEND_URL", "").strip()
    if default_frontend:
        allow_origins = [default_frontend]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins or ["*"],  # en dev: "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = Storage()


# ---------------------------
# Helpers de modelos sencillos (sin triangulación)
# ---------------------------

def _export_mesh_to_stl_bytes(mesh: trimesh.Trimesh) -> bytes:
    """
    Exporta el mesh a STL (binario) de forma compatible entre versiones.
    """
    data = mesh.export(file_type="stl")
    # trimesh devuelve bytes o str; normalizamos a bytes
    return data if isinstance(data, (bytes, bytearray)) else data.encode("utf-8")


def generate_vesa_adapter(params: Dict[str, Any]) -> bytes:
    """
    Placeholder: placa rectangular (w x h) con espesor t.
    Evitamos agujeros para no requerir triangulación ni booleanas.
    """
    w = float(params.get("width", 180))
    h = float(params.get("height", 180))
    t = float(params.get("thickness", 6))

    # Box centrado (X=w, Y=h, Z=t)
    mesh = trimesh.creation.box(extents=[w, h, t])
    return _export_mesh_to_stl_bytes(mesh)


def generate_router_mount(params: Dict[str, Any]) -> bytes:
    """
    Placeholder: placa base (w x H) con espesor t.
    """
    w = float(params.get("width", 160))
    H = float(params.get("height", 220))
    t = float(params.get("thickness", 4))

    mesh = trimesh.creation.box(extents=[w, H, t])
    return _export_mesh_to_stl_bytes(mesh)


def generate_cable_tray(params: Dict[str, Any]) -> bytes:
    """
    Placeholder: canaleta como prisma rectangular (L x w x t).
    (Ignoramos "slots" aquí para mantenerlo simple y robusto)
    """
    w = float(params.get("width", 60))
    h = float(params.get("height", 25))
    L = float(params.get("length", 180))
    t = float(params.get("thickness", 3))

    # Representamos la canaleta como una "L" gruesa simplificada:
    # base (L x w x t) + pared (L x t x h) → unimos con concatenate
    base = trimesh.creation.box(extents=[L, w, t])
    wall = trimesh.creation.box(extents=[L, t, h])

    # Colocamos la pared en un borde de la base
    wall.apply_translation([0, (w - t) / 2.0, (h - t) / 2.0])

    mesh = trimesh.util.concatenate([base, wall])
    return _export_mesh_to_stl_bytes(mesh)


# ---------------------------
# Rutas
# ---------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate")
async def generate(request: Request):
    """
    Input JSON:
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

    model = (payload.get("model") or payload.get("model_slug") or "").strip().lower()
    if not model:
        model = "vesa-adapter"

    params = payload.get("params", {}) or {}
    filename = "forge-output.stl"

    try:
        if model in ("vesa-adapter", "vesa_adapter", "vesa"):
            stl_bytes = generate_vesa_adapter(params)
            filename = "vesa-adapter.stl"
        elif model in ("router-mount", "router_mount", "router"):
            stl_bytes = generate_router_mount(params)
            filename = "router-mount.stl"
        elif model in ("cable-tray", "cable_tray", "cable"):
            stl_bytes = generate_cable_tray(params)
            filename = "cable-tray.stl"
        else:
            return {"status": "error", "detail": f"Unknown model '{model}'"}

        url = storage.upload_stl_and_sign(stl_bytes, filename=filename, expires_in=3600)
        return {"status": "ok", "stl_url": url}

    except Exception as e:
        return {"status": "error", "detail": f"Upload error: {e}"}
