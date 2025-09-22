# teknovashop-forge/app.py
import os, uuid, time
from typing import List, Literal, Optional, Any, Tuple, Union

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

    # extras (se ignoran en makers antiguos)
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

# ---------- helpers de saneo ----------
def _as_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

def _hole_dict_to_tuple(d: dict) -> Optional[Tuple[float, float, float]]:
    if not isinstance(d, dict):
        return None
    # Acepta x/z/d o x_mm/z_mm/d_mm
    x = d.get("x_mm", d.get("x"))
    z = d.get("z_mm", d.get("z"))
    dval = d.get("d_mm", d.get("d") or d.get("diameter"))
    if x is None or z is None or dval is None:
        return None
    return (_as_float(x), _as_float(z), _as_float(dval))

def _sanitize(value: Any, context_key: str = "") -> Any:
    """
    Sanea recursivamente:
      - numbers -> float
      - dict agujero -> (x,z,d)
      - listas/tuplas -> procesa cada elemento
      - dict genérico -> procesa valores
    """
    # Dict con forma de agujero
    if isinstance(value, dict):
        as_hole = _hole_dict_to_tuple(value)
        if as_hole is not None:
            return as_hole
        # Dict genérico: sanea cada valor
        return {k: _sanitize(v, f"{context_key}.{k}" if context_key else k) for k, v in value.items()}

    # Lista/Tupla: sanea cada item
    if isinstance(value, (list, tuple)):
        out = []
        for i, item in enumerate(value):
            item_s = _sanitize(item, f"{context_key}[{i}]")
            out.append(item_s)
        # si es tupla, devolvemos tupla; si no, lista
        return tuple(out) if isinstance(value, tuple) else out

    # Booleans tal cual
    if isinstance(value, bool):
        return value

    # Números/cadenas -> float si son numéricos
    try:
        return _as_float(value)
    except Exception:
        return value

def _params_debug_types(d: dict) -> dict:
    def t(v: Any) -> str:
        if isinstance(v, (list, tuple)):
            return f"{type(v).__name__}[{', '.join(t(x) for x in v)}]"
        return type(v).__name__
    return {k: t(v) for k, v in d.items()}

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
        model = req.model

        # Construimos params base por modelo (valores por defecto ya en float)
        if model == "cable_tray":
            params = dict(
                width=req.width_mm or 60,
                height=req.height_mm or 25,
                length=req.length_mm or 180,
                thickness=req.thickness_mm or 3,
                ventilated=bool(req.ventilated),
                holes=[h.model_dump() if hasattr(h, "model_dump") else h for h in (req.holes or [])],
            )

        elif model == "vesa_adapter":
            params = dict(
                vesa_mm=req.vesa_mm or 100,
                thickness=req.thickness_mm or 4,
                clearance=req.clearance_mm or 1,
                hole=req.hole_diameter_mm or 5,
                holes=[h.model_dump() if hasattr(h, "model_dump") else h for h in (req.holes or [])],
            )

        elif model == "router_mount":
            params = dict(
                router_width=req.router_width_mm or 120,
                router_depth=req.router_depth_mm or 80,
                thickness=req.thickness_mm or 4,
                holes=[h.model_dump() if hasattr(h, "model_dump") else h for h in (req.holes or [])],
            )

        elif model == "phone_stand":
            angle_val = req.angle_deg or 60
            depth_val = req.support_depth or 110
            params = dict(
                angle_deg=angle_val,
                angle=angle_val,               # alias compat
                support_depth=depth_val,
                depth=depth_val,               # alias compat
                width=req.width or 80,
                thickness=req.thickness_mm or 4,
                # phone_stand no usa holes
            )

        elif model == "qr_plate":
            params = dict(
                length=req.length_mm or 90,
                width=req.width or 38,
                thickness=req.thickness_mm or 8,
                slot_mm=req.slot_mm or 22,
                screw_d_mm=req.screw_d_mm or 6.5,
                holes=[h.model_dump() if hasattr(h, "model_dump") else h for h in (req.holes or [])],
            )

        elif model == "enclosure_ip65":
            params = dict(
                length=req.box_length or req.length_mm or 201,
                width=req.box_width or req.width or 68,
                height=req.box_height or req.height_mm or 31,
                wall=req.wall_mm or req.thickness_mm or 5,
                holes=[h.model_dump() if hasattr(h, "model_dump") else h for h in (req.holes or [])],
            )

        elif model == "cable_clip":
            params = dict(
                diameter=req.clip_diameter or 8,
                width=req.clip_width or 12,
                thickness=req.thickness_mm or 2.4,
            )
        else:
            raise HTTPException(400, "Modelo no soportado")

        # Saneo RECURSIVO de todos los parámetros
        params = _sanitize(params, model)

        # Log de diagnóstico (tipos)
        print(f"[generate] model={model} types={_params_debug_types(params)}")
        if isinstance(params, dict) and "holes" in params:
            holes = params.get("holes") or []
            if holes:
                print(f"[generate] holes[0] sample={repr(holes[0])} type={type(holes[0]).__name__}")

        # Llamada al maker correspondiente
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
        else:
            raise HTTPException(400, "Modelo no soportado")

        # Export STL
        stl_bytes: bytes = mesh.export(file_type="stl")
        if not stl_bytes:
            raise HTTPException(500, "STL vacío")

        fname = f"{model}/{uuid.uuid4().hex}.stl"
        stl_url = upload_to_supabase(fname, stl_bytes)
        return {"status": "ok", "stl_url": stl_url, "model": model}

    except HTTPException:
        raise
    except TypeError as te:
        # Imprime params para cazarlos al vuelo
        print(f"[generate][TypeError] model={req.model} params={params}")
        raise HTTPException(status_code=500, detail=str(te))
    except Exception as e:
        print("ERROR generate:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))
