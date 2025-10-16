# apps/stl-service/app.py
import os
import io
import uuid
import base64
from typing import List, Optional, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import numpy as np
import trimesh
from trimesh.creation import cylinder

from supabase_client import upload_and_get_url
from models import REGISTRY  # dict: slug -> { 'types', 'defaults', 'make' }

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
    Aplica agujeros como cilindros restados a lo largo de Z (centrados).
    'holes': [{x, y, r}]
    """
    if not holes:
        return mesh
    base = mesh
    # Altura del cilindro suficientemente grande para atravesar
    height = max(thickness * 4.0, float(mesh.extents[2]) + 10.0)
    for h in holes:
        x = float(h.get("x", 0.0))
        y = float(h.get("y", 0.0))
        r = max(0.1, float(h.get("r", 1.0)))
        cyl = cylinder(radius=r, height=height, sections=64)
        # mover para que atraviese el sólido: centramos en Z del mesh
        # situamos el cilindro con su base en z=0 y lo subimos a mitad de su altura
        cyl.apply_translation((x, y, -height * 0.5))
        # ahora lo centramos en el "centro" del mesh en Z
        cz = float(mesh.bounds.mean(axis=0)[2])
        cyl.apply_translation((0.0, 0.0, cz + height * 0.5))
        diff = _boolean_diff_safe(base, cyl)
        base = diff if isinstance(diff, trimesh.Trimesh) else base
    return base

def _apply_rounding_if_possible(mesh: trimesh.Trimesh, fillet_mm: float) -> trimesh.Trimesh:
    """
    Fillet/chaflán aproximado con manifold3d si está disponible.
    Si no, no hace nada.
    """
    r = float(fillet_mm or 0.0)
    if r <= 0.0:
        return mesh
    try:
        import manifold3d as m3d
        man = m3d.Manifold(mesh)
        # cierre morfológico suave
        smooth = man.Erode(r).Dilate(r)
        return smooth.to_trimesh() if hasattr(smooth, "to_trimesh") else mesh
    except Exception:
        return mesh

def _apply_array(mesh: trimesh.Trimesh, ops: List[Dict[str, float]]) -> trimesh.Trimesh:
    """
    Aplica arrays con desplazamientos (dx, dy).
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

def _apply_text_ops(mesh: trimesh.Trimesh, text_ops: List[Dict[str, Any]]) -> trimesh.Trimesh:
    """
    Extruye textos si está disponible freetype/potrace en trimesh.
    Cada op: { text, size_mm, depth_mm, x, y, z, rotZ_deg, union(True)/diff(False) }
    """
    if not text_ops:
        return mesh

    out = mesh
    for op in text_ops:
        text = str(op.get("text", "")).strip()
        if not text:
            continue
        size = float(op.get("size_mm", 10.0))
        depth = float(op.get("depth_mm", 1.0))
        x = float(op.get("x", 0.0))
        y = float(op.get("y", 0.0))
        z = float(op.get("z", 0.0))
        rot = float(op.get("rotZ_deg", 0.0))
        do_union = bool(op.get("union", True))  # True: graba en relieve (suma). False: graba en hundido (resta)

        try:
            # trimesh tiene creation.text() si freetype está disponible
            glyph = trimesh.creation.text(text, font=None, font_size=size, depth=depth)
            if isinstance(glyph, list):
                glyph = trimesh.util.concatenate(glyph)
            if not isinstance(glyph, trimesh.Trimesh):
                continue
            # Colocar/rotar
            glyph.apply_translation((-glyph.bounds.mean(axis=0)[0], -glyph.bounds.mean(axis=0)[1], 0.0))
            # rotación Z
            if abs(rot) > 1e-6:
                R = trimesh.transformations.rotation_matrix(np.deg2rad(rot), [0, 0, 1])
                glyph.apply_transform(R)
            glyph.apply_translation((x, y, z))

            if do_union:
                # Unión robusta: si falla booleano, concatenamos
                try:
                    tmp = out.union(glyph)
                    if isinstance(tmp, list):
                        tmp = trimesh.util.concatenate(tmp)
                    out = tmp
                except Exception:
                    out = trimesh.util.concatenate([out, glyph])
            else:
                diff = _boolean_diff_safe(out, glyph)
                if isinstance(diff, trimesh.Trimesh):
                    out = diff
        except Exception:
            # si la extrusión de texto no está disponible, lo ignoramos
            continue

    return out

def _to_data_url(stl_bytes: bytes, filename: str) -> str:
    b64 = base64.b64encode(stl_bytes).decode("ascii")
    # name no es estándar pero algunos viewers lo aprovechan
    return f"data:application/sla;name={filename};base64,{b64}"

# ---------------- Schemas ----------------
class GenerateParams(BaseModel):
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    fillet_mm: Optional[float] = 0.0
    holes: List[Dict[str, float]] = Field(default_factory=list)
    textOps: List[Dict[str, Any]] = Field(default_factory=list)
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
    # Normalizamos slug para REGISTRY
    slug = (payload.model or "").strip().lower().replace(" ", "_").replace("-", "_")
    if slug not in REGISTRY:
        # pista: lista de válidos
        return {"ok": False, "error": f"Model '{slug}' not found", "available": list(REGISTRY.keys())}

    entry = REGISTRY[slug]
    defaults = (entry.get("defaults") or {}) if isinstance(entry, dict) else {}
    make = (entry.get("make") if isinstance(entry, dict) else None) or entry.get("builder") or None
    if not callable(make):
        return {"ok": False, "error": f"Model '{slug}' has no builder"}

    # 1) Construcción base del modelo
    params_in = payload.params.model_dump(exclude_none=True) if hasattr(payload.params, "model_dump") else dict(payload.params)
    params = {**defaults, **params_in}
    try:
        built = make(params)
    except Exception as e:
        return {"ok": False, "error": f"Build error: {e}"}

    mesh = _to_mesh(built)
    if not isinstance(mesh, trimesh.Trimesh):
        return {"ok": False, "error": "Builder did not return a mesh"}

    # thickness fiable para perforar
    thickness = float(params.get("thickness_mm") or 3.0)

    # 2) Post-procesado
    mesh = _apply_holes(mesh, params.get("holes", []), thickness)
    mesh = _apply_array(mesh, params.get("arrayOps", []))
    mesh = _apply_text_ops(mesh, params.get("textOps", []))
    mesh = _apply_rounding_if_possible(mesh, float(params.get("fillet_mm") or 0.0))

    # 3) Exportar
    # A veces export() devuelve str si file_type="stl" no está bien; forzamos bytes con BytesIO
    f = io.BytesIO()
    mesh.export(f, file_type="stl")
    stl_bytes = f.getvalue()

    filename = f"{slug}-{uuid.uuid4().hex[:8]}.stl"

    # 4) Subir (si hay credenciales) Y devolver data_url para previsualizar SIEMPRE
    data_url = _to_data_url(stl_bytes, filename)
    upload = upload_and_get_url(stl_bytes, folder=slug, filename=filename)  # acepta bytes o file-like
    url = (upload or {}).get("url")

    return {
        "ok": True,
        "slug": slug,
        "filename": filename,
        "bytes": len(stl_bytes),
        "url": url,                   # puede ser None si no hay credenciales, pero la previsualización funciona
        "data_url": data_url          # el front puede usar esto directamente si quiere
    }
