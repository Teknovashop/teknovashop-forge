# teknovashop-forge/app.py
import os, uuid, time
from typing import List, Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from models.cable_tray import make_model as make_cable_tray
from models.router_mount import make_model as make_router_mount
from models.vesa_adapter import make_model as make_vesa

# --------- ENV SUPABASE ---------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "forge-stl")
if not SUPABASE_URL or not SUPABASE_KEY:
    print("[WARN] Faltan SUPABASE_URL / SUPABASE_SERVICE_KEY")

# --------- APP ---------
app = FastAPI(title="Teknovashop Forge")

# --------- MODELOS/SCHEMAS ---------
class HoleSpec(BaseModel):
    x_mm: float
    z_mm: float
    d_mm: float = Field(gt=0)

ModelKind = Literal["cable_tray", "router_mount", "vesa_adapter"]

class GenerateReq(BaseModel):
    model: ModelKind

    # Cable tray
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    length_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    ventilated: Optional[bool] = True

    # Agujeros (común a todos los modelos)
    holes: Optional[List[HoleSpec]] = None

    # VESA
    vesa_mm: Optional[float] = None
    clearance_mm: Optional[float] = None
    hole_diameter_mm: Optional[float] = None

    # Router
    router_width_mm: Optional[float] = None
    router_depth_mm: Optional[float] = None
    strap_slots: Optional[bool] = True  # reservado para futuras ranuras

@app.get("/health")
def health():
    return {"ok": True, "ts": int(time.time())}

def upload_to_supabase(path: str, content: bytes, content_type="model/stl") -> str:
    """Sube a Supabase Storage y devuelve Signed URL absoluto."""
    up_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{path}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": content_type,
        "X-Upsert": "true",
    }
    r = httpx.put(up_url, headers=headers, content=content, timeout=30)
    if r.status_code not in (200, 201):
        raise HTTPException(500, f"Supabase upload error: {r.status_code} {r.text}")

    sign_url = f"{SUPABASE_URL}/storage/v1/object/sign/{SUPABASE_BUCKET}/{path}"
    r2 = httpx.post(
        sign_url,
        headers={"Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
        json={"expiresIn": 3600},
        timeout=30,
    )
    if r2.status_code != 200:
        raise HTTPException(500, f"Supabase sign error: {r2.status_code} {r2.text}")

    data = r2.json()
    signed = data.get("signedURL") or data.get("signedUrl")
    if not signed:
        raise HTTPException(500, "No signedURL in Supabase response")
    return f"{SUPABASE_URL}{signed}"

@app.post("/generate")
def generate(req: GenerateReq):
    try:
        if req.model == "cable_tray":
            params = {
                "width": float(req.width_mm or 60),
                "height": float(req.height_mm or 25),
                "length": float(req.length_mm or 180),
                "thickness": float(req.thickness_mm or 3),
                "ventilated": bool(req.ventilated),
                "holes": [h.model_dump() for h in (req.holes or [])],
            }
            mesh = make_cable_tray(params)

        elif req.model == "vesa_adapter":
            params = {
                "vesa_mm": float(req.vesa_mm or 100),
                "thickness": float(req.thickness_mm or 4),
                "clearance": float(req.clearance_mm or 1),
                "hole": float(req.hole_diameter_mm or 5),
                "holes": [h.model_dump() for h in (req.holes or [])],  # <- soporta agujeros extra
            }
            mesh = make_vesa(params)

        elif req.model == "router_mount":
            params = {
                "router_width": float(req.router_width_mm or 120),
                "router_depth": float(req.router_depth_mm or 80),
                "thickness": float(req.thickness_mm or 4),
                "holes": [h.model_dump() for h in (req.holes or [])],  # <- soporta agujeros en base
            }
            mesh = make_router_mount(params)

        else:
            raise HTTPException(400, "Modelo no soportado")

        # Export simple (binario STL)
        stl_bytes: bytes = mesh.export(file_type="stl")

        fname = f"{req.model}/{uuid.uuid4().hex}.stl"
        stl_url = upload_to_supabase(fname, stl_bytes)

        return {"status": "ok", "stl_url": stl_url, "model": req.model}

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR generate:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))
