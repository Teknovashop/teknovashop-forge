# apps/stl-service/app.py
import io
import os
import uuid
from typing import List, Optional, Dict, Any, Union

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import trimesh
from trimesh.creation import cylinder

from supabase_client import upload_and_get_url
from models import REGISTRY  # dict con entradas: { "make": callable, "defaults": {...}, "aliases": [...] }

# ---------------- CORS ----------------
origins = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
app = FastAPI(title="Teknovashop Forge API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Helpers ----------------
def _to_mesh(obj: Any) -> Optional[trimesh.Trimesh]:
    if isinstance(obj, trimesh.Trimesh):
        return obj
    if isinstance(obj, list) and obj and isinstance(obj[0], trimesh.Trimesh):
        try:
            return trimesh.util.concatenate(obj)
        except Exception:
            return obj[0]
    if isinstance(obj, trimesh.Scene):
        try:
            return obj.dump(concatenate=True)
        except Exception:
            return None
    return None


def _boolean_diff_safe(a: trimesh.Trimesh, b: trimesh.Trimesh) -> Optional[trimesh.Trimesh]:
    try:
        out = a.difference(b)
        if isinstance(out, list):
            out = trimesh.util.concatenate(out)
        return out
    except Exception:
        return None


def _apply_holes(mesh: trimesh.Trimesh, holes: List[Dict[str, float]], thickness: float) -> trimesh.Trimesh:
    """
    Agujeros verticales (Z) restando cilindros.
    UI envía: x_mm, y_mm, d_mm  -> radio = d/2
    """
    if not holes:
        return mesh
    base = mesh
    h = max(thickness * 2.5, 5.0)
    for hdef in holes:
        x = float(hdef.get("x_mm", hdef.get("x", 0.0)))
        y = float(hdef.get("y_mm", hdef.get("y", 0.0)))
        d = float(hdef.get("d_mm", hdef.get("d", 2.0)))
        r = max(0.25, d * 0.5)
        cyl = cylinder(radius=r, height=h, sections=64)
        # lo situamos atravesando la placa (asumimos base en Z=0)
        cyl.apply_translation((x, y, h * 0.5))
        diff = _boolean_diff_safe(base, cyl)
        base = diff if isinstance(diff, trimesh.Trimesh) else base
    return base


def _apply_array(mesh: trimesh.Trimesh, ops: List[Dict[str, float]]) -> trimesh.Trimesh:
    if not ops:
        return mesh
    copies = [mesh]
    for op in ops:
        count = int(op.get("count", 1))
        dx = float(op.get("dx", 0.0))
        dy = float(op.get("dy", 0.0))
        for i in range(1, max(1, count)):
            m = mesh.copy()
            m.apply_translation((dx * i, dy * i, 0.0))
            copies.append(m)
    try:
        return trimesh.util.concatenate(copies)
    except Exception:
        return mesh


# ---------------- Schemas ----------------
class TextOp(BaseModel):
    text: str
    x_mm: float = 0
    y_mm: float = 0
    z_mm: float = 0
    height_mm: float = 6
    depth_mm: float = 0.6  # relieve (+) o grabado (-)
    rotate_deg: float = 0


class ArrayOp(BaseModel):
    count: int = 1
    dx: float = 0.0
    dy: float = 0.0


class HoleOp(BaseModel):
    x_mm: float
    y_mm: float
    d_mm: float


class GenerateParams(BaseModel):
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    fillet_mm: Optional[float] = 0.0
    holes: List[HoleOp] = Field(default_factory=list)
    textOps: List[TextOp] = Field(default_factory=list)   # placeholder seguro
    arrayOps: List[ArrayOp] = Field(default_factory=list)


class GeneratePayload(BaseModel):
    model: str
    params: GenerateParams = Field(default_factory=GenerateParams)


# ---------------- Rutas ----------------
@app.get("/health")
async def health():
    return {"status": "ok"}


def _resolve_entry(slug: str) -> Optional[Dict[str, Any]]:
    """Acepta alias declarados en REGISTRY."""
    e = REGISTRY.get(slug)
    if e:
        return e
    # buscar por alias
    for name, entry in REGISTRY.items():
        aliases = (entry.get("aliases") or []) if isinstance(entry, dict) else []
        if slug in aliases:
            return entry
    return None


@app.post("/generate")
async def generate(payload: GeneratePayload):
    try:
        slug = (payload.model or "").replace("-", "_").strip()
        entry = _resolve_entry(slug)
        if not entry:
            return {"ok": False, "error": f"Model '{slug}' not found"}

        defaults = (entry.get("defaults") or {}) if isinstance(entry, dict) else {}
        make = (entry.get("make") if isinstance(entry, dict) else None) or entry.get("builder") or None
        if not callable(make):
            return {"ok": False, "error": f"Model '{slug}' has no builder"}

        # Params finales (prioriza los del payload)
        params_dict = payload.params.model_dump(exclude_none=True)
        params: Dict[str, Any] = {**defaults, **params_dict}

        # Build
        try:
            built = make(params)
        except Exception as e:
            return {"ok": False, "error": f"Build error: {e}"}

        mesh = _to_mesh(built)
        if not isinstance(mesh, trimesh.Trimesh):
            return {"ok": False, "error": "Builder did not return a mesh"}

        thickness = float(params.get("thickness_mm") or 3.0)

        # Post-proceso (no rompe si algo falla)
        try:
            mesh = _apply_holes(mesh, [h.model_dump() for h in payload.params.holes], thickness)
        except Exception:
            pass
        try:
            mesh = _apply_array(mesh, [a.model_dump() for a in payload.params.arrayOps])
        except Exception:
            pass
        # textOps: queda preparado (placeholder sin romper)
        # Si más adelante integras extrusión de fuentes, aplícalo aquí.

        # Export STL
        stl_bytes: Union[bytes, bytearray]
        try:
            stl_bytes = mesh.export(file_type="stl")
        except Exception:
            f = io.BytesIO()
            mesh.export(f, file_type="stl")
            stl_bytes = f.getvalue()

        # Subir a Supabase
        filename = f"{slug}-{uuid.uuid4().hex[:8]}.stl"
        up = upload_and_get_url(stl_bytes, folder=slug, filename=filename)  # acepta bytes o file-like
        url = (up or {}).get("url")

        return {"ok": True, "slug": slug, "url": url, "path": (up or {}).get("path")}
    except Exception as e:
        # Nunca 500: siempre JSON amigable
        return {"ok": False, "error": f"unexpected: {e.__class__.__name__}: {e}"}
