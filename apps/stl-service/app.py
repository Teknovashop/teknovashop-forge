import io
import os
from typing import List, Optional, Callable, Dict, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

import numpy as np
import trimesh
from trimesh.creation import box, cylinder

from supabase_client import upload_and_get_url

# =========================================================
# Config
# =========================================================
CORS_ALLOW_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()] or ["*"]
BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")
PUBLIC_READ = os.getenv("SUPABASE_PUBLIC_READ", "0") == "1"

# Boolean engines availability
HAS_SCAD = bool(getattr(trimesh.interfaces, "scad", None)) and bool(trimesh.interfaces.scad.exists)
HAS_BLENDER = bool(getattr(trimesh.interfaces, "blender", None)) and bool(trimesh.interfaces.blender.exists)

def boolean_diff(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Boolean difference robusta: SCAD > Blender > fallback (sin agujero).
    """
    try:
        if HAS_SCAD:
            return trimesh.boolean.difference([a, b], engine="scad")
        if HAS_BLENDER:
            return trimesh.boolean.difference([a, b], engine="blender")
        # Fallback: intenta con engine por defecto (puede funcionar en algunos entornos)
        return trimesh.boolean.difference([a, b])
    except Exception as e:
        # Sin motor disponible o fallo -> devolvemos 'a' y registramos
        print(f"[WARN] Boolean difference no disponible: {e}")
        return a

# =========================================================
# Modelos de request/response
# =========================================================
class Hole(BaseModel):
    x_mm: float
    z_mm: float
    d_mm: float

class Params(BaseModel):
    length_mm: float = Field(..., gt=0)
    width_mm: float  = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    thickness_mm: Optional[float] = Field(default=3, gt=0)

    @validator("*", pre=True)
    def to_float(cls, v):
        return float(v)

class GenerateReq(BaseModel):
    model: str = Field(..., description="cable-tray | vesa-adapter | router-mount")
    params: Params
    holes: Optional[List[Hole]] = []

    @validator("holes", pre=True)
    def _coerce(cls, v):
        if not v:
            return []
        out = []
        for h in v:
            out.append({"x_mm": float(h["x_mm"]), "z_mm": float(h.get("z_mm", 0)), "d_mm": float(h["d_mm"])})
        return out

class GenerateRes(BaseModel):
    stl_url: str
    object_key: str
    engine: Optional[str] = None  # motor booleano usado (scad/blender/none)

# =========================================================
# Helpers de construcción
# =========================================================
def clamps(p: Params) -> Tuple[float, float, float, float]:
    L = max(20.0, float(p.length_mm))
    W = max(10.0, float(p.width_mm))
    H = max(5.0,  float(p.height_mm))
    T = float(p.thickness_mm or 3.0)
    T = min(max(1.0, T), min(W, H) / 2.0)  # grosor razonable
    return L, W, H, T

def make_plate(L: float, W: float, T: float) -> trimesh.Trimesh:
    # Caja centrada en origen, Z altura; subimos T/2 para dejar base sobre Z=0
    plate = box(extents=(L, W, T))
    plate.apply_translation((0, 0, T / 2.0))
    return plate

def add_holes_top(solid: trimesh.Trimesh, L: float, H: float, holes: List[Hole]) -> trimesh.Trimesh:
    if not holes:
        return solid
    engine_used = "none"
    for h in holes:
        r = max(0.1, h.d_mm / 2.0)
        # Coordenada X del usuario va en [0..L]; convertimos a centro [-L/2..L/2]
        cx = float(h.x_mm) - (L / 2.0)
        # Z del usuario es respecto a la cara superior; si no viene, agujereamos desde arriba
        cz = H if h.z_mm is None else float(h.z_mm)
        cyl = cylinder(radius=r, height=max(H * 2.0, 100.0), sections=64)
        # Cilindro por eje Z; subimos a la tapa
        cyl.apply_translation((cx, 0.0, cz))
        before = solid
        solid = boolean_diff(solid, cyl)
        if solid is before:
            engine_used = "none"
        else:
            engine_used = "scad" if HAS_SCAD else ("blender" if HAS_BLENDER else "default")
    # guardamos en atributo para responder qué motor se usó
    solid.metadata = solid.metadata or {}
    solid.metadata["engine"] = engine_used
    return solid

# =========================================================
# Builders de modelos
# =========================================================
def build_cable_tray(p: Params, holes: List[Hole]) -> trimesh.Trimesh:
    """
    Bandeja en U simple: base + paredes laterales -> (caja exterior - caja interior).
    """
    L, W, H, T = clamps(p)
    outer = box(extents=(L, W, H))
    outer.apply_translation((0, 0, H / 2.0))

    inner = box(extents=(L - 2 * T, W - 2 * T, H))  # abierto por arriba (quitamos luego la tapa)
    inner.apply_translation((0, 0, H / 2.0))
    tray = boolean_diff(outer, inner)

    # quitar tapa superior: restamos una lámina fina en la parte de arriba
    top_cut = box(extents=(L, W, H + 0.01))
    top_cut.apply_translation((0, 0, H + 0.005))
    tray = boolean_diff(tray, top_cut)

    # Agujeros en la base superior (si se piden)
    tray = add_holes_top(tray, L, H, holes)
    return tray

def build_vesa_adapter(p: Params, holes: List[Hole]) -> trimesh.Trimesh:
    """
    Placa VESA: placa rectangular con agujeros VESA 75/100 + opcionales del usuario.
    - length_mm ~ ancho X
    - width_mm  ~ alto Y
    - height_mm ~ grosor T
    """
    L, W, H, T = clamps(p)
    plate = make_plate(L, W, T)

    # Agujeros VESA (75 y 100 mm). Solo los que quepan en la placa.
    def drill_circle(solid: trimesh.Trimesh, x: float, y: float, r: float) -> trimesh.Trimesh:
        cyl = cylinder(radius=r, height=max(T * 3, 20.0), sections=64)
        cyl.apply_translation((x, y, T / 2.0))
        return boolean_diff(solid, cyl)

    screw_r = 3.5  # M6 clearance ~ 3.5 mm radio
    # 100x100
    if L >= 110 and W >= 110:
        for sx in (-50.0, 50.0):
            for sy in (-50.0, 50.0):
                plate = drill_circle(plate, sx, sy, screw_r)
    # 75x75
    if L >= 85 and W >= 85:
        for sx in (-37.5, 37.5):
            for sy in (-37.5, 37.5):
                plate = drill_circle(plate, sx, sy, screw_r)

    # Agujeros adicionales del payload (proyectados desde arriba en X)
    plate = add_holes_top(plate, L, T, holes)
    return plate

def build_router_mount(p: Params, holes: List[Hole]) -> trimesh.Trimesh:
    """
    Soporte en 'L': placa base + placa vertical (ambas con grosor T).
    length=L (X), width=W (Y), height=H (altura del ala vertical)
    """
    L, W, H, T = clamps(p)
    base = make_plate(L, W, T)  # base sobre Z=0
    vertical = make_plate(L, H, T)
    # Giramos 90° para que la placa vertical suba en Z y ocupe eje Y como altura H
    vertical.apply_translation((0, 0, -T / 2.0))
    vertical.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0]))
    vertical.apply_translation((0, (W / 2.0) - (T / 2.0), H / 2.0))

    bracket = trimesh.util.concatenate([base, vertical])

    # Agujeros del usuario en la placa vertical: interpretamos x_mm como a lo largo de L
    # y z_mm como altura sobre la base
    if holes:
        for h in holes:
            r = max(0.1, h.d_mm / 2.0)
            cx = float(h.x_mm) - (L / 2.0)
            cz = float(h.z_mm if h.z_mm is not None else H / 2.0)
            cyl = cylinder(radius=r, height=max(W * 2.0, 100.0), sections=64)
            # Taladrar perpendicular a la placa vertical (eje Y)
            cyl.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0, 1, 0]))
            cyl.apply_translation((cx, (W / 2.0) - (T / 2.0), cz))
            bracket = boolean_diff(bracket, cyl)

    return bracket

# Registro de modelos
MODEL_REGISTRY: Dict[str, Callable[[Params, List[Hole]], trimesh.Trimesh]] = {
    "cable-tray": build_cable_tray,
    "vesa-adapter": build_vesa_adapter,
    "router-mount": build_router_mount,
}

# =========================================================
# FastAPI
# =========================================================
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
    return {"ok": True, "scad": HAS_SCAD, "blender": HAS_BLENDER}

@app.get("/models")
def models():
    return {"models": list(MODEL_REGISTRY.keys())}

@app.post("/generate", response_model=GenerateRes)
def generate(req: GenerateReq):
    model_id = req.model.strip()
    builder = MODEL_REGISTRY.get(model_id)
    if not builder:
        raise HTTPException(status_code=400, detail=f"Modelo '{model_id}' no soportado")

    # Construye la malla
    mesh = builder(req.params, req.holes or [])

    # Export STL a memoria
    stl_bytes = mesh.export(file_type="stl")
    if isinstance(stl_bytes, str):
        stl_bytes = stl_bytes.encode("utf-8")
    buf = io.BytesIO(stl_bytes)

    # Subir a Supabase
    object_key = f"{model_id}/forge-output.stl"
    url = upload_and_get_url(buf, object_key, bucket=BUCKET, public=PUBLIC_READ)

    engine_used = (mesh.metadata or {}).get("engine")
    return GenerateRes(stl_url=url, object_key=object_key, engine=engine_used)
