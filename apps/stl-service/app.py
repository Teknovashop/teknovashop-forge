import io
import os
from typing import List, Optional, Literal, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

import trimesh
from trimesh.creation import box

from supabase_client import upload_and_get_url
from apps.stl-service.models import REGISTRY  # del repo que subiste
from apps.stl-service.models._ops import cut_hole, cut_box, round_edges_box

# --------- Config ---------
CORS_ALLOW_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()]
if not CORS_ALLOW_ORIGINS:
    CORS_ALLOW_ORIGINS = ["*"]

BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")
PUBLIC_READ = os.getenv("SUPABASE_PUBLIC_READ", "0") == "1"

# --------- Tipos ---------
class Hole(BaseModel):
    x_mm: float
    y_mm: float = 0.0  # añadimos Y (antes sólo x,z)
    z_mm: float
    d_mm: float
    axis: Literal["x", "y", "z"] = "z"  # dirección del taladro

class Cut(BaseModel):
    cx_mm: float
    cy_mm: float
    cz_mm: float
    sx_mm: float
    sy_mm: float
    sz_mm: float

class Ops(BaseModel):
    holes: List[Hole] = []
    cuts: List[Cut] = []
    round_radius_mm: float = 0.0  # fillet simple para modelos de caja

class Params(BaseModel):
    # parámetros genéricos; cada modelo puede esperar otros,
    # pero aceptamos un dict libre y lo pasamos a su "make".
    # Añadimos long/width/height por compatibilidad con tu UI actual:
    length_mm: Optional[float] = Field(default=None, gt=0)
    width_mm: Optional[float] = Field(default=None, gt=0)
    height_mm: Optional[float] = Field(default=None, gt=0)
    thickness_mm: Optional[float] = Field(default=None, gt=0)

    extra: Dict[str, Any] = Field(default_factory=dict)

class GenerateReq(BaseModel):
    model: str = Field(..., description="id de modelo, p.ej. cable_tray | vesa_adapter | router_mount | ...")
    params: Params
    ops: Ops = Ops()

class GenerateRes(BaseModel):
    stl_url: str
    object_key: str

class ModelInfo(BaseModel):
    id: str
    defaults: Dict[str, Any]

# --------- App ---------
app = FastAPI(title="Teknovashop Forge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/models", response_model=List[ModelInfo])
def models():
    out = []
    for mid, meta in REGISTRY.items():
        out.append({"id": mid, "defaults": meta.get("defaults", {})})
    return out

def _apply_ops(mesh: trimesh.Trimesh, ops: Ops) -> trimesh.Trimesh:
    out = mesh
    # Redondeo simple si el mesh es una “caja”: intentamos detectar por bounding box
    if ops.round_radius_mm and isinstance(mesh, trimesh.Trimesh):
        L, W, H = (mesh.bounds[1] - mesh.bounds[0]).tolist()
        # Re-construimos como caja-fillete con mismas extents (esto es opcional y documentado)
        out = round_edges_box((L, W, H), ops.round_radius_mm)

    # Agujeros
    for h in (ops.holes or []):
        out = cut_hole(out, h.x_mm, h.y_mm, h.z_mm, h.d_mm, axis=h.axis)

    # Cortes rectangulares
    for c in (ops.cuts or []):
        out = cut_box(out, (c.cx_mm, c.cy_mm, c.cz_mm), (c.sx_mm, c.sy_mm, c.sz_mm))

    return out

@app.post("/generate", response_model=GenerateRes)
def generate(req: GenerateReq):
    mid = req.model
    meta = REGISTRY.get(mid)
    if not meta:
        raise RuntimeError(f"Modelo '{mid}' no encontrado. Usa /models para ver los disponibles.")

    # Construir base usando el make del registro
    make = meta["make"]
    # Combinamos params “planos” + extra para dar libertad
    param_dict = {k: v for k, v in req.params.dict().items() if k not in ("extra",) and v is not None}
    param_dict.update(req.params.extra or {})

    base_mesh = make(param_dict)  # los make_* del repo devuelven trimesh.Trimesh o Scene

    # Normalizamos a Trimesh (si viene Scene con un solo geom)
    if isinstance(base_mesh, trimesh.Scene):
        geoms = list(base_mesh.geometry.values())
        if not geoms:
            raise RuntimeError("El modelo generó una escena vacía.")
        base_mesh = geoms[0].copy()

    # Centrado + elevación en Z
    bb = base_mesh.bounds
    H = (bb[1][2] - bb[0][2]).item()
    base_mesh.apply_translation(-base_mesh.centroid)
    base_mesh.apply_translation((0, 0, H / 2.0))

    # Operaciones (agujeros/cortes/fillet simple)
    final_mesh = _apply_ops(base_mesh, req.ops)

    # Export STL
    stl_bytes = final_mesh.export(file_type="stl")
    if isinstance(stl_bytes, str):
        stl_bytes = stl_bytes.encode("utf-8")
    buf = io.BytesIO(stl_bytes)

    # Subir a Supabase
    object_key = f"{mid}/forge-{os.urandom(4).hex()}.stl"
    url = upload_and_get_url(buf, object_key, bucket=BUCKET, public=PUBLIC_READ)
    return GenerateRes(stl_url=url, object_key=object_key)
