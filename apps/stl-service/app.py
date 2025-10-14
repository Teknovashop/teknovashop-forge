# apps/stl-service/app.py
import io
import os
import math
import traceback
import inspect
from typing import List, Optional, Callable, Dict, Any, Iterable

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError

import numpy as np
import trimesh
from trimesh.creation import box, cylinder

# ---- Registro de modelos (tu paquete)
from models import REGISTRY as MODEL_REGISTRY

# ---- Supabase helpers
from supabase_client import upload_and_get_url

# ============================================================
#                   Utiles comunes
# ============================================================

def _hole_get(h: Any, key: str, default: float = 0.0) -> float:
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

def _boolean_union(meshes: List[trimesh.Trimesh]) -> trimesh.Trimesh:
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

def _boolean_diff(a: trimesh.Trimesh, b_or_list: Any) -> Optional[trimesh.Trimesh]:
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

def _apply_rounding_if_possible(mesh: trimesh.Trimesh, fillet_mm: float) -> trimesh.Trimesh:
    r = float(fillet_mm or 0.0)
    if r <= 0.0:
        return mesh
    try:
        import manifold3d as m3d
        man = m3d.Manifold(mesh)
        smooth = man.Erode(r).Dilate(r)
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

def _frame_scene_for_mesh(mesh: trimesh.Trimesh, width: int, height: int) -> trimesh.Scene:
    scene = trimesh.Scene(mesh)
    bounds = mesh.bounds
    center = bounds.mean(axis=0)
    ext = (bounds[1] - bounds[0])
    diag = float(np.linalg.norm(ext))
    diag = max(diag, 1.0)
    distance = diag * 1.8
    cam = trimesh.scene.cameras.Camera(resolution=(width, height), fov=(60, 45))
    scene.camera = cam

    from trimesh.transformations import rotation_matrix, translation_matrix
    rot = rotation_matrix(math.radians(25), [1, 0, 0]) @ rotation_matrix(math.radians(-30), [0, 0, 1])
    pos = center + np.array([0.0, -distance, distance * 0.6])
    view = np.linalg.inv(translation_matrix(pos) @ rot)
    scene.camera_transform = view
    return scene

def _render_thumbnail_png(
    mesh: trimesh.Trimesh,
    width: int = 900,
    height: int = 600,
    background=(245, 246, 248, 255),
) -> bytes:
    try:
        scene = _frame_scene_for_mesh(mesh, width, height)
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
    # compat con Forge Pro
    operations: Optional[List[Dict[str, Any]]] = []
    outputs: Optional[List[str]] = []

class GenerateRes(BaseModel):
    stl_url: str
    object_key: str
    thumb_url: Optional[str] = None
    svg_url: Optional[str] = None

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
    try:
        models = list(MODEL_REGISTRY.keys())
    except Exception:
        models = []
    return {"ok": True, "models": models}

# ------------------------------------------------------------
#      TEXT helper (fallback con matplotlib)
# ------------------------------------------------------------

def _text_to_mesh(text: str, size_mm: float, depth_mm: float) -> Optional[trimesh.Trimesh]:
    try:
        from matplotlib.textpath import TextPath
        from shapely.geometry import Polygon
        from shapely.ops import unary_union

        tp = TextPath((0, 0), text, size=size_mm)
        polys: Iterable[np.ndarray] = tp.to_polygons(closed_only=True)

        solids: List[trimesh.Trimesh] = []
        for poly in polys:
            if len(poly) < 3:
                continue
            shp = Polygon(poly).buffer(0)
            if shp.is_empty:
                continue
            if shp.geom_type == "Polygon":
                solids.append(trimesh.creation.extrude_polygon(shp, height=depth_mm))
            else:
                merged = unary_union(shp)
                if merged.geom_type == "Polygon":
                    solids.append(trimesh.creation.extrude_polygon(merged, height=depth_mm))
                else:
                    for g in getattr(merged, "geoms", []):
                        if g.geom_type == "Polygon":
                            solids.append(trimesh.creation.extrude_polygon(g, height=depth_mm))
        if not solids:
            return None
        return _boolean_union(solids)
    except Exception as e:
        print("[WARN] Fallback TEXT via matplotlib falló:", e)
        return None

# ------------------------------------------------------------
#      OPERACIONES UNIVERSALES (Forge Pro)
# ------------------------------------------------------------

def _mk_cutout(shape: str, x: float, y: float, L: float, W: float,
               depth: float, z_center: float,
               d: Optional[float] = None,
               w: Optional[float] = None, h: Optional[float] = None) -> trimesh.Trimesh:
    cx = x - L * 0.5
    cy = y - W * 0.5
    depth = max(depth, 0.1)
    if (shape or "").lower() == "circle":
        r = max(0.05, (float(d or 0.0) * 0.5))
        cutter = cylinder(radius=r, height=depth, sections=64)
        cutter.apply_translation((cx, cy, z_center))
        return cutter
    else:
        ww = max(0.1, float(w or 0.0))
        hh = max(0.1, float(h or 0.0))
        cutter = box(extents=(ww, hh, depth))
        cutter.apply_translation((cx, cy, z_center))
        return cutter

def _apply_operations(mesh: trimesh.Trimesh, ops: List[Dict[str, Any]],
                      L: float, W: float, H: float) -> trimesh.Trimesh:
    if not ops:
        return mesh

    current = mesh
    cutters: List[trimesh.Trimesh] = []
    unions: List[trimesh.Trimesh] = []
    extra_fillet: float = 0.0
    topZ = float(current.bounds[1][2])

    for op in ops:
        t = (op.get("type") or "").lower()

        if t == "round":
            extra_fillet = max(extra_fillet, float(op.get("r_mm") or op.get("r") or 0.0))
            continue

        if t == "cutout":
            shape = (op.get("shape") or "circle").lower()
            depth = float(op.get("depth_mm") or H)
            zc = topZ - depth * 0.5
            c = _mk_cutout(
                shape=shape,
                x=float(op.get("x_mm") or 0.0),
                y=float(op.get("y_mm") or 0.0),
                L=L, W=W, depth=depth, z_center=zc,
                d=op.get("d_mm"),
                w=op.get("w_mm"), h=op.get("h_mm"),
            )
            cutters.append(c)
            continue

        if t == "array":
            shape = (op.get("shape") or "circle").lower()
            nx = max(1, int(op.get("nx") or 1))
            ny = max(1, int(op.get("ny") or 1))
            dx = float(op.get("dx_mm") or 10.0)
            dy = float(op.get("dy_mm") or 10.0)
            start_x = float(op.get("start_x_mm") or 0.0)
            start_y = float(op.get("start_y_mm") or 0.0)
            depth = float(op.get("depth_mm") or H)
            zc = topZ - depth * 0.5
            for ix in range(nx):
                for iy in range(ny):
                    x = start_x + ix * dx
                    y = start_y + iy * dy
                    c = _mk_cutout(shape=shape, x=x, y=y, L=L, W=W, depth=depth, z_center=zc,
                                   d=op.get("d_mm"), w=op.get("w_mm"), h=op.get("h_mm"))
                    cutters.append(c)
            continue

        if t == "text":
            txt = str(op.get("text") or "").strip()
            if not txt:
                continue
            size = max(1.0, float(op.get("size_mm") or 10.0))
            depth = max(0.2, float(op.get("depth_mm") or 1.0))
            x = float(op.get("x_mm") or 0.0)
            y = float(op.get("y_mm") or 0.0)
            engrave = bool(op.get("engrave", True))

            txt_mesh = _text_to_mesh(txt, size, depth)
            if txt_mesh is not None:
                bb = txt_mesh.bounds
                sx = x - L * 0.5 - (bb[0][0])
                sy = y - W * 0.5 - (bb[0][1])
                sz = topZ - depth * 0.5
                txt_mesh.apply_translation((sx, sy, sz))
                if engrave:
                    cutters.append(txt_mesh)
                else:
                    unions.append(txt_mesh)
            else:
                print("[WARN] No se pudo generar el texto; se omite.")

    if unions:
        current = _boolean_union([current] + unions)

    if cutters:
        diff = _boolean_diff(current, cutters)
        if diff is not None:
            current = diff
        else:
            print("[WARN] difference batch falló; aplicando por piezas…")
            for c in cutters:
                tmp = _boolean_diff(current, c)
                if tmp is not None:
                    current = tmp

    if extra_fillet > 0.0:
        current = _apply_rounding_if_possible(current, extra_fillet)

    return current

# ------------------------- Resolución de builder (compat firmas) -------------------------

def _pick_callable_from_entry(entry: Any) -> Callable:
    """Devuelve una función callable desde un entry del REGISTRY (callable directo o dict con varias claves)."""
    if callable(entry):
        return entry
    if isinstance(entry, dict):
        for key in ("build", "fn", "make", "factory", "make_model", "model"):
            cand = entry.get(key)
            if callable(cand):
                return cand
    raise HTTPException(
        status_code=500,
        detail="El modelo existe en REGISTRY pero no expone una función callable válida (build/fn/make/factory/make_model)."
    )

def _wrap_builder_any_sig(fn: Callable) -> Callable[[dict, List[Any]], trimesh.Trimesh]:
    """
    Devuelve un wrapper que SIEMPRE acepta (p, holes) y adapta la llamada:
    - si la función acepta 2 args → fn(p, holes)
    - si acepta 1 arg → fn(p)
    - si TypeError por firma, reintenta con la otra forma
    """
    sig = None
    try:
        sig = inspect.signature(fn)
    except Exception:
        pass

    def call(p: dict, holes: List[Any]) -> trimesh.Trimesh:
        # camino rápido usando signature si la tenemos
        if sig:
            pos_or_kw = [v for v in sig.parameters.values()
                         if v.kind in (inspect.Parameter.POSITIONAL_ONLY,
                                       inspect.Parameter.POSITIONAL_OR_KEYWORD)]
            # para métodos bound, len puede ser 1 aunque el origen tuviera self,p
            if len(pos_or_kw) >= 2:
                return fn(p, holes)
            else:
                return fn(p)
        # si no hay signature fiable, probamos 2→1 con catch
        try:
            return fn(p, holes)
        except TypeError:
            return fn(p)
    return call

def _resolve_builder(name: str) -> Callable[[dict, List[Any]], trimesh.Trimesh]:
    if not isinstance(MODEL_REGISTRY, dict):
        raise RuntimeError("El REGISTRY de modelos no es un dict válido.")

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

    fn = _pick_callable_from_entry(entry)
    return _wrap_builder_any_sig(fn)

# ------------------------- Núcleo de generación -------------------------

def _generate_core(req: "GenerateReq") -> Dict[str, Any]:
    p = {
        "length_mm": req.params.length_mm,
        "width_mm": req.params.width_mm,
        "height_mm": req.params.height_mm,
        "thickness_mm": req.params.thickness_mm or 3.0,
        "fillet_mm": req.params.fillet_mm or 0.0,
    }

    builder = _resolve_builder(req.model)

    mesh = builder(p, req.holes or [])

    f = float(p.get("fillet_mm") or 0.0)
    if f > 0:
        mesh = _apply_rounding_if_possible(mesh, f)

    ops = req.operations or []
    mesh = _apply_operations(mesh, ops, p["length_mm"], p["width_mm"], p["height_mm"])

    return {"mesh": mesh, "p": p}

# ------------------------- Generate -------------------------

@app.post("/generate", response_model=GenerateRes)
def generate(req: GenerateReq):
    try:
        out = _generate_core(req)
        mesh = out["mesh"]
        p = out["p"]
    except ValidationError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        print("[ERROR] Fallo al generar mesh:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Fallo al construir '{req.model}': {e}")

    # Export y Upload
    stl_bytes = _export_stl(mesh)
    stl_buf = io.BytesIO(stl_bytes); stl_buf.seek(0)
    base_key = (req.model.replace("_", "-")).lower()
    object_key = f"{base_key}/forge-output.stl"
    try:
        stl_url = upload_and_get_url(stl_buf, object_key, bucket=BUCKET, public=PUBLIC_READ)
    except Exception as e:
        print("[ERROR] Fallo subiendo a Supabase:")
        print(traceback.format_exc())
        msg = str(e)
        if "trailing slash" in msg.lower():
            msg += " (Revisa SUPABASE_URL / storage endpoint: DEBE terminar en '/')."
        raise HTTPException(status_code=500, detail=f"No se pudo subir STL: {msg}")

    # Thumbnail
    thumb_url = None
    try:
        png_bytes = _render_thumbnail_png(mesh, width=900, height=600, background=(245, 246, 248, 255))
        if png_bytes:
            png_buf = io.BytesIO(png_bytes); png_buf.seek(0)
            png_key = f"{base_key}/thumbnail.png"
            thumb_url = upload_and_get_url(png_buf, png_key, bucket=BUCKET, public=PUBLIC_READ)
    except Exception:
        print("[WARN] No se pudo generar miniatura:")
        print(traceback.format_exc())

    # SVG opcional (ejemplo cable_tray)
    svg_url = None
    try:
        want_svg = bool(req.outputs and any(o.lower() == "svg" for o in req.outputs))
        norm_name = req.model.replace("-", "_").lower()
        if want_svg and norm_name == "cable_tray":
            from models.cable_tray import make_svg as cable_tray_make_svg
            svg_text = cable_tray_make_svg(p, req.holes or [])
            if svg_text:
                svg_buf = io.BytesIO(svg_text.encode("utf-8")); svg_buf.seek(0)
                svg_key = f"{base_key}/outline.svg"
                svg_url = upload_and_get_url(svg_buf, svg_key, bucket=BUCKET, public=PUBLIC_READ)
    except Exception:
        print("[WARN] SVG opcional falló:")
        print(traceback.format_exc())

    return GenerateRes(stl_url=stl_url, object_key=object_key, thumb_url=thumb_url, svg_url=svg_url)

# ------------------------- Debug: generar sin subir -------------------------

@app.post("/debug/generate-no-upload")
def debug_generate_no_upload(req: GenerateReq):
    try:
        out = _generate_core(req)
        mesh = out["mesh"]
    except Exception as e:
        print("[ERROR] debug_generate_no_upload:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Fallo al construir '{req.model}': {e}")

    stl_bytes = _export_stl(mesh)
    return {"ok": True, "stl_bytes": len(stl_bytes)}

# ------------------------- Thumbnail -------------------------

class ThumbnailReq(BaseModel):
    model: str
    params: Params
    holes: Optional[List[Hole]] = []

class ThumbnailRes(BaseModel):
    thumb_url: str
    object_key: str

@app.post("/thumbnail", response_model=ThumbnailRes)
def thumbnail(req: ThumbnailReq):
    gen = generate(GenerateReq(model=req.model, params=req.params, holes=req.holes))
    if not gen.thumb_url:
        raise HTTPException(status_code=500, detail="No se pudo generar la miniatura.")
    png_key = gen.object_key.replace("forge-output.stl", "thumbnail.png")
    return ThumbnailRes(thumb_url=gen.thumb_url, object_key=png_key)
