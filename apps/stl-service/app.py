# apps/stl-service/app.py
import os
import io
import uuid
import base64
from typing import List, Optional, Dict, Any, Union

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import numpy as np
import trimesh
from trimesh.creation import cylinder, box

from supabase_client import upload_and_get_url
from models import (
    REGISTRY,                      # dict: name -> { types, defaults, make/builder }
)

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
    """
    Convierte lo que devuelva el generador a una Trimesh.
    Acepta:
      - Trimesh
      - Lista de Trimesh
      - Scene (dump concatenado)
    """
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
    Aplica agujeros como cilindros restados a lo largo de Z.
    'holes': [{x, y, r}]
    """
    if not holes:
        return mesh
    base = mesh
    for h in holes:
        x = float(h.get("x", 0.0))
        y = float(h.get("y", 0.0))
        r = max(0.1, float(h.get("r", 1.0)))
        cyl = cylinder(radius=r, height=max(thickness * 2.5, 5.0), sections=48)
        cyl.apply_translation((x, y, cyl.extents[2] * 0.5))
        diff = _boolean_diff_safe(base, cyl)
        base = diff if isinstance(diff, trimesh.Trimesh) else base
    return base

def _apply_rounding_if_possible(mesh: trimesh.Trimesh, fillet_mm: float) -> trimesh.Trimesh:
    """
    Fillet/chaflán aproximado con manifold3d si está disponible.
    Si no, no hace nada (no rompe).
    """
    r = float(fillet_mm or 0.0)
    if r <= 0.0:
        return mesh
    try:
        import manifold3d as m3d
        man = m3d.Manifold(mesh)
        smooth = man.Erode(r).Dilate(r)  # cierre morfológico
        return smooth.to_trimesh() if hasattr(smooth, "to_trimesh") else mesh
    except Exception:
        return mesh

def _apply_array(mesh: trimesh.Trimesh, ops: List[Dict[str, float]]) -> trimesh.Trimesh:
    """
    Aplica arrays de duplicación con desplazamientos (dx, dy).
    Si algo falla, concatena sin booleanos.
    """
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

def _export_stl_bytes(mesh: trimesh.Trimesh) -> bytes:
    if hasattr(mesh, "export"):
        try:
            return mesh.export(file_type="stl")
        except Exception:
            pass
    f = io.BytesIO()
    mesh.export(f, file_type="stl")
    return f.getvalue()

def _ensure_not_empty(mesh: Optional[trimesh.Trimesh]) -> trimesh.Trimesh:
    """
    Si el generador devolviera None o una malla degenerada, fabricamos
    un cubo 10x10x3mm para que el visor no quede vacío.
    """
    if isinstance(mesh, trimesh.Trimesh) and mesh.vertices.size >= 3:
        return mesh
    # cubito centrado
    fallback = box(extents=(10.0, 10.0, 3.0))
    fallback.apply_translation((0, 0, 1.5))
    return fallback

# ---------------- Schemas ----------------
class GenerateParams(BaseModel):
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    fillet_mm: Optional[float] = 0.0
    holes: List[Dict[str, float]] = Field(default_factory=list)
    textOps: List[Dict[str, float]] = Field(default_factory=list)   # placeholder
    arrayOps: List[Dict[str, float]] = Field(default_factory=list)

class GeneratePayload(BaseModel):
    model: str
    params: GenerateParams = Field(default_factory=GenerateParams)

# ---------------- Rutas ----------------
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/generate")
async def generate(payload: GeneratePayload):
    try:
        slug = (payload.model or "").replace("-", "_").strip()
        if slug not in REGISTRY:
            return {"ok": False, "error": f"Model '{slug}' not found"}

        entry = REGISTRY[slug]
        defaults = (entry.get("defaults") or {}) if isinstance(entry, dict) else {}
        make = (entry.get("make") if isinstance(entry, dict) else None) or entry.get("builder") or None
        if not callable(make):
            return {"ok": False, "error": f"Model '{slug}' has no builder"}

        # 1) Construcción base del modelo
        params = {
            **defaults,
            **(payload.params.model_dump(exclude_none=True) if hasattr(payload.params, "model_dump") else dict(payload.params))
        }

        try:
            built = make(params)
        except Exception as e:
            return {"ok": False, "error": f"Build error: {e}"}

        mesh = _ensure_not_empty(_to_mesh(built))

        # Necesario para agujeros: grosor
        thickness = float(params.get("thickness_mm") or 3.0)

        # 2) Post-procesado
        mesh = _apply_holes(mesh, params.get("holes", []), thickness)
        mesh = _apply_array(mesh, params.get("arrayOps", []))
        mesh = _apply_rounding_if_possible(mesh, float(params.get("fillet_mm") or 0.0))
        # textOps: reservado (sin cambios)

        # 3) Exportar STL (bytes) + data URL inline SIEMPRE
        stl_bytes = _export_stl_bytes(mesh)
        stl_b64 = base64.b64encode(stl_bytes).decode("ascii")
        stl_data_url = f"data:model/stl;base64,{stl_b64}"

        # 4) Subir (no bloqueante para pintar en el visor)
        url: Optional[str] = None
        try:
            filename = f"{slug}-{uuid.uuid4().hex[:8]}.stl"
            up = upload_and_get_url(stl_bytes, folder=slug, filename=filename)  # acepta bytes o file-like
            url = (up or {}).get("url")
        except Exception as e:
            # No rompemos la respuesta: el visor podrá usar stlData
            url = None

        return {"ok": True, "slug": slug, "url": url, "stlData": stl_data_url}

    except Exception as e:
        return {"ok": False, "error": f"unexpected: {type(e).__name__}: {e}"}
