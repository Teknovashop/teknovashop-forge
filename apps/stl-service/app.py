# apps/stl-service/app.py
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

    # intento iterativo
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

    # intento motor boolean
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


def _apply_top_holes(solid: trimesh.Trimesh, holes: List[Any], L: float, W: float, H: float) -> trimesh.Trimesh:
    current = solid
    for h in holes or []:
        d_mm = _hole_get(h, "d_mm", 0.0)
        if d_mm <= 0:
            continue
        r = max(0.05, d_mm * 0.5)

        x_mm = _hole_get(h, "x_mm", 0.0)
        y_mm = _hole_get(h, "y_mm", 0.0)

        cx = x_mm - L * 0.5
        cy = y_mm - W * 0.5

        drill = cylinder(radius=r, height=max(H * 1.5, 20.0), sections=64)
        drill.apply_translation((cx, cy, H * 0.5))

        diff = _boolean_diff(current, drill)
        if diff is not None:
            current = diff
        else:
            print("[WARN] No se pudo aplicar un agujero (CSG no disponible).")
    return current


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

def _frame_scene_for_mesh(mesh: trimesh.Trimesh) -> trimesh.Scene:
    scene = trimesh.Scene(mesh)
    bounds = mesh.bounds
    center = bounds.mean(axis=0)
    ext = (bounds[1] - bounds[0])
    diag = float(np.linalg.norm(ext))
    diag = max(diag, 1.0)

    distance = diag * 1.8
    rot_euler = trimesh.transformations.euler_matrix(
        math.radians(25),
        math.radians(-30),
        0.0
    )
    cam_tf = trimesh.scene.cameras.look_at(points=[center], distance=distance, rotation=rot_euler)
    scene.camera_transform = cam_tf
    return scene


def _render_thumbnail_png(
    mesh: trimesh.Trimesh,
    width: int = 900,
    height: int = 600,
    background=(245, 246, 248, 255),
) -> bytes:
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
#        MODELOS – geometrías base
# ============================================================

def mdl_cable_tray(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(1.0, float(p.get("thickness_mm") or 3.0))
    # U hueca: laterales y base
    outer = box(extents=(L, W, H)); outer.apply_translation((0, 0, H * 0.5))
    inner = box(extents=(L - 2 * T, W - 2 * T, H + 2.0)); inner.apply_translation((0, 0, H))
    hollow = _boolean_diff(outer, inner) or outer
    hollow = _apply_top_holes(hollow, holes, L, W, H)
    return hollow


def mdl_vesa_adapter(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W = float(p["length_mm"]), float(p["width_mm"])
    T = max(2.0, float(p.get("thickness_mm") or 4.0))
    plate = box(extents=(L, W, T)); plate.apply_translation((0, 0, T * 0.5))
    return _apply_top_holes(plate, holes, L, W, T)


def mdl_router_mount(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(2.0, float(p.get("thickness_mm") or 3.0))
    base = box(extents=(L, W, T)); base.apply_translation((0, 0, T * 0.5))
    vertical = box(extents=(L, T, H)); vertical.apply_translation((0, (W * 0.5 - T * 0.5), H * 0.5))
    mesh = _boolean_union([base, vertical])
    return _apply_top_holes(mesh, holes, L, W, max(H, T))


def mdl_camera_mount(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(2.0, float(p.get("thickness_mm") or 3.0))
    base = box(extents=(L, W, T)); base.apply_translation((0, 0, T * 0.5))
    col_h = min(max(H - T, 10.0), H)
    col = box(extents=(T * 2.0, T * 2.0, col_h)); col.apply_translation((0, 0, T + col_h * 0.5))
    mesh = _boolean_union([base, col])
    return _apply_top_holes(mesh, holes, L, W, T + col_h)


def mdl_wall_bracket(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(3.0, float(p.get("thickness_mm") or 4.0))
    horiz = box(extents=(L, W, T)); horiz.apply_translation((0, 0, T * 0.5))
    vert = box(extents=(T, W, H)); vert.apply_translation((L * 0.5 - T * 0.5, 0, H * 0.5))
    mesh = _boolean_union([horiz, vert])
    return _apply_top_holes(mesh, holes, L, W, max(H, T))


def mdl_fan_guard(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    D_out = float(p["length_mm"]); D_in = float(p["width_mm"])
    Tz = max(2.0, float(p.get("height_mm") or 4.0))
    R_out = max(1.0, D_out * 0.5); R_in = max(0.1, D_in * 0.5)
    if R_in >= R_out: R_in = R_out * 0.6
    outer = cylinder(radius=R_out, height=Tz, sections=96)
    inner = cylinder(radius=R_in, height=Tz + 2.0, sections=96)
    ring = _boolean_diff(outer, inner) or outer
    ring = _apply_top_holes(ring, holes, D_out, D_out, Tz)
    ring.apply_translation((0, 0, Tz * 0.5))
    return ring


def mdl_desk_hook(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L = float(p["length_mm"]); W = float(p["width_mm"]); H = float(p["height_mm"])
    T = max(3.0, float(p.get("thickness_mm") or 4.0))
    base = box(extents=(L, W, T)); base.apply_translation((0, 0, T * 0.5))
    arm_len = max(W * 0.6, 20.0)
    arm = box(extents=(T * 1.2, arm_len, T)); arm.apply_translation((0, (W * 0.5 - arm_len * 0.5), T * 0.5))
    tip_r = max(T * 0.6, 3.0)
    tip = cylinder(radius=tip_r, height=T * 1.2, sections=64)
    tip.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
    tip.apply_translation((0, (W * 0.5 + tip_r * 0.8), T * 0.5))
    mesh = _boolean_union([base, arm, tip])
    return _apply_top_holes(mesh, holes, L, W, max(H, T))


# Registro de modelos
REGISTRY: Dict[str, Callable[[dict, List[Any]], trimesh.Trimesh]] = {
    "cable_tray": mdl_cable_tray,
    "vesa_adapter": mdl_vesa_adapter,
    "router_mount": mdl_router_mount,
    "camera_mount": mdl_camera_mount,
    "wall_bracket": mdl_wall_bracket,
    "fan_guard": mdl_fan_guard,
    "desk_hook": mdl_desk_hook,
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
    model: str
    params: Params
    holes: Optional[List[Hole]] = []
    outputs: Optional[List[str]] = None             # ["stl","svg"]
    operations: Optional[List[Dict[str, Any]]] = None  # 🔸 UNIVERSALES

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
    return {"ok": True, "models": list(REGISTRY.keys())}

# ------------------------------------------------------------
#      OPERACIONES UNIVERSALES (cutout, text, round, array)
# ------------------------------------------------------------

def _mk_cutout(shape: str, x: float, y: float, L: float, W: float,
               depth: float, d: Optional[float] = None,
               w: Optional[float] = None, h: Optional[float] = None) -> trimesh.Trimesh:
    """
    Crea un "cutter" localizado en (x,y) en el plano de la cara superior.
    - shape: "circle" usa d (diámetro)
             "rect"   usa w,h
    depth: profundidad (en Z) hacia abajo.
    """
    cx = x - L * 0.5
    cy = y - W * 0.5
    depth = max(depth, 0.1)
    if (shape or "").lower() == "circle":
        r = max(0.05, (float(d or 0.0) * 0.5))
        cutter = cylinder(radius=r, height=depth, sections=64)
        cutter.apply_translation((cx, cy, depth * 0.5))
        return cutter
    else:
        ww = max(0.1, float(w or 0.0))
        hh = max(0.1, float(h or 0.0))
        cutter = box(extents=(ww, hh, depth))
        cutter.apply_translation((cx, cy, depth * 0.5))
        return cutter


def _apply_operations(mesh: trimesh.Trimesh, ops: List[Dict[str, Any]],
                      L: float, W: float, H: float) -> trimesh.Trimesh:
    if not ops:
        return mesh

    current = mesh
    cutters: List[trimesh.Trimesh] = []
    unions: List[trimesh.Trimesh] = []
    extra_fillet: float = 0.0

    for op in ops:
        t = (op.get("type") or "").lower()

        # round = fillet extra (aprox)
        if t == "round":
            extra_fillet = max(extra_fillet, float(op.get("r_mm") or op.get("r") or 0.0))
            continue

        # cutout simple
        if t == "cutout":
            shape = (op.get("shape") or "circle").lower()
            depth = float(op.get("depth_mm") or H)
            c = _mk_cutout(
                shape=shape,
                x=float(op.get("x_mm") or 0.0),
                y=float(op.get("y_mm") or 0.0),
                L=L, W=W, depth=depth,
                d=op.get("d_mm"),
                w=op.get("w_mm"), h=op.get("h_mm"),
            )
            cutters.append(c)
            continue

        # array de cutouts (circle/rect)
        if t == "array":
            shape = (op.get("shape") or "circle").lower()
            nx = max(1, int(op.get("nx") or 1))
            ny = max(1, int(op.get("ny") or 1))
            dx = float(op.get("dx_mm") or 10.0)
            dy = float(op.get("dy_mm") or 10.0)
            start_x = float(op.get("start_x_mm") or 0.0)
            start_y = float(op.get("start_y_mm") or 0.0)
            depth = float(op.get("depth_mm") or H)
            for ix in range(nx):
                for iy in range(ny):
                    x = start_x + ix * dx
                    y = start_y + iy * dy
                    c = _mk_cutout(shape=shape, x=x, y=y, L=L, W=W, depth=depth,
                                   d=op.get("d_mm"), w=op.get("w_mm"), h=op.get("h_mm"))
                    cutters.append(c)
            continue

        # text: grabado (engrave=True => difference) o relieve (union)
        if t == "text":
            txt = str(op.get("text") or "").strip()
            if not txt:
                continue
            size = max(1.0, float(op.get("size_mm") or 10.0))
            depth = max(0.2, float(op.get("depth_mm") or 1.0))
            x = float(op.get("x_mm") or 0.0)
            y = float(op.get("y_mm") or 0.0)
            engrave = bool(op.get("engrave", True))

            try:
                # genera contornos del texto como paths y extruye a sólido
                from trimesh.path.creation import text as path_text
                path = path_text(txt, font_size=size)
                # a polígonos (shapely), luego extruir
                polys = path.polygons_full
                solids = []
                if polys:
                    for poly in polys:
                        solid = trimesh.creation.extrude_polygon(poly, height=depth)
                        # desplazar: en top-face, centrado en (x,y)
                        # path genera texto alrededor de (0,0); lo colocamos con su bbox
                        bb = solid.bounds
                        sx = x - L * 0.5 - (bb[0][0])
                        sy = y - W * 0.5 - (bb[0][1])
                        sz = depth * 0.5
                        solid.apply_translation((sx, sy, sz))
                        solids.append(solid)
                    txt_mesh = _boolean_union(solids)
                    if engrave:
                        cutters.append(txt_mesh)
                    else:
                        unions.append(txt_mesh)
            except Exception as e:
                print("[WARN] Texto no soportado (trimesh.path/shapely indisponible):", e)
            continue

    # aplica uniones primero (emboss)
    if unions:
        current = _boolean_union([current] + unions)

    # aplica diferencias en bloque si es posible
    if cutters:
        diff = _boolean_diff(current, cutters)
        if diff is not None:
            current = diff
        else:
            print("[WARN] difference batch falló; intentando por partes…")
            for c in cutters:
                tmp = _boolean_diff(current, c)
                if tmp is not None:
                    current = tmp

    # fillet adicional solicitado por "round"
    if extra_fillet > 0.0:
        current = _apply_rounding_if_possible(current, extra_fillet)

    return current

# ------------------------- Generate STL + PNG (+ SVG opcional) -------------------------

@app.post("/generate", response_model=GenerateRes)
def generate(req: GenerateReq):
    p = {
        "length_mm": req.params.length_mm,
        "width_mm": req.params.width_mm,
        "height_mm": req.params.height_mm,
        "thickness_mm": req.params.thickness_mm or 3.0,
        "fillet_mm": req.params.fillet_mm or 0.0,
    }

    candidates = {
        req.model,
        req.model.replace("-", "_"),
        req.model.replace("_", "-"),
        req.model.lower(),
        req.model.lower().replace("-", "_"),
        req.model.lower().replace("_", "-"),
    }

    builder: Optional[Callable[[dict, List[Any]], trimesh.Trimesh]] = None
    chosen = None
    for k in candidates:
        if k in REGISTRY:
            builder = REGISTRY[k]; chosen = k; break
    if builder is None:
        raise RuntimeError(f"Modelo desconocido: {req.model}. Disponibles: {', '.join(REGISTRY.keys())}")

    # malla base
    mesh = builder(p, req.holes or [])

    # fillet "global" (param)
    f = float(p.get("fillet_mm") or 0.0)
    if f > 0:
        mesh = _apply_rounding_if_possible(mesh, f)

    # 🔸 operaciones universales
    try:
        mesh = _apply_operations(mesh, req.operations or [], p["length_mm"], p["width_mm"], p["height_mm"])
    except Exception as e:
        print("[WARN] Falló _apply_operations:", e)

    # STL
    stl_bytes = _export_stl(mesh)
    stl_buf = io.BytesIO(stl_bytes); stl_buf.seek(0)

    base_key = (chosen or req.model).replace("_", "-")
    object_key = f"{base_key}/forge-output.stl"
    stl_url = upload_and_get_url(stl_buf, object_key, bucket=BUCKET, public=PUBLIC_READ)

    # PNG
    thumb_url = None
    try:
        png_bytes = _render_thumbnail_png(mesh, width=900, height=600, background=(245, 246, 248, 255))
        if png_bytes:
            png_buf = io.BytesIO(png_bytes); png_buf.seek(0)
            png_key = f"{base_key}/thumbnail.png"
            thumb_url = upload_and_get_url(png_buf, png_key, bucket=BUCKET, public=PUBLIC_READ)
    except Exception as e:
        print("[WARN] No se pudo generar miniatura:", e)

    # SVG opcional (solo si se solicita y hay generador específico)
    svg_url = None
    try:
        want_svg = bool(req.outputs and any(o.lower() == "svg" for o in req.outputs))
        if want_svg and (chosen or req.model).replace("-", "_") == "cable_tray":
            from models.cable_tray import make_svg as cable_tray_make_svg
            svg_text = cable_tray_make_svg(p, req.holes or [])
            if svg_text:
                svg_buf = io.BytesIO(svg_text.encode("utf-8")); svg_buf.seek(0)
                svg_key = f"{base_key}/outline.svg"
                svg_url = upload_and_get_url(svg_buf, svg_key, bucket=BUCKET, public=PUBLIC_READ)
    except Exception as e:
        print("[WARN] SVG opcional falló:", e)

    return GenerateRes(stl_url=stl_url, object_key=object_key, thumb_url=thumb_url, svg_url=svg_url)


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
    gen = generate(GenerateReq(model=req.model, params=req.params, holes=req.holes))
    if not gen.thumb_url:
        raise RuntimeError("No se pudo generar la miniatura.")
    png_key = gen.object_key.replace("forge-output.stl", "thumbnail.png")
    return ThumbnailRes(thumb_url=gen.thumb_url, object_key=png_key)
