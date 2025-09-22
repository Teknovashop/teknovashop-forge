# teknovashop-forge/app.py
import os, uuid, time
from typing import List, Literal, Optional, Tuple, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# --------- MODELOS ---------
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
if not SUPABASE_BUCKET:
    print("[WARN] Falta SUPABASE_BUCKET; usando 'forge-stl' por defecto")

# --------- APP ---------
app = FastAPI(title="Teknovashop Forge")

# --------- SCHEMAS ---------
class HoleSpec(BaseModel):
    x_mm: float
    z_mm: float
    d_mm: float = Field(gt=0)
    y_mm: Optional[float] = None
    nx: Optional[float] = None
    ny: Optional[float] = None
    nz: Optional[float] = None
    axis: Optional[Literal["auto","x","y","z"]] = "auto"

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

    # genéricos
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
    length_mm_qr: Optional[float] = None
    width_mm_qr: Optional[float] = None

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


# ---------- Helpers ----------
def normalize_holes(holes_in: Optional[List[HoleSpec]]) -> Dict[str, Any]:
    """
    Devuelve tres variantes compatibles:
      - holes_legacy: List[Tuple[x, z, d]]
      - holes:       List[Dict{x,z,d}]
      - holes_xyz:   List[Dict{x,y,z,d,nx,ny,nz,axis}]
    Todas las magnitudes ya en mm (floats).
    """
    holes_legacy: List[Tuple[float, float, float]] = []
    holes_list: List[Dict[str, float]] = []
    holes_xyz: List[Dict[str, float]] = []

    for h in holes_in or []:
        # Pydantic model -> dict
        d = h.model_dump()
        x = float(d.get("x_mm", 0.0))
        z = float(d.get("z_mm", 0.0))
        y = float(d.get("y_mm", 0.0) or 0.0)
        dia = float(d.get("d_mm", 0.0))
        nx = float(d.get("nx", 0.0) or 0.0)
        ny = float(d.get("ny", 0.0) or 1.0)  # por defecto vertical
        nz = float(d.get("nz", 0.0) or 0.0)
        axis = d.get("axis", "auto") or "auto"

        holes_legacy.append((x, z, dia))
        holes_list.append({"x": x, "z": z, "d": dia})
        holes_xyz.append({"x": x, "y": y, "z": z, "d": dia, "nx": nx, "ny": ny, "nz": nz, "axis": axis})

    return {
        "holes_legacy": holes_legacy,
        "holes": holes_list,
        "holes_xyz": holes_xyz,
    }


def upload_to_supabase(path: str, content: bytes, content_type="model/stl") -> str:
    """Sube a Supabase Storage y devuelve Signed URL absoluto."""
    up_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{path}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": content_type,
        "X-Upsert": "true",
    }
    r = httpx.put(up_url, headers=headers, content=content, timeout=60)
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


# ---------- Endpoint principal ----------
@app.post("/generate")
def generate(req: GenerateReq):
    try:
        holes_norm = normalize_holes(req.holes)

        if req.model == "cable_tray":
            params = {
                "width": float(req.width_mm or 60),
                "height": float(req.height_mm or 25),
                "length": float(req.length_mm or 180),
                "thickness": float(req.thickness_mm or 3),
                "ventilated": bool(req.ventilated),
                # compatibilidad máxima
                "holes": holes_norm["holes"],
                "holes_legacy": holes_norm["holes_legacy"],
                "holes_xyz": holes_norm["holes_xyz"],
            }
            mesh = make_cable_tray(params)

        elif req.model == "vesa_adapter":
            params = {
                "vesa_mm": float(req.vesa_mm or 100),
                "thickness": float(req.thickness_mm or 4),
                "clearance": float(req.clearance_mm or 1),
                "hole": float(req.hole_diameter_mm or 5),
                "ventilated": bool(req.ventilated),
                "holes": holes_norm["holes"],
                "holes_legacy": holes_norm["holes_legacy"],
                "holes_xyz": holes_norm["holes_xyz"],
            }
            mesh = make_vesa(params)

        elif req.model == "router_mount":
            params = {
                "router_width": float(req.router_width_mm or 120),
                "router_depth": float(req.router_depth_mm or 80),
                "thickness": float(req.thickness_mm or 4),
                "ventilated": bool(req.ventilated),
                "holes": holes_norm["holes"],
                "holes_legacy": holes_norm["holes_legacy"],
                "holes_xyz": holes_norm["holes_xyz"],
            }
            mesh = make_router_mount(params)

        elif req.model == "phone_stand":
            params = {
                "angle_deg": float(req.angle_deg or 60),
                "support_depth": float(req.support_depth or 110),
                "width": float(req.width or 80),
                "thickness": float(req.thickness_mm or 4),
                # este modelo normalmente no usa agujeros, pero los pasamos por si procede
                "holes": holes_norm["holes"],
                "holes_xyz": holes_norm["holes_xyz"],
            }
            mesh = make_phone_stand(params)

        elif req.model == "qr_plate":
            params = {
                "length": float(req.length_mm_qr or req.length_mm or 90),
                "width": float(req.width_mm_qr or req.width or 38),
                "thickness": float(req.thickness_mm or 8),
                "slot_mm": float(req.slot_mm or 22),
                "screw_d_mm": float(req.screw_d_mm or 6.5),
                "ventilated": bool(req.ventilated),
                "holes": holes_norm["holes"],
                "holes_legacy": holes_norm["holes_legacy"],
                "holes_xyz": holes_norm["holes_xyz"],
            }
            mesh = make_qr_plate(params)

        elif req.model == "enclosure_ip65":
            params = {
                "length": float(req.box_length or req.length_mm or 201),
                "width": float(req.box_width or req.width or 68),
                "height": float(req.box_height or req.height_mm or 31),
                "wall": float(req.wall_mm or req.thickness_mm or 5),
                "ventilated": bool(req.ventilated),
                "holes": holes_norm["holes"],
                "holes_legacy": holes_norm["holes_legacy"],
                "holes_xyz": holes_norm["holes_xyz"],
            }
            mesh = make_enclosure_ip65(params)

        elif req.model == "cable_clip":
            params = {
                "diameter": float(req.clip_diameter or 8),
                "width": float(req.clip_width or 12),
                "thickness": float(req.thickness_mm or 2.4),
                "holes": holes_norm["holes"],
                "holes_xyz": holes_norm["holes_xyz"],
            }
            mesh = make_cable_clip(params)

        else:
            raise HTTPException(400, "Modelo no soportado")

        # Export STL binario (Trimesh >=4.4.x)
        # No pasamos kwargs exóticos para evitar fallos de cabecera
        stl_bytes: bytes = mesh.export(file_type="stl")

        fname = f"{req.model}/{uuid.uuid4().hex}.stl"
        stl_url = upload_to_supabase(fname, stl_bytes)

        return {"status": "ok", "stl_url": stl_url, "model": req.model}

    except HTTPException:
        # Re-levanta HTTPException tal cual
        raise
    except Exception as e:
        # Log visible en Render
        print("ERROR generate:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))
