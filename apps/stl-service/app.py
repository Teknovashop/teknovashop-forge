# apps/stl-service/app.py
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Literal, Optional, Dict, Any
import time

from supabase import create_client
# Aquí asumo que ya tienes tu generador interno importable:
# from generator import generate_stl_and_svg  # -> deberías tenerlo en tu proyecto

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "forge-stl")
CORS_ALLOW = os.environ.get("CORS_ALLOW_ORIGINS", "").split(",")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ALLOW if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Modelos de entrada -----
class Params(BaseModel):
    length_mm: float
    width_mm: float
    height_mm: float
    thickness_mm: Optional[float] = 3
    fillet_mm: Optional[float] = 0

class Hole(BaseModel):
    x_mm: float
    y_mm: float
    d_mm: float

class OpBase(BaseModel):
    type: Literal["cutout", "text", "round", "array"]
    title: Optional[str] = None

class OpCutout(OpBase):
    type: Literal["cutout"] = "cutout"
    shape: Literal["circle", "rect"]
    x_mm: float
    y_mm: float
    d_mm: Optional[float] = None
    w_mm: Optional[float] = None
    h_mm: Optional[float] = None
    depth_mm: Optional[float] = 9999

class OpText(OpBase):
    type: Literal["text"] = "text"
    text: str
    x_mm: float
    y_mm: float
    size_mm: float
    depth_mm: float
    engrave: Optional[bool] = True

class OpRound(OpBase):
    type: Literal["round"] = "round"
    r_mm: float

class OpArray(OpBase):
    type: Literal["array"] = "array"
    shape: Literal["circle", "rect"]
    start_x_mm: float
    start_y_mm: float
    nx: int
    ny: int
    dx_mm: float
    dy_mm: float
    d_mm: Optional[float] = None
    w_mm: Optional[float] = None
    h_mm: Optional[float] = None

Operation = OpCutout | OpText | OpRound | OpArray

class GenerateReq(BaseModel):
    model: str
    params: Params
    holes: List[Hole] = []
    operations: List[Operation] = []
    outputs: Optional[List[Literal["stl","svg"]]] = ["stl"]

def normalize_model_id(m: str) -> str:
    return (m or "").strip().replace("-", "_")

# ----- Utilidades Supabase -----
def upload_bytes_and_get_signed(path: str, data: bytes, mime: str, expire_seconds: int = 60*60) -> str:
    # sube el archivo
    supabase.storage.from_(SUPABASE_BUCKET).upload(path, data, {"contentType": mime, "upsert": True})
    # crea URL firmada
    res = supabase.storage.from_(SUPABASE_BUCKET).create_signed_url(path, expire_seconds)
    if not res or not res.get("signedURL"):
        raise RuntimeError("No se pudo firmar la URL")
    # Devuelve URL absoluta
    return f"{SUPABASE_URL}/storage/v1/object/sign/{SUPABASE_BUCKET}/{path}?token={res['token']}" if "token" in res else res["signedURL"]

# ----- Endpoint principal -----
@app.post("/generate")
def generate(req: GenerateReq):
    model_id = normalize_model_id(req.model)
    if not model_id:
        raise HTTPException(status_code=400, detail="Modelo no válido")

    # Aquí deberías llamar a tu pipeline real de generación (CadQuery/Trimesh/OpenSCAD…)
    # stl_bytes, svg_bytes = generate_stl_and_svg(model_id, req.params, req.holes, req.operations, outputs=req.outputs)
    # Para mantenerlo no intrusivo, asumo que ya tienes esa función.
    # A falta de eso, devuelvo 400 para que nunca “falle silencioso”:
    try:
        from generator import generate_stl_and_svg  # tu módulo existente
    except Exception:
        raise HTTPException(status_code=500, detail="Pipeline de generación no disponible en este entorno")

    result = generate_stl_and_svg(
        model=model_id,
        params=req.params.model_dump(),
        holes=[h.model_dump() for h in req.holes],
        operations=[(op.model_dump()) for op in req.operations],
        outputs=req.outputs or ["stl"]
    )

    stl_bytes: Optional[bytes] = result.get("stl")
    svg_bytes: Optional[bytes] = result.get("svg")

    if not stl_bytes:
        raise HTTPException(status_code=500, detail="No se pudo generar STL")

    ts = int(time.time())
    base = f"{model_id}/forge-output-{ts}"

    stl_path = f"{base}.stl"
    stl_url  = upload_bytes_and_get_signed(stl_path, stl_bytes, "model/stl")

    svg_url = None
    if svg_bytes:
        svg_path = f"{base}.svg"
        svg_url  = upload_bytes_and_get_signed(svg_path, svg_bytes, "image/svg+xml")

    return {"stl_url": stl_url, "svg_url": svg_url}
