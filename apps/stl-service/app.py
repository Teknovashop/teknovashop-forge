# teknovashop-forge/app.py
import os, uuid, time
from typing import List, Literal, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ---- modelos existentes
from models.cable_tray import make_model as make_cable_tray
from models.router_mount import make_model as make_router_mount
from models.vesa_adapter import make_model as make_vesa

# ---- modelos nuevos
from models.phone_stand import make_model as make_phone_stand
from models.qr_plate import make_model as make_qr_plate
from models.enclosure_ip65 import make_model as make_enclosure_ip65
from models.cable_clip import make_model as make_cable_clip

# ========= ENV SUPABASE =========
SUPABASE_URL = (os.environ.get("SUPABASE_URL", "") or "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY".lower(), "")
SUPABASE_BUCKET = (os.environ.get("SUPABASE_BUCKET", "forge-stl") or "forge-stl").strip("/")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[WARN] Faltan SUPABASE_URL / SUPABASE_SERVICE_KEY")

# ========= APP =========
app = FastAPI(title="Teknovashop Forge")

# ========= SCHEMAS =========
class HoleSpec(BaseModel):
    x_mm: float
    z_mm: float
    d_mm: float = Field(gt=0)
    # campos opcionales del nuevo visor (no los usan los generadores legacy)
    y_mm: Optional[float] = None
    nx: Optional[float] = None
    ny: Optional[float] = None
    nz: Optional[float] = None
    axis: Optional[Literal["auto", "x", "y", "z"]] = "auto"

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

    # genérico
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


# ========= HELPERS =========
def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)

def _holes_to_xzd(holes: Optional[List[HoleSpec]], fallback_d: float) -> List[Tuple[float, float, float]]:
    """
    Normaliza la lista de agujeros a [(x,z,d), ...] con números float.
    Ignora y/normal/axis para no romper los modelos legacy.
    """
    out: List[Tuple[float, float, float]] = []
    if not holes:
        return out
    for h in holes:
        # h ya es HoleSpec (pydantic), pero por si llega “a pelo” desde otro cliente:
        try:
            x = _num(getattr(h, "x_mm", None) if hasattr(h, "x_mm") else h.get("x_mm"))
            z = _num(getattr(h, "z_mm", None) if hasattr(h, "z_mm") else h.get("z_mm"))
            d = _num(getattr(h, "d_mm", None) if hasattr(h, "d_mm") else h.get("d_mm"), fallback_d)
        except Exception:
            # dict raro; intenta claves sueltas
            try:
                x = _num(h["x"])
                z = _num(h["z"])
                d = _num(h.get("d") or fallback_d)
            except Exception:
                # ignora entradas corruptas
                continue
        if d <= 0:
            d = fallback_d
        out.append((x, z, d))
    return out

def _upload_to_supabase(path: str, content: bytes, content_type="application/sla") -> str:
    """
    Sube a Supabase Storage y devuelve Signed URL absoluta, con download=true
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(500, "Storage no configurado (SUPABASE_URL / SUPABASE_SERVICE_KEY)")

    safe_key = path.strip("/")

    put_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{safe_key}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": content_type,
        "X-Upsert": "true",
    }
    r = httpx.put(put_url, headers=headers, content=content, timeout=60)
    if r.status_code not in (200, 201):
        raise HTTPException(500, f"Supabase upload error: {r.status_code} {r.text}")

    sign_url = f"{SUPABASE_URL}/storage/v1/object/sign/{SUPABASE_BUCKET}/{safe_key}"
    r2 = httpx.post(
        sign_url,
        headers={
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
        json={"expiresIn": 3600, "download": True},
        timeout=30,
    )
    if r2.status_code != 200:
        raise HTTPException(500, f"Supabase sign error: {r2.status_code} {r2.text}")

    data = r2.json()
    signed = data.get("signedURL") or data.get("signedUrl")
    if not signed:
        raise HTTPException(500, "No signedURL in Supabase response")
    # firmado es un path relativo que ya incluye token; anteponer base
    return f"{SUPABASE_URL}{signed}"


# ========= ENDPOINTS =========
@app.get("/health")
def health():
    return {"ok": True, "ts": int(time.time())}

@app.post("/generate")
def generate(req: GenerateReq):
    try:
        model_id = req.model

        if model_id == "cable_tray":
            holes = _holes_to_xzd(req.holes, fallback_d=_num(req.hole_diameter_mm, 5))
            params = {
                "width": _num(req.width_mm, 60),
                "height": _num(req.height_mm, 25),
                "length": _num(req.length_mm, 180),
                "thickness": _num(req.thickness_mm, 3),
                "ventilated": bool(req.ventilated),
                "holes": holes,
            }
            mesh = make_cable_tray(params)

        elif model_id == "vesa_adapter":
            holes = _holes_to_xzd(req.holes, fallback_d=_num(req.hole_diameter_mm, 5))
            params = {
                "vesa_mm": _num(req.vesa_mm, 100),
                "thickness": _num(req.thickness_mm, 5),
                "clearance": _num(req.clearance_mm, 1),
                "hole": _num(req.hole_diameter_mm, 5),
                "holes": holes,
            }
            mesh = make_vesa(params)

        elif model_id == "router_mount":
            holes = _holes_to_xzd(req.holes, fallback_d=_num(req.hole_diameter_mm, 5))
            params = {
                "router_width": _num(req.router_width_mm, 120),
                "router_depth": _num(req.router_depth_mm, 80),
                "thickness": _num(req.thickness_mm, 4),
                "ventilated": bool(req.ventilated),
                "holes": holes,
            }
            mesh = make_router_mount(params)

        elif model_id == "phone_stand":
            # este no usa holes
            params = {
                "angle_deg": _num(req.angle_deg, 60),
                "support_depth": _num(req.support_depth, 110),
                "width": _num(req.width, 80),
                "thickness": _num(req.thickness_mm, 4),
            }
            mesh = make_phone_stand(params)

        elif model_id == "qr_plate":
            holes = _holes_to_xzd(req.holes, fallback_d=_num(req.hole_diameter_mm, 5))
            params = {
                "length": _num(req.length_mm, 90),
                "width": _num(req.width, 38),
                "thickness": _num(req.thickness_mm, 8),
                "slot_mm": _num(req.slot_mm, 22),
                "screw_d_mm": _num(req.screw_d_mm, 6.5),
                "holes": holes,
            }
            mesh = make_qr_plate(params)

        elif model_id == "enclosure_ip65":
            holes = _holes_to_xzd(req.holes, fallback_d=_num(req.hole_diameter_mm, 5))
            params = {
                "length": _num(req.box_length if req.box_length is not None else req.length_mm, 201),
                "width": _num(req.box_width if req.box_width is not None else req.width, 68),
                "height": _num(req.box_height if req.box_height is not None else req.height_mm, 31),
                "wall": _num(req.wall_mm if req.wall_mm is not None else req.thickness_mm, 5),
                "ventilated": bool(req.ventilated),
                "holes": holes,
            }
            mesh = make_enclosure_ip65(params)

        elif model_id == "cable_clip":
            # sin holes
            params = {
                "diameter": _num(req.clip_diameter, 8),
                "width": _num(req.clip_width, 12),
                "thickness": _num(req.thickness_mm, 2.4),
            }
            mesh = make_cable_clip(params)

        else:
            raise HTTPException(400, "Modelo no soportado")

        # Export STL binario
        stl_bytes: bytes = mesh.export(file_type="stl")
        fname = f"{model_id}/{uuid.uuid4().hex}.stl"
        stl_url = _upload_to_supabase(fname, stl_bytes, content_type="application/sla")

        return {"status": "ok", "stl_url": stl_url, "model": model_id}

    except HTTPException:
        raise
    except Exception as e:
        # imprime para logs de Render
        print("ERROR generate:", repr(e))
        # propaga mensaje al cliente
        raise HTTPException(status_code=500, detail=str(e))
