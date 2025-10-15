# apps/stl-service/app.py
import io
import os
import math
from typing import List, Optional, Callable, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError

import numpy as np
import trimesh
from trimesh.creation import box, cylinder

# ---- Registro de modelos: usa el paquete con TODOS los modelos ----
# (Tu __init__.py de models ya registra 16; aquí solo lo consumimos)
from models import REGISTRY as MODEL_REGISTRY

# ---- Supabase helpers (los tuyos) ----
from supabase_client import upload_and_get_url


# ============================================================
#                   Utiles comunes
# ============================================================

def _hole_get(h: Any, key: str, default: float = 0.0) -> float:
    """
    Lee un campo de un 'hole' que puede ser un dict o un BaseModel.
    """
    if isinstance(h, dict):
        v = h.get(key, default)
    else:
        v = getattr(h, key, default)
    try:
        return float(v if v is not None else default)
    except Exception:
        return float(default)


def _as_mesh(obj: Any) -> Optional[trimesh.Trimesh]:
    if isinstance(obj, trimesh.Trimesh):
        return obj
    if isinstance(obj, trimesh.Scene):
        return obj.dump(concatenate=True)
    return None


def _boolean_diff(a: trimesh.Trimesh, b_or_list: Any) -> Optional[trimesh.Trimesh]:
    """
    Boolean difference robusta con fallback; admite un mesh o una lista de cutters.
    """
    cutters: List[trimesh.Trimesh] = []
    if isinstance(b_or_list, (list, tuple)):
        for el in b_or_list:
            m = _as_mesh(el)
            if isinstance(el, trimesh.Trimesh):
                cutters.append(el)
            elif m is not None:
                cutters.append(m)
    else:
        m = _as_mesh(b_or_list)
        if isinstance(b_or_list, trimesh.Trimesh):
            cutters.append(b_or_list)
        elif m is not None:
            cutters.append(m)

    current = a
    try:
        for c in cutters:
            res = current.difference(c)
            m = _as_mesh(res)
            if m is None:
                raise RuntimeError("difference fallback")
            current = m
        return current
    except Exception:
        pass

    try:
        from trimesh import boolean
        if cutters:
            res = boolean.difference([current] + cutters, engine=None)
        else:
            res = current
        m = _as_mesh(res)
        if m is not None:
            return m
        if isinstance(res, list) and len(res) > 0:
            return trimesh.util.concatenate([_as_mesh(x) or x for x in res])
    except Exception:
        pass

    return None


def _boolean_union(meshes: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    """
    Unión robusta con fallbacks. Si falla, concatena pura.
    """
    meshes = [m for m in meshes if isinstance(m, trimesh.Trimesh)]
    if not meshes:
        return trimesh.Trimesh()
    if len(meshes) == 1:
        return meshes[0]

    try:
        from trimesh import boolean
        res = boolean.union(meshes, engine=None)
        m = _as_mesh(res)
        if m is not None:
            return m
        if isinstance(res, list) and len(res) > 0:
            return trimesh.util.concatenate([_as_mesh(x) or x for x in res])
    except Exception:
        pass

    return trimesh.util.concatenate(meshes)


def _apply_top_holes(solid: trimesh.Trimesh, holes: List[Any], L: float, W: float, H: float) -> trimesh.Trimesh:
    """
    Taladros pasantes desde la cara superior (Z+) con diámetro d_mm y
    coordenadas (x_mm, y_mm) en el plano superior (0..L, 0..W).
    Si los motores CSG fallan, deja la pieza tal cual (no rompe).
    """
    current = solid
    for h in holes or []:
        d_mm = _hole_get(h, "d_mm", 0.0)
        if d_mm <= 0:
            continue
        r = max(0.05, d_mm * 0.5)

        x_mm = _hole_get(h, "x_mm", 0.0)  # 0..L
        y_mm = _hole_get(h, "y_mm", 0.0)  # 0..W

        # coords centradas del mesh
        cx = x_mm - L * 0.5
        cy = y_mm - W * 0.5

        drill = cylinder(radius=r, height=max(H * 1.5, 20.0), sections=64)
        drill.apply_translation((cx, cy, H * 0.5))

        diff = _boolean_diff(current, drill)
        if diff is not None:
            current = diff
        else:
            print("[WARN] No se pudo aplicar un agujero (CSG no disponible). Continuo…")

    return current


def _apply_rounding_if_possible(mesh: trimesh.Trimesh, fillet_mm: float) -> trimesh.Trimesh:
    """
    Fillet/chaflán aproximado. Si no hay manifold3d, ignora (no rompe).
    """
    r = float(fillet_mm or 0.0)
    if r <= 0.0:
        return mesh

    try:
        import manifold3d as m3d
        man = m3d.Manifold(mesh)
        smooth = man.Erode(r).Dilate(r)  # closing morfológico
        out = smooth.to_trimesh()
        if isinstance(out, trimesh.Trimesh):
            return out
    except Exception:
        print("[INFO] Fillet ignorado (manifold3d no disponible o falló).")

    return mesh


def _export_stl(mesh_or_scene: trimesh.Trimesh | trimesh.Scene) -> bytes:
    data = mesh_or_scene.export(file_type="stl")
    return data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")


# ------------------------- Render PNG (misma cámara del visor anterior) -------------------------

def _frame_scene_for_mesh(mesh: trimesh.Trimesh) -> trimesh.Scene:
    """
    Crea una escena con cámara y 'look_at' para enmarcar el mesh (ángulo clásico).
    """
    scene = trimesh.Scene(mesh)
    bounds = mesh.bounds
    center = bounds.mean(axis=0)
    ext = (bounds[1] - bounds[0])
    diag = float(np.linalg.norm(ext))
    diag = max(diag, 1.0)

    # Cámara: ligeramente elevada y ladeada
    distance = diag * 1.8
    rot_euler = trimesh.transformations.euler_matrix(
        math.radians(25),   # pitch
        math.radians(-30),  # yaw
        0.0
    )
    cam_tf = trimesh.scene.cameras.look_at(
        points=[center],
        distance=distance,
        rotation=rot_euler
    )
    scene.camera_transform = cam_tf
    return scene


def _render_thumbnail_png(
    mesh: trimesh.Trimesh,
    width: int = 900,
    height: int = 600,
    background=(245, 246, 248, 255),
) -> bytes:
    """
    Render offscreen de una miniatura PNG. Si el raster offscreen no está
    disponible, dibuja un fallback con PIL.
    """
    try:
        scene = _frame_scene_for_mesh(mesh)
        img = scene.save_image(resolution=(width, height), background=background)
        if isinstance(img, (bytes, bytearray)):
            return bytes(img)
    except Exception as e:
        print("[WARN] Render offscreen falló, fallback PIL:", e)

    try:
        from PIL import Image, ImageDraw
        im = Image.new("RGBA", (width, height), background)
        dr = ImageDraw.Draw(im)
        pad = 24
        dr.rounded_rectangle(
            [pad, pad, width - pad, height - pad],
            radius=18,
            outline=(180, 186, 193, 255),
            width=2,
            fill=(250, 251, 252, 255)
        )
        dr.text((pad + 12, pad + 12), "Vista previa (fallback)", fill=(90, 96, 102, 255))
        out = io.BytesIO()
        im.save(out, format="PNG")
        return out.getvalue()
    except Exception as e:
        print("[ERROR] Fallback PIL también falló:", e)
        return b""


# ============================================================
#               FastAPI + modelos de request/response
# ============================================================

CORS_ALLOW_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()] or ["*"]
BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")
PUBLIC_READ = os.getenv("SUPABASE_PUBLIC_READ", "0") == "1"

class Hole(BaseModel):
    x_mm: float = 0
    y_mm: float = 0
    d_mm: float = 0

class Params(BaseModel):
    length_mm: float = Field(..., gt=0)
    width_mm: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    thickness_mm: Optional[float] = Field(default=3, gt=0)
    fillet_mm: Optional[float] = Field(default=0, ge=0)

class GenerateReq(BaseModel):
    model: str
    params: Params
    holes: Optional[List[Hole]] = []

class GenerateRes(BaseModel):
    stl_url: str
    object_key: str
    thumb_url: Optional[str] = None  # miniatura


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
    # lista todo lo que haya en el paquete models (16 si están los archivos)
    try:
        models = list(MODEL_REGISTRY.keys())
    except Exception:
        models = []
    return {"ok": True, "models": models}


# ------------------------- Resolver builder desde REGISTRY del paquete -------------------------

def _resolve_builder(name: str) -> Callable[[dict, List[Any]], trimesh.Trimesh]:
    """
    El REGISTRY del paquete mapea:
      name -> {"make": function, "defaults": ..., "types": ...}
    Aceptamos alias con guiones/bajos y mayúsculas/minúsculas.
    """
    if not isinstance(MODEL_REGISTRY, dict):
        raise HTTPException(status_code=500, detail="REGISTRY inválido.")

    variations = {
        name,
        name.replace("-", "_"),
        name.replace("_", "-"),
        name.lower(),
        name.lower().replace("-", "_"),
        name.lower().replace("_", "-"),
    }

    entry = None
    for k in variations:
        if k in MODEL_REGISTRY:
            entry = MODEL_REGISTRY[k]
            break

    if entry is None:
        raise HTTPException(
            status_code=400,
            detail=f"Modelo desconocido: {name}. Disponibles: {', '.join(MODEL_REGISTRY.keys())}"
        )

    if isinstance(entry, dict):
        make = entry.get("make") or entry.get("make_model")
        if callable(make):
            def wrap(p: dict, holes: List[Any]) -> trimesh.Trimesh:
                # Por compatibilidad: algunos modelos aceptan 'holes' en p
                q = dict(p)
                if holes:
                    q["holes"] = holes
                return make(q)  # type: ignore[misc]
            return wrap

    if callable(entry):
        # Compat: si algún día registráis funciones directas
        def wrap2(p: dict, holes: List[Any]) -> trimesh.Trimesh:
            return entry(p)  # type: ignore[misc]
        return wrap2

    raise HTTPException(status_code=500, detail=f"El modelo '{name}' no expone make/make_model callable.")


# ------------------------- Generate STL + PNG -------------------------

@app.post("/generate", response_model=GenerateRes)
def generate(req: GenerateReq):
    try:
        p = {
            "length_mm": req.params.length_mm,
            "width_mm": req.params.width_mm,
            "height_mm": req.params.height_mm,
            "thickness_mm": req.params.thickness_mm or 3.0,
            "fillet_mm": req.params.fillet_mm or 0.0,
        }
    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    builder = _resolve_builder(req.model)

    # Construye la malla base
    try:
        mesh = builder(p, req.holes or [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fallo al construir '{req.model}': {e}")

    # Fillet / chaflán aproximado si procede (por si el modelo no lo hace internamente)
    f = float(p.get("fillet_mm") or 0.0)
    if f > 0:
        mesh = _apply_rounding_if_possible(mesh, f)

    # Exportar STL
    stl_bytes = _export_stl(mesh)
    stl_buf = io.BytesIO(stl_bytes); stl_buf.seek(0)

    # Guardar en Supabase
    base_key = (req.model.replace("_", "-")).lower()
    object_key = f"{base_key}/forge-output.stl"
    try:
        stl_url = upload_and_get_url(stl_buf, object_key, bucket=BUCKET, public=PUBLIC_READ)
    except Exception as e:
        msg = str(e)
        if "trailing slash" in msg.lower():
            msg += " (Revisa SUPABASE_URL de storage: debe terminar en '/')."
        raise HTTPException(status_code=500, detail=f"No se pudo subir STL: {msg}")

    # Render PNG y subir
    thumb_url = None
    try:
        png_bytes = _render_thumbnail_png(mesh, width=900, height=600, background=(245, 246, 248, 255))
        if png_bytes:
            png_buf = io.BytesIO(png_bytes); png_buf.seek(0)
            png_key = f"{base_key}/thumbnail.png"
            thumb_url = upload_and_get_url(png_buf, png_key, bucket=BUCKET, public=PUBLIC_READ)
    except Exception as e:
        print("[WARN] No se pudo generar miniatura:", e)

    return GenerateRes(stl_url=stl_url, object_key=object_key, thumb_url=thumb_url)


# ------------------------- Solo PNG opcional -------------------------

class ThumbnailReq(BaseModel):
    model: str
    params: Params
    holes: Optional[List[Hole]] = []

class ThumbnailRes(BaseModel):
    thumb_url: str
    object_key: str

@app.post("/thumbnail", response_model=ThumbnailRes)
def thumbnail(req: ThumbnailReq):
    """
    Genera SOLO la miniatura PNG en el bucket, sin guardar STL.
    """
    gen = generate(GenerateReq(model=req.model, params=req.params, holes=req.holes))
    if not gen.thumb_url:
        raise HTTPException(status_code=500, detail="No se pudo generar la miniatura.")
    png_key = gen.object_key.replace("forge-output.stl", "thumbnail.png")
    return ThumbnailRes(thumb_url=gen.thumb_url, object_key=png_key)
