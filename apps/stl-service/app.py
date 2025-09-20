# teknovashop-forge/app.py
import os, uuid, time, math
from typing import List, Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# modelos existentes
from models.cable_tray import make_model as make_cable_tray
from models.router_mount import make_model as make_router_mount
from models.vesa_adapter import make_model as make_vesa

# nuevos
from models.phone_stand import make_model as make_phone_stand
from models.qr_plate import make_model as make_qr_plate
from models.enclosure_ip65 import make_model as make_enclosure_ip65
from models.cable_clip import make_model as make_cable_clip


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
    # centro del agujero en milímetros (sistema de escena)
    x_mm: float
    z_mm: float
    y_mm: Optional[float] = None  # nuevo: altura exacta del pick
    d_mm: float = Field(gt=0)
    # orientación: si no viene o es "auto", se calcula con la normal
    axis: Optional[Literal["auto", "x", "y", "z"]] = "auto"
    # normal de la cara pickeada (opcional pero útil)
    nx: Optional[float] = None
    ny: Optional[float] = None
    nz: Optional[float] = None


ModelKind = Literal[
    "cable_tray",
    "router_mount",
    "vesa_adapter",
    "phone_stand",
    "qr_plate",
    "enclosure_ip65",
    "cable_clip",
]


class GenerateReq(BaseModel):
    model: ModelKind

    # genéricos de placa/soporte
    holes: Optional[List[HoleSpec]] = None
    thickness_mm: Optional[float] = None
    ventilated: Optional[bool] = True

    # Cable tray
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    length_mm: Optional[float] = None

    # VESA
    vesa_mm: Optional[float] = None
    clearance_mm: Optional[float] = None
    hole_diameter_mm: Optional[float] = None

    # Router
    router_width_mm: Optional[float] = None
    router_depth_mm: Optional[float] = None

    # Phone stand
    angle_deg: Optional[float] = None
    support_depth: Optional[float] = None
    width: Optional[float] = None

    # QR plate
    slot_mm: Optional[float] = None
    screw_d_mm: Optional[float] = None

    # Enclosure
    wall_mm: Optional[float] = None
    box_length: Optional[float] = None
    box_width: Optional[float] = None
    box_height: Optional[float] = None

    # Cable clip
    clip_diameter: Optional[float] = None
    clip_width: Optional[float] = None


@app.get("/health")
def health():
    return {"ok": True, "ts": int(time.time())}


# --------- HELPERS ---------
def _auto_axis_from_normal(nx: Optional[float], ny: Optional[float], nz: Optional[float]) -> str:
    """
    Decide el eje del taladro según la normal:
    - |ny| máximo  -> 'y'
    - |nx| máximo  -> 'x'
    - |nz| máximo  -> 'z'
    Si no hay normal válida, por defecto 'y'.
    """
    comps = [
        ("x", abs(nx) if nx is not None else -1.0),
        ("y", abs(ny) if ny is not None else -1.0),
        ("z", abs(nz) if nz is not None else -1.0),
    ]
    # si ninguna tiene valor >=0, devolvemos y
    if max(c for _, c in comps) < 0:
        return "y"
    comps.sort(key=lambda p: p[1], reverse=True)
    return comps[0][0]


def _hole_to_dict(h: HoleSpec) -> dict:
    axis = h.axis or "auto"
    if axis == "auto":
        axis = _auto_axis_from_normal(h.nx, h.ny, h.nz)
    return {
        "x_mm": float(h.x_mm),
        "y_mm": float(h.y_mm if h.y_mm is not None else 0.0),
        "z_mm": float(h.z_mm),
        "d_mm": float(h.d_mm),
        "axis": axis,      # 'x' | 'y' | 'z'
        "nx": h.nx,
        "ny": h.ny,
        "nz": h.nz,
    }


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


# --------- ENDPOINT PRINCIPAL ---------
@app.post("/generate")
def generate(req: GenerateReq):
    try:
        # Normaliza agujeros una vez aquí
        norm_holes = [_hole_to_dict(h) for h in (req.holes or [])]

        if req.model == "cable_tray":
            params = {
                "width": float(req.width_mm or 60),
                "height": float(req.height_mm or 25),
                "length": float(req.length_mm or 180),
                "thickness": float(req.thickness_mm or 3),
                "ventilated": bool(req.ventilated),
                "holes": norm_holes,
            }
            mesh = make_cable_tray(params)

        elif req.model == "vesa_adapter":
            params = {
                "vesa_mm": float(req.vesa_mm or 100),
                "thickness": float(req.thickness_mm or 4),
                "clearance": float(req.clearance_mm or 1),
                "hole": float(req.hole_diameter_mm or 5),
                "holes": norm_holes,
            }
            mesh = make_vesa(params)

        elif req.model == "router_mount":
            params = {
                "router_width": float(req.router_width_mm or 120),
                "router_depth": float(req.router_depth_mm or 80),
                "thickness": float(req.thickness_mm or 4),
                "holes": norm_holes,
            }
            mesh = make_router_mount(params)

        elif req.model == "phone_stand":
            params = {
                "angle_deg": float(req.angle_deg or 60),
                "support_depth": float(req.support_depth or 110),
                "width": float(req.width or 80),
                "thickness": float(req.thickness_mm or 4),
                # sin holes por defecto (base inclinada, no perforamos)
            }
            mesh = make_phone_stand(params)

        elif req.model == "qr_plate":
            params = {
                "length": float(req.length_mm or 90),
                "width": float(req.width or 38),
                "thickness": float(req.thickness_mm or 8),
                "slot_mm": float(req.slot_mm or 22),
                "screw_d_mm": float(req.screw_d_mm or 6.5),
                "holes": norm_holes,
            }
            mesh = make_qr_plate(params)

        elif req.model == "enclosure_ip65":
            params = {
                "length": float(req.box_length or req.length_mm or 201),
                "width": float(req.box_width or req.width or 68),
                "height": float(req.box_height or req.height_mm or 31),
                "wall": float(req.wall_mm or req.thickness_mm or 5),
                "holes": norm_holes,
            }
            mesh = make_enclosure_ip65(params)

        elif req.model == "cable_clip":
            params = {
                "diameter": float(req.clip_diameter or 8),
                "width": float(req.clip_width or 12),
                "thickness": float(req.thickness_mm or 2.4),
                # normalmente sin holes
            }
            mesh = make_cable_clip(params)

        else:
            raise HTTPException(400, "Modelo no soportado")

        # Export STL binario
        stl_bytes: bytes = mesh.export(file_type="stl")

        fname = f"{req.model}/{uuid.uuid4().hex}.stl"
        stl_url = upload_to_supabase(fname, stl_bytes)

        return {"status": "ok", "stl_url": stl_url, "model": req.model}

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR generate:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))
