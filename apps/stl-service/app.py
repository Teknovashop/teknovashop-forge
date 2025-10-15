# apps/stl-service/app.py
import os
import io
import uuid
from typing import List, Optional, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import numpy as np
import trimesh
from trimesh.creation import cylinder

from supabase_client import upload_and_get_url
from models import REGISTRY  # dict: name -> { defaults, make/builder, ... }

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
    if not holes:
        return mesh
    base = mesh
    for h in holes:
        x = float(h.get("x", h.get("x_mm", 0.0)))
        y = float(h.get("y", h.get("y_mm", 0.0)))
        if "r" in h:
            r = float(h["r"])
        else:
            d = float(h.get("d", h.get("d_mm", 0.0)) or 0.0)
            r = float(h.get("r", d / 2.0 if d > 0 else 2.0))
        r = max(0.1, r)

        cyl = cylinder(radius=r, height=max(thickness * 3.0, 8.0), sections=64)
        cyl.apply_translation((x, y, cyl.extents[2] * 0.5))
        diff = _boolean_diff_safe(base, cyl)
        base = diff if isinstance(diff, trimesh.Trimesh) else base
    return base


def _apply_rounding_if_possible(mesh: trimesh.Trimesh, fillet_mm: float) -> trimesh.Trimesh:
    r = float(fillet_mm or 0.0)
    if r <= 0.0:
        return mesh
    try:
        import manifold3d as m3d
        man = m3d.Manifold(mesh)
        smooth = man.Erode(r).Dilate(r)
        return smooth.to_trimesh() if hasattr(smooth, "to_trimesh") else mesh
    except Exception:
        return mesh


def _apply_array(mesh: trimesh.Trimesh, ops: List[Dict[str, float]]) -> trimesh.Trimesh:
    if not ops:
        return mesh
    copies = [mesh]
    for op in ops:
        count = max(1, int(op.get("count", 1)))
        dx = float(op.get("dx", 0.0))
        dy = float(op.get("dy", 0.0))
        for i in range(1, count):
            m = mesh.copy()
            m.apply_translation((dx * i, dy * i, 0.0))
            copies.append(m)
    try:
        return trimesh.util.concatenate(copies)
    except Exception:
        return mesh

# ---------------- Schemas ----------------
class GenerateParams(BaseModel):
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    fillet_mm: Optional[float] = 0.0
    holes: List[Dict[str, float]] = Field(default_factory=list)
    textOps: List[Dict[str, float]] = Field(default_factory=list)
    arrayOps: List[Dict[str, float]] = Field(default_factory=list)


class GeneratePayload(BaseModel):
    model: str
    params: GenerateParams = Field(default_factory=GenerateParams)
    # compat: estos pueden venir a nivel raíz
    holes: List[Dict[str, float]] = Field(default_factory=list)
    arrayOps: List[Dict[str, float]] = Field(default_factory=list)
    textOps: List[Dict[str, float]] = Field(default_factory=list)

# ---------------- Rutas ----------------
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/generate")
async def generate(payload: GeneratePayload):
    slug = (payload.model or "").replace("-", "_").strip()
    if slug not in REGISTRY:
        return JSONResponse({"ok": False, "error": f"Model '{slug}' not found"}, status_code=404)

    entry = REGISTRY[slug]
    defaults = (entry.get("defaults") or {}) if isinstance(entry, dict) else {}
    make = (entry.get("make") if isinstance(entry, dict) else None) or entry.get("builder")
    if not callable(make):
        return JSONResponse({"ok": False, "error": f"Model '{slug}' has no builder"}, status_code=500)

    base_params = payload.params.model_dump(exclude_none=True)
    if payload.holes and not base_params.get("holes"):
        base_params["holes"] = payload.holes
    if payload.arrayOps and not base_params.get("arrayOps"):
        base_params["arrayOps"] = payload.arrayOps
    if payload.textOps and not base_params.get("textOps"):
        base_params["textOps"] = payload.textOps

    params: Dict[str, Any] = {**defaults, **base_params}

    try:
        built = make(params)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"Build error: {e}"}, status_code=400)

    mesh = _to_mesh(built)
    if not isinstance(mesh, trimesh.Trimesh):
        return JSONResponse({"ok": False, "error": "Builder did not return a mesh"}, status_code=400)

    thickness = float(params.get("thickness_mm") or 3.0)

    mesh = _apply_holes(mesh, params.get("holes", []), thickness)
    mesh = _apply_array(mesh, params.get("arrayOps", []))
    mesh = _apply_rounding_if_possible(mesh, float(params.get("fillet_mm") or 0.0))

    try:
        stl_bytes = mesh.export(file_type="stl")
        if not isinstance(stl_bytes, (bytes, bytearray)):
            buf = io.BytesIO()
            mesh.export(buf, file_type="stl")
            stl_bytes = buf.getvalue()
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"Export error: {e}"}, status_code=500)

    filename = f"{slug}-{uuid.uuid4().hex[:8]}.stl"
    try:
        uploaded = upload_and_get_url(io.BytesIO(stl_bytes), folder=slug, filename=filename)
        url = (uploaded or {}).get("url")
        if not url:
            return JSONResponse({"ok": False, "error": "upload-failed", "detail": uploaded}, status_code=502)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"upload-exception: {e!s}"}, status_code=502)

    faces = int(getattr(mesh, "faces", np.empty((0, 3))).shape[0])
    bounds = getattr(mesh, "bounds", None)
    meta_bounds = bounds.tolist() if bounds is not None else None

    return JSONResponse(
        {
            "ok": True,
            "model": slug,
            "stl_url": url,
            "filename": filename,
            "meta": {"triangles": faces, "bounds": meta_bounds},
        },
        status_code=200,
    )
