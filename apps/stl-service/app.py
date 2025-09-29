import io
import os
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

import trimesh
from trimesh.creation import box, cylinder

from supabase_client import get_supabase, upload_and_get_url

# --------- Config ---------
CORS_ALLOW_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()]
if not CORS_ALLOW_ORIGINS:
    CORS_ALLOW_ORIGINS = ["*"]

BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")
PUBLIC_READ = os.getenv("SUPABASE_PUBLIC_READ", "0") == "1"

# --------- Models ---------
class Hole(BaseModel):
    x_mm: float
    z_mm: float
    d_mm: float

class Params(BaseModel):
    length_mm: float = Field(..., gt=0)
    width_mm: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    thickness_mm: Optional[float] = Field(default=3, gt=0)

class GenerateReq(BaseModel):
    model: str = Field(..., description="cable_tray | vesa_adapter | router_mount ... (de momento ignorado)")
    params: Params
    holes: Optional[List[Hole]] = []

    @validator("holes", pre=True)
    def _coerce(cls, v):
        if v is None:
            return []
        # permite objetos {x_mm,z_mm,d_mm} o arrays
        out = []
        for h in v:
            out.append({"x_mm": float(h["x_mm"]), "z_mm": float(h.get("z_mm", 0)), "d_mm": float(h["d_mm"])})
        return out

class GenerateRes(BaseModel):
    stl_url: str
    object_key: str

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

@app.post("/generate", response_model=GenerateRes)
def generate(req: GenerateReq):
    p = req.params
    L, W, H = p.length_mm, p.width_mm, p.height_mm

    # Caja centrada en origen y elevada H/2 (Z arriba)
    # Nota: trimesh box toma "extents" y devuelve centrado en ORIGEN.
    solid = box(extents=(L, W, H))
    solid.apply_translation((0, 0, H/2.0))

    # Taladrado de agujeros (en cara superior, Z ~ H)
    for h in (req.holes or []):
        r = max(0.1, h.d_mm / 2.0)
        cx = h.x_mm - (L / 2.0)  # convertir coordenada de [0..L] a [-L/2..L/2]
        cz = H                   # tapa superior
        # Cilindro alto para asegurar diferencia
        cyl = cylinder(radius=r, height=max(H*2.0, 50.0), sections=36)
        # Trimesh crea el cilindro centrado en origen a lo largo de Z; subimos para cortar desde arriba
        cyl.apply_translation((cx, 0.0, cz))
        solid = solid.difference(cyl, engine="scad") if trimesh.interfaces.scad.exists else solid.difference(cyl)

    # Export a STL en memoria
    stl_bytes = solid.export(file_type="stl")
    if isinstance(stl_bytes, str):
        stl_bytes = stl_bytes.encode("utf-8")
    buf = io.BytesIO(stl_bytes)

    # Subir a Supabase
    object_key = f"{req.model}/forge-output.stl"
    url = upload_and_get_url(buf, object_key, bucket=BUCKET, public=PUBLIC_READ)

    return GenerateRes(stl_url=url, object_key=object_key)
