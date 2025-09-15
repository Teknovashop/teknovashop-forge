import os
import json
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Trimesh models (ya incluidas en el repo)
from models.cable_tray import make_model as make_cable_tray
from models.vesa_adapter import make_model as make_vesa_adapter
from models.router_mount import make_model as make_router_mount

from utils.storage import Storage

app = FastAPI(title="Teknovashop Forge API", version="0.2.0")

# -------- CORS ----------
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

# -------- Normalización de payloads --------
def _slug(model: str) -> str:
    return (model or "").strip().lower().replace(" ", "-").replace("_", "-")

def _num(x: Any, default: Optional[float]=None) -> Optional[float]:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default

def _normalize_params(model_slug: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    # Preferimos 'params' si viene anidado; si no, usamos top-level
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    top = payload

    m = model_slug
    out: Dict[str, Any] = {}

    if m in ("cable-tray", "cable_tray", "cable"):
        out["width"]     = _num(params.get("width"),     _num(top.get("width_mm"), 60))
        out["height"]    = _num(params.get("height"),    _num(top.get("height_mm"), 25))
        out["length"]    = _num(params.get("length"),    _num(top.get("length_mm"), 180))
        out["thickness"] = _num(params.get("thickness"), _num(top.get("thickness_mm"), 3))
        # 'ventilated' en UI -> 'slots' aquí (si tu modelo los usa)
        out["slots"] = bool(params.get("slots", top.get("ventilated", True)))

    elif m in ("vesa-adapter", "vesa_adapter", "vesa"):
        v = _num(params.get("vesa_mm"), _num(top.get("vesa_mm")))
        out["width"]     = _num(params.get("width"),     v if v is not None else 180)
        out["height"]    = _num(params.get("height"),    v if v is not None else 180)
        out["thickness"] = _num(params.get("thickness"), _num(top.get("thickness_mm"), 6))

    elif m in ("router-mount", "router_mount", "router"):
        out["width"]     = _num(params.get("width"),     _num(top.get("router_width_mm"), 160))
        out["depth"]     = _num(params.get("depth"),     _num(top.get("router_depth_mm"), 40))
        out["thickness"] = _num(params.get("thickness"), _num(top.get("thickness_mm"), 4))
        # Altura: si llega la usamos; si no, el modelo pone su default interno
        if _num(params.get("height")) is not None:
            out["height"] = _num(params.get("height"))
        elif _num(top.get("router_height_mm")) is not None:
            out["height"] = _num(top.get("router_height_mm"))
        # Slots/strap (por si los usas más adelante)
        if "strap_slots" in top or "slots" in params:
            out["vent_slots"] = bool(params.get("slots", top.get("strap_slots", True)))

    else:
        raise HTTPException(status_code=400, detail=f"Modelo no soportado: {model_slug}")

    # Limpia None (deja que el modelo aplique defaults)
    return {k: v for k, v in out.items() if v is not None}

@app.post("/generate")
async def generate(req: Request):
    try:
        payload = await req.json()
    except Exception:
        raise HTTPException(400, detail="JSON inválido")

    model_in = payload.get("model") or payload.get("model_slug") or ""
    model_slug = _slug(model_in or "vesa-adapter")

    params = _normalize_params(model_slug, payload)

    # ---- Generación con trimesh ----
    try:
        if model_slug in ("cable-tray", "cable_tray", "cable"):
            mesh = make_cable_tray(params)
            filename = "cable-tray.stl"
            folder = "cable-tray"
        elif model_slug in ("vesa-adapter", "vesa_adapter", "vesa"):
            mesh = make_vesa_adapter(params)
            filename = "vesa-adapter.stl"
            folder = "vesa-adapter"
        elif model_slug in ("router-mount", "router_mount", "router"):
            mesh = make_router_mount(params)
            filename = "router-mount.stl"
            folder = "router-mount"
        else:
            raise HTTPException(400, detail=f"Modelo no soportado: {model_slug}")

        stl_bytes = mesh.export(file_type="stl")  # bytes
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=f"Error generando STL: {e}")

    # ---- Subida a Supabase y URL firmada ----
    try:
        signed = storage.upload_stl_and_sign(
            stl_bytes,
            filename=filename,
            model_folder=folder,
            expires_in=3600,
        )
        return {"status": "ok", "stl_url": signed}
    except Exception as e:
        raise HTTPException(500, detail=f"Error subiendo a storage: {e}")
