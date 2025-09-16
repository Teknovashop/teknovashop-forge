# apps/stl-service/app.py
import os, json, datetime, base64
from typing import Any, Dict
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models.cable_tray import make_model as make_cable_tray
from models.vesa_adapter import make_model as make_vesa_adapter
from models.router_mount import make_model as make_router_mount
from utils.storage import Storage
from utils.watermark import add_watermark_plaque

APP_NAME = "Teknovashop Forge API"
APP_VERSION = "0.3.0"

app = FastAPI(title=APP_NAME, version=APP_VERSION)

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
    allow_methods=["GET","POST","OPTIONS"],
    allow_headers=["*"],
)

storage = Storage()

@app.get("/health")
async def health():
    return {"status":"ok","service":APP_NAME,"version":APP_VERSION}

def _slug(m: str) -> str:
    return (m or "").strip().lower().replace("_","-").replace(" ","-")

def _f(x, d=None):
    try: return float(x)
    except Exception: return d

def normalize(model_slug: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    p = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    top = payload

    if model_slug in ("cable-tray","cable_tray","cable"):
        return {
            "length":    _f(p.get("length"),    _f(top.get("length_mm"),    180)),
            "height":    _f(p.get("height"),    _f(top.get("height_mm"),     25)),
            "width":     _f(p.get("width"),     _f(top.get("width_mm"),      60)),
            "thickness": _f(p.get("thickness"), _f(top.get("thickness_mm"),   3)),
            "ventilated": bool(p.get("ventilated", top.get("ventilated", True))),
        }
    if model_slug in ("vesa-adapter","vesa_adapter","vesa"):
        v = _f(p.get("vesa_mm"), _f(top.get("vesa_mm"), 100))
        return {
            "vesa_mm":   v,
            "thickness": _f(p.get("thickness"), _f(top.get("thickness_mm"), 4)),
            "clearance": _f(p.get("clearance"), _f(top.get("clearance_mm"), 1)),
            "hole":      _f(p.get("hole"),      _f(top.get("hole_diameter_mm"), 5)),
        }
    if model_slug in ("router-mount","router_mount","router"):
        return {
            "router_width":  _f(p.get("width"),     _f(top.get("router_width_mm"), 120)),
            "router_depth":  _f(p.get("depth"),     _f(top.get("router_depth_mm"),  80)),
            "thickness":     _f(p.get("thickness"), _f(top.get("thickness_mm"),      4)),
            "strap_slots":   bool(p.get("strap_slots", top.get("strap_slots", True))),
            "hole":          _f(p.get("hole"),      _f(top.get("hole_diameter_mm"), 4)),
        }
    raise HTTPException(400, detail=f"Modelo no soportado: {model_slug}")

def _stl_header_meta(meta: Dict[str, Any]) -> bytes:
    # Añade metadatos simples al header del STL binario (80 bytes)
    blob = json.dumps(meta, separators=(",",":"))[:70].encode("utf-8")
    return blob.ljust(80, b" ")

@app.post("/generate")
async def generate(req: Request):
    try:
        payload = await req.json()
    except Exception:
        raise HTTPException(400, detail="JSON inválido")

    model_slug = _slug(payload.get("model") or payload.get("model_slug") or "")
    if not model_slug:
        raise HTTPException(400, detail="Falta 'model'")

    params = normalize(model_slug, payload)

    # --- Generación ---
    try:
        if model_slug in ("cable-tray","cable_tray","cable"):
            mesh = make_cable_tray(params)
            folder, fname = "cable-tray", "cable-tray.stl"
        elif model_slug in ("vesa-adapter","vesa_adapter","vesa"):
            mesh = make_vesa_adapter(params)
            folder, fname = "vesa-adapter", "vesa-adapter.stl"
        elif model_slug in ("router-mount","router_mount","router"):
            mesh = make_router_mount(params)
            folder, fname = "router-mount", "router-mount.stl"
        else:
            raise HTTPException(400, detail=f"Modelo no soportado: {model_slug}")

        # Marca de agua: plaquita + QR discreto
        lic = payload.get("license_id") or ""
        qr_url = f"https://teknovashop.com/license/{lic}" if lic else "https://teknovashop.com/forge"
        mesh = add_watermark_plaque(mesh, qr_url=qr_url, text="TEKNOVASHOP FORGE")

        # Export binario con header con metadatos
        meta = {
            "model": model_slug,
            "params": params,
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "license_id": lic,
            "ver": APP_VERSION,
        }
        stl_bytes = mesh.export(file_type="stl", header=_stl_header_meta(meta))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=f"Error generando STL: {e}")

    # --- Subida + URL firmada corta ---
    try:
        signed = storage.upload_stl_and_sign(
            stl_bytes,
            filename=fname,
            model_folder=folder,
            expires_in=300,  # 5 minutos
        )
        return {"status":"ok","stl_url": signed}
    except Exception as e:
        raise HTTPException(500, detail=f"Error subiendo a storage: {e}")
