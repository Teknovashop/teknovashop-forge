# apps/stl-service/app.py
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
  holes: Optional[List[Any]] = None  # aceptamos dicts o tuplas
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

def _hole_to_tuple(h: Any) -> Optional[Tuple[float, float, float]]:
  """
  Acepta:
    - dict con claves x_mm/x, z_mm/z, d_mm/d/diameter
    - tuple/list (x, z, d)
  Devuelve siempre (x,z,d) en float o None si no válido.
  """
  if h is None:
    return None
  if isinstance(h, (list, tuple)) and len(h) >= 3:
    return (_as_float(h[0]), _as_float(h[1]), _as_float(h[2]))
  if isinstance(h, dict):
    x = h.get("x_mm", h.get("x"))
    z = h.get("z_mm", h.get("z"))
    dval = h.get("d_mm", h.get("d") or h.get("diameter"))
    if x is None or z is None or dval is None:
      return None
    return (_as_float(x), _as_float(z), _as_float(dval))
  # pydantic HoleSpec?
  if hasattr(h, "x_mm") and hasattr(h, "z_mm") and hasattr(h, "d_mm"):
    return (_as_float(h.x_mm), _as_float(h.z_mm), _as_float(h.d_mm))
  return None

def _normalize_holes(holes: Optional[List[Any]]) -> List[Tuple[float, float, float]]:
  out: List[Tuple[float, float, float]] = []
  for h in holes or []:
    tup = _hole_to_tuple(h)
    if tup is not None:
      out.append(tup)
  return out

def _params_debug_types(d: dict) -> dict:
  def t(v: Any) -> str:
    if isinstance(v, (list, tuple)):
      return f"{type(v).__name__}[{', '.join(t(x) for x in v)}]"
    return type(v).__name__
  return {k: t(v) for k, v in d.items()}

def upload_to_supabase(path: str, content: bytes, content_type="application/octet-stream") -> str:
  if not SUPABASE_URL or not SUPABASE_KEY:
    raise HTTPException(500, "Supabase no configurado")

  path = path.lstrip("/")
  print(f"[upload] bucket='{SUPABASE_BUCKET}' put path='{path}'")

  # 1) subir
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

  # Si el bucket es público, devolvemos URL directa
  if SUPABASE_PUBLIC_READ:
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{path}"
    print(f"[upload] public URL -> {public_url}")
    return public_url

  # 2) firmar
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

    # Normaliza agujeros a lista de tuplas (x,z,d)
    holes_tuples = _normalize_holes(req.holes)

    if model == "cable_tray":
      params = dict(
        width=req.width_mm or 60,
        height=req.height_mm or 25,
        length=req.length_mm or 180,
        thickness=req.thickness_mm or 3,
        ventilated=bool(req.ventilated),
        holes=holes_tuples,
      )
    elif model == "vesa_adapter":
      params = dict(
        vesa_mm=req.vesa_mm or 100,
        thickness=req.thickness_mm or 4,
        clearance=req.clearance_mm or 1,
        hole=req.hole_diameter_mm or 5,
        holes=holes_tuples,
      )
    elif model == "router_mount":
      params = dict(
        router_width=req.router_width_mm or 120,
        router_depth=req.router_depth_mm or 80,
        thickness=req.thickness_mm or 4,
        holes=holes_tuples,
      )
    elif model == "phone_stand":
      angle_val = req.angle_deg or 60
      depth_val = req.support_depth or 110
      params = dict(
        angle_deg=angle_val,
        angle=angle_val,
        support_depth=depth_val,
        depth=depth_val,
        width=req.width or 80,
        thickness=req.thickness_mm or 4,
      )
    elif model == "qr_plate":
      params = dict(
        length=req.length_mm or 90,
        width=req.width or 38,
        thickness=req.thickness_mm or 8,
        slot_mm=req.slot_mm or 22,
        screw_d_mm=req.screw_d_mm or 6.5,
        holes=holes_tuples,
      )
    elif model == "enclosure_ip65":
      params = dict(
        length=req.box_length or req.length_mm or 201,
        width=req.box_width or req.width or 68,
        height=req.box_height or req.height_mm or 31,
        wall=req.wall_mm or req.thickness_mm or 5,
        holes=holes_tuples,
      )
    elif model == "cable_clip":
      params = dict(
        diameter=req.clip_diameter or 8,
        width=req.clip_width or 12,
        thickness=req.thickness_mm or 2.4,
      )
    else:
      raise HTTPException(400, "Modelo no soportado")

    print(f"[generate] bucket='{SUPABASE_BUCKET}' model={model} types={_params_debug_types(params)}")
    if holes_tuples:
      print(f"[generate] holes[0] sample={repr(holes_tuples[0])} type={type(holes_tuples[0]).__name__}")

    # make
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
  except Exception as e:
    print("[generate][ERROR]", repr(e))
    raise HTTPException(status_code=500, detail=str(e))
