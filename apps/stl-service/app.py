# apps/stl-service/app.py
import io
import os
import sys
import math
import traceback
from typing import List, Optional, Callable, Dict, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

import trimesh
from trimesh.creation import box, cylinder, icosphere

# --- Supabase (tuyo, ya existente) ---
from supabase_client import upload_and_get_url


# ============================================================
# Utilidades geométricas
# ============================================================

def _exists_scad() -> bool:
    # OpenSCAD como motor boolean de respaldo si está disponible
    return getattr(trimesh.interfaces, "scad", None) is not None and trimesh.interfaces.scad.exists


def _boolean_union(meshes: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    """Une varias mallas con el mejor motor disponible."""
    if not meshes:
        raise ValueError("No meshes to union")
    if len(meshes) == 1:
        return meshes[0]

    try:
        # Intento directo (Manifold plugin o CGAL si existiera)
        m = meshes[0].union(meshes[1])
        for mm in meshes[2:]:
            m = m.union(mm)
        return m
    except Exception:
        if _exists_scad():
            m = meshes[0].union(meshes[1], engine="scad")
            for mm in meshes[2:]:
                m = m.union(mm, engine="scad")
            return m
        # Fallback: convex hull de todos (aprox, pero estable)
        scene = trimesh.util.concatenate(meshes)
        return scene.convex_hull


def _boolean_difference(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
    """Resta booleana robusta con fallback."""
    try:
        return a.difference(b)
    except Exception:
        if _exists_scad():
            return a.difference(b, engine="scad")
        # Fallback: si no se puede, no perforamos para no romper.
        print("[WARN] Boolean difference falló; se omite un agujero.")
        return a


def rounded_block(extents: Tuple[float, float, float], r: float) -> trimesh.Trimesh:
    """
    Caja con esquinas redondeadas (fillet) aproximada:
    - Cuerpo central reducido (L-2r, W-2r, H-2r)
    - 12 cilindros a lo largo de los bordes (radio r)
    - 8 esferas en las esquinas (radio r)
    Si r <= 0 devuelve box puro.
    """
    L, W, H = extents
    r = max(0.0, float(r or 0.0))
    if r <= 0.0:
        m = box(extents=extents)
        m.apply_translation((0, 0, H / 2.0))
        return m

    # Limitar r para no quedar negativo
    r = min(r, L / 2.0, W / 2.0, H / 2.0)
    core = box(extents=(max(1e-3, L - 2 * r), max(1e-3, W - 2 * r), max(1e-3, H - 2 * r)))
    pieces = [core]

    # Esferas (8 esquinas)
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                s = icosphere(subdivisions=2, radius=r)
                s.apply_translation((sx * (L / 2.0 - r), sy * (W / 2.0 - r), sz * (H / 2.0 - r)))
                pieces.append(s)

    # Cilindros en los 12 bordes
    # Ejes X (4)
    hx = max(1e-3, L - 2 * r)
    for sy in (-1, 1):
        for sz in (-1, 1):
            c = cylinder(radius=r, height=hx, sections=36)
            c.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (0, 1, 0)))
            c.apply_translation((0, sy * (W / 2.0 - r), sz * (H / 2.0 - r)))
            pieces.append(c)

    # Ejes Y (4)
    hy = max(1e-3, W - 2 * r)
    for sx in (-1, 1):
        for sz in (-1, 1):
            c = cylinder(radius=r, height=hy, sections=36)
            c.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (1, 0, 0)))
            c.apply_translation((sx * (L / 2.0 - r), 0, sz * (H / 2.0 - r)))
            pieces.append(c)

    # Ejes Z (4)
    hz = max(1e-3, H - 2 * r)
    for sx in (-1, 1):
        for sy in (-1, 1):
            c = cylinder(radius=r, height=hz, sections=36)
            c.apply_translation((sx * (L / 2.0 - r), sy * (W / 2.0 - r), 0))
            pieces.append(c)

    solid = _boolean_union(pieces)
    # Elevar para que apoye en Z=0 (como hacías)
    solid.apply_translation((0, 0, H / 2.0))
    return solid


def add_holes_top(solid: trimesh.Trimesh, holes: List[dict], L: float, H: float) -> trimesh.Trimesh:
    """Agujeros pasantes verticales desde la cara superior."""
    for h in holes or []:
        d_mm = float(h.get("d_mm", 0) or 0)
        x_mm = float(h.get("x_mm", 0) or 0)
        if d_mm <= 0:
            continue
        r = max(0.1, d_mm / 2.0)
        # Coordenada centrada en X
        cx = x_mm - (L / 2.0)
        # Cilindro largo para garantizar paso completo
        drill = cylinder(radius=r, height=max(H * 2.0, 100.0), sections=48)
        # Trimesh crea cilindro a lo largo de Z centrado en (0,0,0), lo subimos
        drill.apply_translation((cx, 0.0, H))
        solid = _boolean_difference(solid, drill)
    return solid


# ============================================================
#  Modelos
# ============================================================

def _build_cable_tray(p: dict, holes: List[dict]) -> trimesh.Trimesh:
    L, W, H = p["length_mm"], p["width_mm"], p["height_mm"]
    fillet = p.get("fillet_mm", 0.0)
    base = rounded_block((L, W, H), fillet)
    return add_holes_top(base, holes, L, H)


def _build_vesa_adapter(p: dict, holes: List[dict]) -> trimesh.Trimesh:
    L, W, H = p["length_mm"], p["width_mm"], max(5.0, p["height_mm"])
    fillet = p.get("fillet_mm", 0.0)
    base = rounded_block((L, W, H), fillet)
    # (podríamos auto-taladrar patrón VESA según tamaño, lo dejamos básico + holes)
    return add_holes_top(base, holes, L, H)


def _build_router_mount(p: dict, holes: List[dict]) -> trimesh.Trimesh:
    L, W, H = p["length_mm"], p["width_mm"], p["height_mm"]
    fillet = p.get("fillet_mm", 0.0)
    base = rounded_block((L, W, H), fillet)
    return add_holes_top(base, holes, L, H)


# Modelos extra (placeholders sólidos + agujeros + fillet)
def _simple_block(p: dict, holes: List[dict]) -> trimesh.Trimesh:
    L, W, H = p["length_mm"], p["width_mm"], p["height_mm"]
    fillet = p.get("fillet_mm", 0.0)
    base = rounded_block((L, W, H), fillet)
    return add_holes_top(base, holes, L, H)


REGISTRY: Dict[str, Callable[[dict, List[dict]], trimesh.Trimesh]] = {
    "cable_tray": _build_cable_tray,
    "vesa_adapter": _build_vesa_adapter,
    "router_mount": _build_router_mount,
    # nuevos
    "pcb_standoff": _simple_block,
    "wall_bracket": _simple_block,
    "duct_adapter": _simple_block,
    "fan_grill": _simple_block,
    "raspberry_mount": _simple_block,
    "camera_mount": _simple_block,
    "cable_clip": _simple_block,
    "hinge": _simple_block,
    "knob": _simple_block,
}


# ============================================================
#  FastAPI + modelos de petición/respuesta
# ============================================================

CORS_ALLOW_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()
] or ["*"]

BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")
PUBLIC_READ = os.getenv("SUPABASE_PUBLIC_READ", "0") == "1"
SIGNED_EXPIRES = int(os.getenv("SIGNED_URL_EXPIRES", "3600"))


class Hole(BaseModel):
    x_mm: float = 0
    d_mm: float = 0
    # (si más adelante quieres Y/Z u orientación, se amplía aquí)


class Params(BaseModel):
    length_mm: float = Field(..., gt=0)
    width_mm: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    thickness_mm: Optional[float] = Field(default=3, gt=0)
    fillet_mm: Optional[float] = Field(default=0, ge=0)


class GenerateReq(BaseModel):
    model: str = Field(..., description="cable_tray | vesa_adapter | router_mount | ...")
    params: Params
    holes: Optional[List[Hole]] = []

    @validator("holes", pre=True)
    def _coerce(cls, v):
        # Acepta lista de dicts del frontend
        if v is None:
            return []
        out = []
        for h in v:
            if isinstance(h, dict):
                out.append({"x_mm": float(h.get("x_mm", 0.0)), "d_mm": float(h.get("d_mm", 0.0))})
            elif isinstance(h, Hole):
                out.append({"x_mm": float(h.x_mm), "d_mm": float(h.d_mm)})
        return out


class GenerateRes(BaseModel):
    stl_url: str
    object_key: str


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
    return {"ok": True, "models": list(REGISTRY.keys())}


def _export_stl(mesh_or_scene: trimesh.Trimesh | trimesh.Scene) -> bytes:
    data = mesh_or_scene.export(file_type="stl")
    return data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")


@app.post("/generate", response_model=GenerateRes)
def generate(req: GenerateReq):
    p = {
        "length_mm": req.params.length_mm,
        "width_mm": req.params.width_mm,
        "height_mm": req.params.height_mm,
        "thickness_mm": req.params.thickness_mm or 3.0,
        "fillet_mm": req.params.fillet_mm or 0.0,
    }

    # normaliza claves cable-tray / cable_tray
    variants = {req.model, req.model.replace("-", "_"), req.model.replace("_", "-")}
    builder = None
    for k in variants:
        if k in REGISTRY:
            builder = REGISTRY[k]
            break
        k2 = k.lower()
        if k2 in REGISTRY:
            builder = REGISTRY[k2]
            break

    if builder is None:
        raise RuntimeError(
            f"Modelo desconocido: {req.model}. Disponibles: {', '.join(sorted(REGISTRY.keys()))}"
        )

    mesh = builder(p, req.holes or [])
    stl_bytes = _export_stl(mesh)
    buf = io.BytesIO(stl_bytes)
    buf.seek(0)

    # objeto estable (si quieres firmados con timestamp, cámbialo)
    object_key = f"{req.model}/forge-output.stl"
    url = upload_and_get_url(buf, object_key, bucket=BUCKET, public=PUBLIC_READ)

    return GenerateRes(stl_url=url, object_key=object_key)
