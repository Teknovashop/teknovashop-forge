# apps/app.py
import io
import os
import math
from typing import List, Optional, Callable, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import numpy as np
import trimesh
from trimesh.creation import box, cylinder

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


def _boolean_diff(a: trimesh.Trimesh, b: trimesh.Trimesh) -> Optional[trimesh.Trimesh]:
    """
    Boolean difference con distintos motores. Devuelve None si todos fallan.
    """
    try:
        res = a.difference(b)
        if isinstance(res, trimesh.Trimesh):
            return res
        if isinstance(res, trimesh.Scene):
            return res.dump(concatenate=True)
    except Exception:
        pass

    try:
        from trimesh import boolean
        res = boolean.difference([a, b], engine=None)
        if isinstance(res, trimesh.Trimesh):
            return res
        if isinstance(res, list) and len(res) > 0 and isinstance(res[0], trimesh.Trimesh):
            return trimesh.util.concatenate(res)
        if isinstance(res, trimesh.Scene):
            return res.dump(concatenate=True)
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
        if isinstance(res, trimesh.Trimesh):
            return res
        if isinstance(res, list) and len(res) > 0:
            return trimesh.util.concatenate(res)
        if isinstance(res, trimesh.Scene):
            return res.dump(concatenate=True)
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


# ------------------------- Render PNG -------------------------

def _frame_scene_for_mesh(mesh: trimesh.Trimesh) -> trimesh.Scene:
    """
    Crea una escena con cámara y 'look_at' para enmarcar el mesh.
    """
    scene = trimesh.Scene(mesh)
    # Centro y tamaño
    bounds = mesh.bounds
    center = bounds.mean(axis=0)
    ext = (bounds[1] - bounds[0])
    diag = float(np.linalg.norm(ext))
    diag = max(diag, 1.0)

    # Cámara: ligeramente elevada y ladeada
    distance = diag * 1.8
    # pequeña rotación suave
    rot_euler = trimesh.transformations.euler_matrix(
        math.radians(25),  # pitch
        math.radians(-30), # yaw
        0.0
    )
    cam_tf = trimesh.scene.cameras.look_at(
        points=[center],
        distance=distance,
        rotation=rot_euler
    )
    scene.camera_transform = cam_tf

    # Luz ambiental simple (el rasterizador de trimesh aplica shading básico)
    return scene


def _render_thumbnail_png(mesh: trimesh.Trimesh,
                          width: int = 800,
                          height: int = 600,
                          background=(245, 246, 248, 255)) -> bytes:
    """
    Render offscreen de una miniatura PNG. Requiere las dependencias de render
    de trimesh (pyglet/pyopengl) en el entorno. Si falla, se devuelve un
    wireframe fallback dibujado con PIL.
    """
    try:
        scene = _frame_scene_for_mesh(mesh)
        img = scene.save_image(resolution=(width, height), background=background)
        if isinstance(img, (bytes, bytearray)):
            return bytes(img)
    except Exception as e:
        print("[WARN] Render offscreen falló, fallback PIL:", e)

    # Fallback: dibujar bounding y silueta básica en PIL
    try:
        from PIL import Image, ImageDraw
        im = Image.new("RGBA", (width, height), background)
        dr = ImageDraw.Draw(im)
        # dibuja rectángulo central y texto
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
#        MODELOS – define aquí cada geometría
# ============================================================

def mdl_cable_tray(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(1.0, float(p.get("thickness_mm") or 3.0))

    outer = box(extents=(L, W, H))
    outer.apply_translation((0, 0, H * 0.5))

    inner = box(extents=(L - 2 * T, W - 2 * T, H + 2.0))
    inner.apply_translation((0, 0, H))

    hollow = _boolean_diff(outer, inner) or outer
    hollow = _apply_top_holes(hollow, holes, L, W, H)
    return hollow


def mdl_vesa_adapter(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(2.0, float(p.get("thickness_mm") or 4.0))
    H = max(H, T)

    plate = box(extents=(L, W, T))
    plate.apply_translation((0, 0, T * 0.5))

    plate = _apply_top_holes(plate, holes, L, W, T)
    return plate


def mdl_router_mount(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(2.0, float(p.get("thickness_mm") or 3.0))

    base = box(extents=(L, W, T))
    base.apply_translation((0, 0, T * 0.5))

    vertical = box(extents=(L, T, H))
    vertical.apply_translation((0, (W * 0.5 - T * 0.5), H * 0.5))

    mesh = _boolean_union([base, vertical])
    mesh = _apply_top_holes(mesh, holes, L, W, max(H, T))
    return mesh


def mdl_camera_mount(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(2.0, float(p.get("thickness_mm") or 3.0))

    base = box(extents=(L, W, T))
    base.apply_translation((0, 0, T * 0.5))

    col_h = min(max(H - T, 10.0), H)
    col = box(extents=(T * 2.0, T * 2.0, col_h))
    col.apply_translation((0, 0, T + col_h * 0.5))

    mesh = _boolean_union([base, col])
    mesh = _apply_top_holes(mesh, holes, L, W, T + col_h)
    return mesh


def mdl_wall_bracket(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(3.0, float(p.get("thickness_mm") or 4.0))

    horiz = box(extents=(L, W, T))
    horiz.apply_translation((0, 0, T * 0.5))

    vert = box(extents=(T, W, H))
    vert.apply_translation((L * 0.5 - T * 0.5, 0, H * 0.5))

    mesh = _boolean_union([horiz, vert])
    mesh = _apply_top_holes(mesh, holes, L, W, max(H, T))
    return mesh


# Registro de modelos
REGISTRY: Dict[str, Callable[[dict, List[Any]], trimesh.Trimesh]] = {
    "cable_tray": mdl_cable_tray,
    "vesa_adapter": mdl_vesa_adapter,
    "router_mount": mdl_router_mount,
    "camera_mount": mdl_camera_mount,
    "wall_bracket": mdl_wall_bracket,
}

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
    model: str = Field(..., description="cable_tray | vesa_adapter | router_mount | camera_mount | wall_bracket")
    params: Params
    holes: Optional[List[Hole]] = []

class GenerateRes(BaseModel):
    stl_url: str
    object_key: str
    thumb_url: Optional[str] = None  # << añadimos miniatura

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

# ------------------------- Generate STL + PNG -------------------------

@app.post("/generate", response_model=GenerateRes)
def generate(req: GenerateReq):
    p = {
        "length_mm": req.params.length_mm,
        "width_mm": req.params.width_mm,
        "height_mm": req.params.height_mm,
        "thickness_mm": req.params.thickness_mm or 3.0,
        "fillet_mm": req.params.fillet_mm or 0.0,
    }

    # normaliza nombres
    candidates = {
        req.model,
        req.model.replace("-", "_"),
        req.model.replace("_", "-"),
        req.model.lower(),
        req.model.lower().replace("-", "_"),
        req.model.lower().replace("_", "-"),
    }

    builder: Optional[Callable[[dict, List[Any]], trimesh.Trimesh]] = None
    for k in candidates:
        if k in REGISTRY:
            builder = REGISTRY[k]
            break
    if builder is None:
        raise RuntimeError(f"Modelo desconocido: {req.model}. Disponibles: {', '.join(REGISTRY.keys())}")

    # Construye la malla base
    mesh = builder(p, req.holes or [])

    # Fillet / chaflán aproximado si procede
    f = float(p.get("fillet_mm") or 0.0)
    if f > 0:
        mesh = _apply_rounding_if_possible(mesh, f)

    # Exportar STL
    stl_bytes = _export_stl(mesh)
    stl_buf = io.BytesIO(stl_bytes); stl_buf.seek(0)

    # Guardar en Supabase
    base_key = req.model.replace("_", "-")
    object_key = f"{base_key}/forge-output.stl"
    stl_url = upload_and_get_url(stl_buf, object_key, bucket=BUCKET, public=PUBLIC_READ)

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
    # Reusar mismo pipeline
    gen = generate(GenerateReq(model=req.model, params=req.params, holes=req.holes))
    if not gen.thumb_url:
        raise RuntimeError("No se pudo generar la miniatura.")
    # Clave PNG inferida del object_key (stl)
    png_key = gen.object_key.replace("forge-output.stl", "thumbnail.png")
    return ThumbnailRes(thumb_url=gen.thumb_url, object_key=png_key)
