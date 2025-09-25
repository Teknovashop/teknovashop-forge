# apps/stl-service/app.py
# teknovashop-forge/app.py
import os, uuid, time
from typing import List, Literal, Optional, Any, Tuple

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Makers
from models.cable_tray import make_model as make_cable_tray
from models.router_mount import make_model as make_router_mount
from models.vesa_adapter import make_model as make_vesa
from models.phone_stand import make_model as make_phone_stand
from models.qr_plate import make_model as make_qr_plate
from models.enclosure_ip65 import make_model as make_enclosure_ip65
from models.cable_clip import make_model as make_cable_clip
# Si tienes vesa_shelf.py ya listo, descomenta la línea siguiente:
# from models.vesa_shelf import make_model as make_vesa_shelf

# --------- ENV SUPABASE ---------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "forge-stl")
SUPABASE_PUBLIC_READ = os.environ.get("SUPABASE_PUBLIC_READ", "false").lower() in ("1", "true", "yes")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[WARN] Faltan SUPABASE_URL / SUPABASE_SERVICE_KEY")

app = FastAPI(title="Teknovashop Forge")

# --------- MODELOS/SCHEMAS ---------
class HoleSpec(BaseModel):
    x_mm: float
    z_mm: float
    d_mm: float = Field(gt=0)
    # opcionales (ignorados por los makers actuales; los aceptamos por compatibilidad)
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
    # "vesa_shelf",  # descomenta cuando tengas el maker importado
]

class GenerateReq(BaseModel):
    model: ModelKind
    holes: Optional[List[HoleSpec | Tuple[float, float, float]]] = None
    thickness_mm: Optional[float] = None
    ventilated: Optional[bool] = True

    # Cable tray
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    length_mm: Optional[float] = None

    # VESA (aceptamos ambas nomenclaturas)
    plate_size_mm: Optional[float] = None
    vesa_pattern_mm: Optional[float] = None
    vesa_hole_d_mm: Optional[float] = None
    # antiguos
    vesa_mm: Optional[float] = None
    hole_diameter_mm: Optional[float] = None
    clearance_mm: Optional[float] = None  # sin uso ahora mismo

    # Router (aceptamos width/depth y router_width/router_depth)
    width_mm_router: Optional[float] = Field(None, alias="width_mm")
    depth_mm_router: Optional[float] = Field(None, alias="depth_mm")
    router_width_mm: Optional[float] = None
    router_depth_mm: Optional[float] = None
    flange_mm: Optional[float] = None

    # Phone stand
    angle_deg: Optional[float] = None
    support_depth: Optional[float] = None
    width: Optional[float] = None

    # QR plate (nombres nuevos y antiguos)
    system: Optional[str] = None
    screw_d_mm: Optional[float] = None
    slot_len_mm: Optional[float] = None
    # antiguos
    slot_mm: Optional[float] = None

    # Enclosure (aceptamos ambos)
    wall_mm: Optional[float] = None
    box_length: Optional[float] = None
    box_width: Optional[float] = None
    box_height: Optional[float] = None

    # Cable clip (aceptamos ambos)
    clip_diameter: Optional[float] = None
    clip_width: Optional[float] = None
    diameter_mm: Optional[float] = None
    width_mm_clip: Optional[float] = Field(None, alias="width_mm")

@app.get("/health")
def health():
    return {"ok": True, "ts": int(time.time())}

# ---------- helpers ----------
def _as_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

def _hole_dict_to_tuple(d: dict) -> Optional[Tuple[float, float, float]]:
    if not isinstance(d, dict):
        return None
    x = d.get("x_mm", d.get("x"))
    z = d.get("z_mm", d.get("z"))
    dval = d.get("d_mm", d.get("d") or d.get("diameter"))
    if x is None or z is None or dval is None:
        return None
    return (_as_float(x), _as_float(z), _as_float(dval))

def _sanitize(value: Any, context_key: str = "") -> Any:
    # Normaliza recursivamente y convierte HoleSpec/dict -> tupla (x,z,d)
    if isinstance(value, HoleSpec):
        return (value.x_mm, value.z_mm, value.d_mm)
    if isinstance(value, dict):
        as_hole = _hole_dict_to_tuple(value)
        if as_hole is not None:
            return as_hole
        return {k: _sanitize(v, f"{context_key}.{k}" if context_key else k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        out = []
        for i, item in enumerate(value):
            # Permitimos ya tuplas (x,z,d), dicts o HoleSpec
            if isinstance(item, tuple) and len(item) == 3 and all(isinstance(n, (int, float)) for n in item):
                out.append((float(item[0]), float(item[1]), float(item[2])))
            else:
                out.append(_sanitize(item, f"{context_key}[{i}]"))
        return out
    if isinstance(value, bool):
        return value
    try:
        return _as_float(value)
    except Exception:
        return value

def _params_debug_types(d: dict) -> dict:
    def t(v: Any) -> str:
        if isinstance(v, list):
            return "list[" + ", ".join(t(x) for x in v[:3]) + (", ..." if len(v) > 3 else "") + "]"
        if isinstance(v, tuple):
            return "tuple[" + ", ".join(t(x) for x in v) + "]"
        return type(v).__name__
    return {k: t(v) for k, v in d.items()}

def upload_to_supabase(path: str, content: bytes, content_type="application/sla") -> str:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(500, "Supabase no configurado")

    path = path.lstrip("/")
    print(f"[upload] bucket='{SUPABASE_BUCKET}' put path='{path}'")

    # 1) subir (upsert)
    put_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{path}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": content_type,
        "X-Upsert": "true",
    }
    r = httpx.put(put_url, headers=headers, content=content, timeout=60)
    if r.status_code not in (200, 201):
        print("[upload][error]", r.status_code, r.text)
        raise HTTPException(500, f"Supabase upload error: {r.status_code} {r.text}")

    # 2) si público, URL pública directa
    if SUPABASE_PUBLIC_READ:
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{path}"
        print(f"[upload] public URL -> {public_url}")
        return public_url

    # 3) firmar 1h
    sign_url = f"{SUPABASE_URL}/storage/v1/object/sign/{SUPABASE_BUCKET}/{path}"
    print(f"[upload] sign path='{path}'")
    r2 = httpx.post(
        sign_url,
        headers={
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
        json={"expiresIn": 3600},
        timeout=30,
    )
    if r2.status_code != 200:
        print("[sign][error]", r2.status_code, r2.text)
        raise HTTPException(500, f"Supabase sign error: {r2.status_code} {r2.text}")

    data = r2.json()
    signed_rel = data.get("signedURL") or data.get("signedUrl")
    if not signed_rel:
        print("[sign][error] missing signedURL key", data)
        raise HTTPException(500, "No signedURL in Supabase response")
    signed_full = f"{SUPABASE_URL}{signed_rel}"
    print(f"[upload] signed URL -> {signed_full}")
    return signed_full

@app.post("/generate")
def generate(req: GenerateReq):
    try:
        model = req.model

        # --- Construcción de params para cada maker, aceptando nombres nuevos/antiguos ---
        if model == "cable_tray":
            params = dict(
                width=req.width_mm or 60,
                height=req.height_mm or 25,
                length=req.length_mm or 180,
                thickness=req.thickness_mm or 3,
                ventilated=bool(req.ventilated),
                holes=req.holes or [],
            )

        elif model == "vesa_adapter":
            plate = req.plate_size_mm or (req.vesa_pattern_mm or req.vesa_mm) or 100
            hole_d = req.vesa_hole_d_mm or req.hole_diameter_mm or 5
            params = dict(
                plate_size_mm=plate,
                thickness_mm=req.thickness_mm or 4,
                vesa_pattern_mm=plate,   # mismo valor que plate_size si tu maker lo usa así
                vesa_hole_d_mm=hole_d,
                holes=req.holes or [],
            )

        elif model == "router_mount":
            w = req.width_mm_router or req.router_width_mm or 180
            d = req.depth_mm_router or req.router_depth_mm or 120
            f = req.flange_mm or 60
            params = dict(
                width_mm=w,
                depth_mm=d,
                flange_mm=f,
                thickness_mm=req.thickness_mm or 4,
                holes=req.holes or [],
            )

        elif model == "phone_stand":
            angle_val = req.angle_deg or 60
            depth_val = req.support_depth or 110
            params = dict(
                angle_deg=angle_val,
                support_depth=depth_val,
                width=req.width or 80,
                thickness=req.thickness_mm or 4,
            )

        elif model == "qr_plate":
            params = dict(
                system=req.system or "arca",
                length_mm=req.length_mm or 90,
                width_mm=req.width or 38,
                thickness_mm=req.thickness_mm or 8,
                screw_d_mm=req.screw_d_mm or 6.5,
                slot_len_mm=(req.slot_len_mm or req.slot_mm or 22),
                holes=req.holes or [],
            )

        elif model == "enclosure_ip65":
            params = dict(
                length=req.box_length or req.length_mm or 120,
                width=req.box_width or req.width or 80,
                height=req.box_height or req.height_mm or 45,
                wall=req.wall_mm or req.thickness_mm or 3,
                holes=req.holes or [],
            )

        elif model == "cable_clip":
            params = dict(
                diameter=req.diameter_mm or req.clip_diameter or 8,
                width=req.width_mm_clip or req.clip_width or 12,
                thickness=req.thickness_mm or 2.4,
            )

        # elif model == "vesa_shelf":
        #     params = dict(
        #         vesa_mm=req.vesa_pattern_mm or req.vesa_mm or 100,
        #         thickness_mm=req.thickness_mm or 5,
        #         shelf_width_mm=req.width_mm or 220,
        #         shelf_depth_mm=req.length_mm or 160,
        #         lip_height_mm=req.height_mm or 10,
        #         vesa_hole_d_mm=req.vesa_hole_d_mm or 5,
        #         holes=req.holes or [],
        #     )

        else:
            raise HTTPException(400, "Modelo no soportado")

        # Normalizar
        params = _sanitize(params, model)
        print(f"[generate] bucket='{SUPABASE_BUCKET}' model={model} types={_params_debug_types(params)}")
        if isinstance(params, dict) and params.get("holes"):
            sample = params["holes"][0]
            print(f"[generate] holes[0] sample={repr(sample)} type={type(sample).__name__}")

        # Llamar maker
        if model == "cable_tray":
            mesh = make_cable_tray(params)
        elif model == "vesa_adapter":
            mesh = make_vesa(params)
        elif model == "router_mount":
            mesh = make_router_mount(params)
        elif model == "phone_stand":
            mesh = make_phone_stand(params)
        elif model == "qr_plate":
            mesh = make_qr_plate(params)
        elif model == "enclosure_ip65":
            mesh = make_enclosure_ip65(params)
        elif model == "cable_clip":
            mesh = make_cable_clip(params)
        # elif model == "vesa_shelf":
        #     mesh = make_vesa_shelf(params)
        else:
            raise HTTPException(400, "Modelo no soportado")

        stl_bytes: bytes = mesh.export(file_type="stl")
        if not stl_bytes:
            raise HTTPException(500, "STL vacío")

        folder = model.replace(" ", "-")
        fname = f"{folder}/{uuid.uuid4().hex}.stl"
        print(f"[generate] put/sign path='{fname}'")

        stl_url = upload_to_supabase(fname, stl_bytes, content_type="application/sla")
        return {"status": "ok", "stl_url": stl_url, "model": model}

    except HTTPException:
        raise
    except TypeError as te:
        print(f"[generate][TypeError] model={req.model} -> {te!r}")
        raise HTTPException(status_code=500, detail=str(te))
    except Exception as e:
        print("[generate][ERROR]", repr(e))
        raise HTTPException(status_code=500, detail=str(e))
