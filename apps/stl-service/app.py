import os
import json
from typing import Any, Dict

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Generadores de modelos
from models.cable_tray import make_model as make_cable_tray
from models.vesa_adapter import make_model as make_vesa_adapter
from models.router_mount import make_model as make_router_mount

# Storage (igual que ya usas; importa tu utilidad actual)
from utils.storage import Storage

app = FastAPI(title="Teknovashop Forge API", version="0.2.0")

def _origins() -> list[str]:
    raw = os.environ.get("CORS_ALLOW_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "https://teknovashop-app.vercel.app",
        "https://teknovashop.com",
        "http://localhost:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

storage = Storage()

@app.get("/health")
async def health():
    return {"status": "ok"}

# ---------------- Normalización de payload ----------------
def _slug(m: str) -> str:
    return (m or "").strip().lower().replace("_", "-").replace(" ", "-")

def _f(x, d=None):
    try:
        return float(x)
    except Exception:
        return d

def normalize(model_slug: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Acepta formato {model, params:{...}} o claves planas del frontend
    y devuelve un diccionario con las keys que esperan los modelos.
    Convención de ejes: X=length, Y=height, Z=width (como en la preview).
    """
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    top = payload

    if model_slug in ("cable-tray", "cable_tray", "cable"):
        return {
            "length":    _f(params.get("length"),    _f(top.get("length_mm"),    180)),
            "height":    _f(params.get("height"),    _f(top.get("height_mm"),     25)),
            "width":     _f(params.get("width"),     _f(top.get("width_mm"),      60)),
            "thickness": _f(params.get("thickness"), _f(top.get("thickness_mm"),   3)),
            "ventilated": bool(params.get("ventilated", top.get("ventilated", True))),
        }

    if model_slug in ("vesa-adapter", "vesa_adapter", "vesa"):
        v = _f(params.get("vesa_mm"), _f(top.get("vesa_mm"), 100))
        return {
            "vesa_mm":   v,
            "thickness": _f(params.get("thickness"), _f(top.get("thickness_mm"), 4)),
            "clearance": _f(params.get("clearance"), _f(top.get("clearance_mm"), 1)),
            "hole":      _f(params.get("hole"),      _f(top.get("hole_diameter_mm"), 5)),
        }

    if model_slug in ("router-mount", "router_mount", "router"):
        return {
            "router_width":  _f(params.get("width"),     _f(top.get("router_width_mm"), 120)),
            "router_depth":  _f(params.get("depth"),     _f(top.get("router_depth_mm"),  80)),
            "thickness":     _f(params.get("thickness"), _f(top.get("thickness_mm"),      4)),
            "strap_slots":   bool(params.get("strap_slots", top.get("strap_slots", True))),
            "hole":          _f(params.get("hole"),      _f(top.get("hole_diameter_mm"), 4)),
        }

    raise HTTPException(400, detail=f"Modelo no soportado: {model_slug}")

# ---------------- Endpoint principal ----------------
@app.post("/generate")
async def generate(req: Request):
    try:
        payload = await req.json()
    except Exception:
        raise HTTPException(400, detail="JSON inválido")

    model_in = payload.get("model") or payload.get("model_slug") or ""
    model_slug = _slug(model_in)
    params = normalize(model_slug, payload)

    # --- Generar malla con los modelos ---
    try:
        if model_slug in ("cable-tray", "cable_tray", "cable"):
            mesh = make_cable_tray(params)
            folder = "cable-tray"
            fname  = "cable-tray.stl"
        elif model_slug in ("vesa-adapter", "vesa_adapter", "vesa"):
            mesh = make_vesa_adapter(params)
            folder = "vesa-adapter"
            fname  = "vesa-adapter.stl"
        elif model_slug in ("router-mount", "router_mount", "router"):
            mesh = make_router_mount(params)
            folder = "router-mount"
            fname  = "router-mount.stl"
        else:
            raise HTTPException(400, detail=f"Modelo no soportado: {model_slug}")

        stl_bytes = mesh.export(file_type="stl")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=f"Error generando STL: {e}")

    # --- Subir a Supabase y firmar URL (igual que antes) ---
    try:
        signed = storage.upload_stl_and_sign(
            stl_bytes,
            filename=fname,
            model_folder=folder,
            expires_in=3600,
        )
        return {"status": "ok", "stl_url": signed}
    except Exception as e:
        raise HTTPException(500, detail=f"Error subiendo a storage: {e}")
