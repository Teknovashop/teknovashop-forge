# teknovashop-forge/app.py
import os, uuid, time
from typing import List, Literal, Optional, Tuple, Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from models.cable_tray import make_model as make_cable_tray
from models.router_mount import make_model as make_router_mount
from models.vesa_adapter import make_model as make_vesa
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
    x_mm: float
    z_mm: float
    d_mm: float = Field(gt=0)
    # extras que puede mandar el front (se ignoran para makers antiguos)
    y_mm: Optional[float] = None
    nx: Optional[float] = None
    ny: Optional[float] = None
    nz: Optional[float] = None
    axis: Optional[str] = None

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

# ---------- helpers ----------
def _as_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

def holes_canonize(holes_any: Optional[Any]) -> List[Tuple[float, float, float]]:
    """
    Acepta:
      - None
      - List[HoleSpec] (pydantic)
      - List[dict] con claves x_mm/z_mm/d_mm o x/z/d
      - List[tuple|list] de 3 números
    Devuelve: List[(x,z,d)]
    """
    res: List[Tuple[float, float, float]] = []
    if not holes_any:
        return res
    for h in holes_any:
        # HoleSpec -> dict
        if hasattr(h, "model_dump"):
            h = h.model_dump()
        if isinstance(h, dict):
            x = h.get("x_mm", h.get("x"))
            z = h.get("z_mm", h.get("z"))
            d = h.get("d_mm", h.get("d") or h.get("diameter"))
            res.append((_as_float(x), _as_float(z), _as_float(d)))
        elif isinstance(h, (list, tuple)) and len(h) >= 3:
            res.append((_as_float(h[0]), _as_float(h[1]), _as_float(h[2])))
        else:
            # ignora silenciosamente formatos desconocidos
            continue
    return res

def upload_to_supabase(path: str, content: bytes, content_type="model/stl") -> str:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(500, "Supabase no configurado")

    path = path.lstrip("/")
    put_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{path}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": content_type,
        "X-Upsert": "true",
    }
    r = httpx.put(put_url, headers=headers, content=content, timeout=30)
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
                "width": _as_float(req.width_mm or 60),
                "height": _as_float(req.height_mm or 25),
                "length": _as_float(req.length_mm or 180),
                "thickness": _as_float(req.thickness_mm or 3),
                "ventilated": bool(req.ventilated),
                "holes": holes_canonize(req.holes),
            }
            mesh = make_cable_tray(params)

        elif req.model == "vesa_adapter":
            params = {
                "vesa_mm": _as_float(req.vesa_mm or 100),
                "thickness": _as_float(req.thickness_mm or 4),
                "clearance": _as_float(req.clearance_mm or 1),
                "hole": _as_float(req.hole_diameter_mm or 5),
                "holes": holes_canonize(req.holes),
            }
            mesh = make_vesa(params)

        elif req.model == "router_mount":
            params = {
                "router_width": _as_float(req.router_width_mm or 120),
                "router_depth": _as_float(req.router_depth_mm or 80),
                "thickness": _as_float(req.thickness_mm or 4),
                "holes": holes_canonize(req.holes),
            }
            mesh = make_router_mount(params)

        elif req.model == "phone_stand":
            angle_val = _as_float(req.angle_deg or 60)
            depth_val = _as_float(req.support_depth or 110)
            params = {
                "angle_deg": angle_val,
                "angle": angle_val,            # compat
                "support_depth": depth_val,
                "depth": depth_val,            # compat
                "width": _as_float(req.width or 80),
                "thickness": _as_float(req.thickness_mm or 4),
            }
            mesh = make_phone_stand(params)

        elif req.model == "qr_plate":
            params = {
                "length": _as_float(req.length_mm or 90),
                "width": _as_float(req.width or 38),
                "thickness": _as_float(req.thickness_mm or 8),
                "slot_mm": _as_float(req.slot_mm or 22),
                "screw_d_mm": _as_float(req.screw_d_mm or 6.5),
                "holes": holes_canonize(req.holes),
            }
            mesh = make_qr_plate(params)

        elif req.model == "enclosure_ip65":
            params = {
                "length": _as_float(req.box_length or req.length_mm or 201),
                "width": _as_float(req.box_width or req.width or 68),
                "height": _as_float(req.box_height or req.height_mm or 31),
                "wall": _as_float(req.wall_mm or req.thickness_mm or 5),
                "holes": holes_canonize(req.holes),
            }
            mesh = make_enclosure_ip65(params)

        elif req.model == "cable_clip":
            params = {
                "diameter": _as_float(req.clip_diameter or 8),
                "width": _as_float(req.clip_width or 12),
                "thickness": _as_float(req.thickness_mm or 2.4),
            }
            mesh = make_cable_clip(params)

        else:
            raise HTTPException(400, "Modelo no soportado")

        stl_bytes: bytes = mesh.export(file_type="stl")
        if not stl_bytes:
            raise HTTPException(500, "STL vacío")

        fname = f"{req.model}/{uuid.uuid4().hex}.stl"
        stl_url = upload_to_supabase(fname, stl_bytes)
        return {"status": "ok", "stl_url": stl_url, "model": req.model}

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR generate:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))
