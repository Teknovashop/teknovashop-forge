import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from utils.storage import Storage

# === builders de los 3 modelos paramétricos (añade los ficheros en /models) ===
from models.vesa_adapter import build as build_vesa
from models.router_mount import build as build_router
from models.cable_tray import build as build_tray

app = FastAPI()

# ---------------------------
# CORS (igual que tu versión)
# ---------------------------
allow_origins = []
cors_env = os.environ.get("CORS_ALLOW_ORIGINS")
if cors_env:
    allow_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
else:
    # Si no hay CORS_ALLOW_ORIGINS, permitimos el FRONT declarado (si existiera).
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/models")
def models_catalog():
    """Catálogo simple de modelos y parámetros aceptados."""
    return {
        "models": {
            "vesa": {
                "desc": "Placa VESA con tetones guía",
                "params": {
                    "plate_w": "mm (default 120)",
                    "plate_h": "mm (default 120)",
                    "plate_t": "mm (default 5)",
                    "vesa":    "75|100|200 (default 100)",
                    "boss_d":  "mm (default 6)",
                    "boss_h":  "mm (default 2)"
                }
            },
            "router": {
                "desc": "Soporte mural en U para router",
                "params": {
                    "inner_w": "mm (default 32)",
                    "inner_h": "mm (default 180)",
                    "wall_t":  "mm (default 3)",
                    "depth":   "mm (default 30)",
                    "brim_t":  "mm (default 10)"
                }
            },
            "tray": {
                "desc": "Canaleta simple para cables",
                "params": {
                    "length":  "mm (default 180)",
                    "inner_w": "mm (default 20)",
                    "inner_h": "mm (default 15)",
                    "wall_t":  "mm (default 2.5)",
                    "base_t":  "mm (default 3)"
                }
            }
        }
    }


@app.post("/generate")
def generate(payload: dict):
    """
    Genera un STL en memoria según el 'model' y 'params' recibidos,
    lo sube al bucket de Supabase y devuelve una URL firmada temporal.
    Body esperado:
    {
      "model": "vesa" | "router" | "tray",
      "params": { ... }   # ver /models para opciones
    }
    """
    model = (payload.get("model") or "vesa").lower()
    params = payload.get("params") or {}

    try:
        if model in ("vesa", "vesa_adapter"):
            stl_bytes = build_vesa(params)
            filename = "vesa-adapter.stl"
        elif model in ("router", "router_mount"):
            stl_bytes = build_router(params)
            filename = "router-mount.stl"
        elif model in ("tray", "cable_tray"):
            stl_bytes = build_tray(params)
            filename = "cable-tray.stl"
        else:
            raise HTTPException(status_code=400, detail=f"Unknown model: {model}")

        # Sube y firma usando tu helper existente (sin cambios al storage)
        signed_url = storage.upload_stl_and_sign(
            stl_bytes,
            filename=filename,
            expires_in=3600  # 1h
        )

        return {"status": "ok", "stl_url": signed_url}

    except HTTPException:
        raise
    except Exception as e:
        # Mantén el formato de error que ya usabas
        return {"status": "error", "detail": f"Generation error: {e}"}
