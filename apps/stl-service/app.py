import os
import json
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

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
    # Por si quieres permitir solo tu frontend en prod:
    # p.ej. https://teknovashop-app.vercel.app
    default_frontend = os.environ.get("NEXT_PUBLIC_BACKEND_URL", "").strip()
    if default_frontend:
        allow_origins = [default_frontend]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins or ["*"],  # en dev está bien "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = Storage()


# ---------------------------
# Utilidades y Generadores "dummy"
# (sustituye por la lógica real de CadQuery/OpenSCAD cuando toque)
# ---------------------------
def _to_ascii_stl(name: str, lines: list[str]) -> bytes:
    return ("\n".join(["solid " + name] + lines + ["endsolid " + name]) + "\n").encode("utf-8")


def generate_vesa_adapter(params: Dict[str, Any]) -> bytes:
    # Usa los params si quieres reflejarlos
    w = int(params.get("width", 180))
    h = int(params.get("height", 180))
    t = int(params.get("thickness", 6))
    pat = str(params.get("pattern", "100x100"))
    lines = [
        f"  facet normal 0 0 1",
        f"    outer loop",
        f"      vertex {-w/2:.1f} {-h/2:.1f} 0",
        f"      vertex { w/2:.1f} {-h/2:.1f} 0",
        f"      vertex { w/2:.1f} { h/2:.1f} 0",
        f"    endloop",
        f"  endfacet",
        f"  facet normal 0 0 -1",
        f"    outer loop",
        f"      vertex {-w/2:.1f} {-h/2:.1f} {t:.1f}",
        f"      vertex { w/2:.1f} { h/2:.1f} {t:.1f}",
        f"      vertex { w/2:.1f} {-h/2:.1f} {t:.1f}",
        f"    endloop",
        f"  endfacet",
        f"  facet normal 1 0 0",
        f"    outer loop",
        f"      vertex { w/2:.1f} {-h/2:.1f} 0",
        f"      vertex { w/2:.1f} { h/2:.1f} 0",
        f"      vertex { w/2:.1f} {-h/2:.1f} {t:.1f}",
        f"    endloop",
        f"  endfacet",
        f"  facet normal -1 0 0",
        f"    outer loop",
        f"      vertex {-w/2:.1f} {-h/2:.1f} 0",
        f"      vertex {-w/2:.1f} {-h/2:.1f} {t:.1f}",
        f"      vertex {-w/2:.1f} { h/2:.1f} 0",
        f"    endloop",
        f"  endfacet",
        f"  facet normal 0 1 0",
        f"    outer loop",
        f"      vertex {-w/2:.1f} { h/2:.1f} 0",
        f"      vertex { w/2:.1f} { h/2:.1f} 0",
        f"      vertex {-w/2:.1f} { h/2:.1f} {t:.1f}",
        f"    endloop",
        f"  endfacet",
        f"  facet normal 0 -1 0",
        f"    outer loop",
        f"      vertex {-w/2:.1f} {-h/2:.1f} 0",
        f"      vertex {-w/2:.1f} {-h/2:.1f} {t:.1f}",
        f"      vertex { w/2:.1f} {-h/2:.1f} 0",
        f"    endloop",
        f"  endfacet",
        f"  // pattern={pat}",
    ]
    return _to_ascii_stl("vesa_adapter", lines)


def generate_router_mount(params: Dict[str, Any]) -> bytes:
    w = int(params.get("width", 160))
    H = int(params.get("height", 220))
    d = int(params.get("depth", 40))
    t = int(params.get("thickness", 4))
    lines = [
        f"  // router-mount w={w} H={H} d={d} t={t}",
        "  facet normal 0 0 1",
        "    outer loop",
        f"      vertex 0 0 0",
        f"      vertex {w} 0 0",
        f"      vertex {w} {H} 0",
        "    endloop",
        "  endfacet",
    ]
    return _to_ascii_stl("router_mount", lines)


def generate_cable_tray(params: Dict[str, Any]) -> bytes:
    w = int(params.get("width", 60))
    h = int(params.get("height", 25))
    L = int(params.get("length", 180))
    t = int(params.get("thickness", 3))
    slots = bool(params.get("slots", True))
    lines = [
        f"  // cable-tray w={w} h={h} L={L} t={t} slots={slots}",
        "  facet normal 0 0 1",
        "    outer loop",
        f"      vertex 0 0 0",
        f"      vertex {L} 0 0",
        f"      vertex {L} {w} 0",
        "    endloop",
        "  endfacet",
    ]
    return _to_ascii_stl("cable_tray", lines)


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
