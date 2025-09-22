# teknovashop-forge/app.py
import os, uuid, time
from typing import List, Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from urllib.parse import quote

# ----- MODELOS EXISTENTES -----
from models.cable_tray import make_model as make_cable_tray
from models.router_mount import make_model as make_router_mount
from models.vesa_adapter import make_model as make_vesa
# ----- NUEVOS MODELOS -----
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
    # opcionalmente, si vienes del visor con normales/eje:
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


def _norm_path(p: str) -> str:
    """Asegura que no hay / inicial, ni //, etc."""
    p = p.strip().lstrip("/")
    while "//" in p:
        p = p.replace("//", "/")
    return p


def upload_to_supabase(path: str, content: bytes, *, download_name: Optional[str] = None) -> str:
    """
    Sube a Supabase Storage y devuelve Signed URL absoluta, con &download=<file>.
    Usa el endpoint moderno de firma; si no está disponible, hace fallback al antiguo.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(500, "Supabase no configurado")

    path = _norm_path(path)
    if not download_name:
        download_name = path.split("/")[-1] or "file.stl"

    # 1) Upload (PUT)
    up_url = f"{SUPABASE_URL}/storage/v1/object/{quote(SUPABASE_BUCKET)}/{quote(path)}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/sla",  # STL binario
        "X-Upsert": "true",
    }
    r = httpx.put(up_url, headers=headers, content=content, timeout=60)
    if r.status_code not in (200, 201):
        raise HTTPException(500, f"Supabase upload error: {r.status_code} {r.text}")

    # 2) Try modern sign endpoint (multiple paths)
    sign_modern = f"{SUPABASE_URL}/storage/v1/object/sign/{quote(SUPABASE_BUCKET)}"
    payload = {"paths": [{"path": path, "expiresIn": 3600}]}
    r2 = httpx.post(
        sign_modern,
        headers={"Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )

    signed_url: Optional[str] = None
    if r2.status_code == 200:
        data = r2.json() or {}
        arr = data.get("signedUrls") or data.get("signedURLs") or []
        if isinstance(arr, list) and len(arr) > 0 and isinstance(arr[0], str):
            signed_url = arr[0]

    # 3) Fallback: legacy sign endpoint (single path in URL)
    if not signed_url:
        legacy = f"{SUPABASE_URL}/storage/v1/object/sign/{quote(SUPABASE_BUCKET)}/{quote(path)}"
        r3 = httpx.post(
            legacy,
            headers={"Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
            json={"expiresIn": 3600},
            timeout=30,
        )
        if r3.status_code != 200:
            raise HTTPException(500, f"Supabase sign error: {r3.status_code} {r3.text}")
        data = r3.json()
        signed_url = data.get("signedURL") or data.get("signedUrl")
        if not signed_url:
            raise HTTPException(500, "No signedURL in Supabase response")

    # 4) Asegurar URL absoluta y añadir download=
    if signed_url.startswith("/"):
        signed_url = f"{SUPABASE_URL}{signed_url}"
    # Sugerir descarga con nombre de fichero
    sep = "&" if "?" in signed_url else "?"
    signed_url = f"{signed_url}{sep}download={quote(download_name)}"
    return signed_url


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
                "holes": [h.model_dump() for h in (req.holes or [])],
            }
            mesh = make_vesa(params)

        elif req.model == "router_mount":
            params = {
                "router_width": float(req.router_width_mm or 120),
                "router_depth": float(req.router_depth_mm or 80),
                "thickness": float(req.thickness_mm or 4),
                "holes": [h.model_dump() for h in (req.holes or [])],
            }
            mesh = make_router_mount(params)

        elif req.model == "phone_stand":
            params = {
                "angle_deg": float(req.angle_deg or 60),
                "support_depth": float(req.support_depth or 110),
                "width": float(req.width or 80),
                "thickness": float(req.thickness_mm or 4),
            }
            mesh = make_phone_stand(params)

        elif req.model == "qr_plate":
            params = {
                "length": float(req.length_mm or 90),
                "width": float(req.width or 38),
                "thickness": float(req.thickness_mm or 8),
                "slot_mm": float(req.slot_mm or 22),
                "screw_d_mm": float(req.screw_d_mm or 6.5),
                "holes": [h.model_dump() for h in (req.holes or [])],
            }
            mesh = make_qr_plate(params)

        elif req.model == "enclosure_ip65":
            params = {
                "length": float(req.box_length or req.length_mm or 201),
                "width": float(req.box_width or req.width or 68),
                "height": float(req.box_height or req.height_mm or 31),
                "wall": float(req.wall_mm or req.thickness_mm or 5),
                "holes": [h.model_dump() for h in (req.holes or [])],
            }
            mesh = make_enclosure_ip65(params)

        elif req.model == "cable_clip":
            params = {
                "diameter": float(req.clip_diameter or 8),
                "width": float(req.clip_width or 12),
                "thickness": float(req.thickness_mm or 2.4),
            }
            mesh = make_cable_clip(params)

        else:
            raise HTTPException(400, "Modelo no soportado")

        # Export STL binario
        stl_bytes: bytes = mesh.export(file_type="stl")

        # nombre consistente por modelo
        filename = f"{req.model}/{uuid.uuid4().hex}.stl"
        download_name = f"{req.model}.stl"

        stl_url = upload_to_supabase(filename, stl_bytes, download_name=download_name)

        return {"status": "ok", "stl_url": stl_url, "model": req.model}

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR generate:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))
