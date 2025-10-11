# apps/stl-service/app.py
import io
import os
import math
from typing import List, Optional, Callable, Dict, Any, Iterable

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
            print("[WARN] No se pudo aplicar un agujero (CSG no disponible). Continuo…")
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
        math.radians(25), math.radians(-30), 0.0
    )
    cam_tf = trimesh.scene.cameras.look_at(points=[center], distance=distance, rotation=rot_euler)
    scene.camera_transform = cam_tf
    return scene

def _render_thumbnail_png(
    mesh: trimesh.Trimesh, width: int = 900, height: int = 600,
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
#        MODELOS – define aquí cada geometría
# ============================================================

def mdl_cable_tray(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(1.0, float(p.get("thickness_mm") or 3.0))
    outer = box(extents=(L, W, H)); outer.apply_translation((0, 0, H * 0.5))
    inner = box(extents=(L - 2 * T, W - 2 * T, H + 2.0)); inner.apply_translation((0, 0, H))
    hollow = _boolean_diff(outer, inner) or outer
    hollow = _apply_top_holes(hollow, holes, L, W, H)
    return hollow

def mdl_vesa_adapter(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(2.0, float(p.get("thickness_mm") or 4.0))
    plate = box(extents=(L, W, T)); plate.apply_translation((0, 0, T * 0.5))
    plate = _apply_top_holes(plate, holes, L, W, T)
    return plate

def mdl_router_mount(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(2.0, float(p.get("thickness_mm") or 3.0))
    base = box(extents=(L, W, T)); base.apply_translation((0, 0, T * 0.5))
    vertical = box(extents=(L, T, H)); vertical.apply_translation((0, (W * 0.5 - T * 0.5), H * 0.5))
    mesh = _boolean_union([base, vertical])
    mesh = _apply_top_holes(mesh, holes, L, W, max(H, T))
    return mesh

def mdl_camera_mount(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(2.0, float(p.get("thickness_mm") or 3.0))
    base = box(extents=(L, W, T)); base.apply_translation((0, 0, T * 0.5))
    col_h = min(max(H - T, 10.0), H)
    col = box(extents=(T * 2.0, T * 2.0, col_h)); col.apply_translation((0, 0, T + col_h * 0.5))
    mesh = _boolean_union([base, col])
    mesh = _apply_top_holes(mesh, holes, L, W, T + col_h)
    return mesh

def mdl_wall_bracket(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(3.0, float(p.get("thickness_mm") or 4.0))
    horiz = box(extents=(L, W, T)); horiz.apply_translation((0, 0, T * 0.5))
    vert = box(extents=(T, W, H)); vert.apply_translation((L * 0.5 - T * 0.5, 0, H * 0.5))
    mesh = _boolean_union([horiz, vert])
    mesh = _apply_top_holes(mesh, holes, L, W, max(H, T))
    return mesh

# --- extra modelos (ligeros) abreviados (como ya tenías) ---
def mdl_headset_stand(p, holes):  # ...
    base = box(extents=(p["length_mm"], p["thickness_mm"], p["width_mm"]))
    base.apply_translation((0, p["thickness_mm"]/2.0, 0))
    mast = box(extents=(p["thickness_mm"]*3.0, p["height_mm"], p["thickness_mm"]))
    mast.apply_translation((0, p["thickness_mm"] + p["height_mm"]/2.0, -p["width_mm"]/2.0 + p["thickness_mm"]*2.0))
    y = p["length_mm"]*0.6; r = p["length_mm"]*0.25; t = p["thickness_mm"]
    bridge = box(extents=(2*r + t, t, y))
    bridge.apply_translation((0, p["thickness_mm"] + p["height_mm"], -p["width_mm"]/2.0 + t*2.0))
    return _boolean_union([base, mast, bridge])

def mdl_laptop_stand(p, holes):
    import shapely.geometry as sg
    poly = sg.Polygon([(0,0), (0,p["height_mm"]), (p["width_mm"], p["height_mm"]*0.6)])
    rib = trimesh.creation.extrude_polygon(poly, p["thickness_mm"])
    rib.apply_translation((-p["length_mm"]/2.0, 0, -p["width_mm"]/2.0))
    rib2 = rib.copy(); rib2.apply_translation((p["length_mm"] - p["thickness_mm"], 0, 0))
    top = box(extents=(p["length_mm"], p["thickness_mm"], p["thickness_mm"]*2.0))
    top.apply_translation((0, p["height_mm"], -p["width_mm"]/2.0 + p["width_mm"]*0.6))
    lip = box(extents=(p["length_mm"], p["thickness_mm"], p["thickness_mm"]*1.5))
    lip.apply_translation((0, p["thickness_mm"]*1.5, -p["width_mm"]/2.0 + p["thickness_mm"]*2.0))
    base = box(extents=(p["length_mm"], p["thickness_mm"], p["thickness_mm"]*2.5))
    base.apply_translation((0, p["thickness_mm"]/2.0, p["width_mm"]/2.0 - p["thickness_mm"]*1.25))
    return _boolean_union([rib, rib2, top, lip, base])

def mdl_wall_hook(p, holes):
    plate = box(extents=(p["width_mm"], p["thickness_mm"], p["length_mm"]))
    plate.apply_translation((0, p["thickness_mm"]/2.0, 0))
    arm = box(extents=(p["thickness_mm"], p["thickness_mm"], p["height_mm"]*0.75))
    arm.apply_translation((0, p["thickness_mm"]/2.0 + p["thickness_mm"], p["height_mm"]*0.75/2.0))
    tip = cylinder(radius=p["thickness_mm"]/2.0, height=p["thickness_mm"], sections=64)
    tip.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [1,0,0]))
    tip.apply_translation((0, p["thickness_mm"], p["height_mm"]*0.75))
    gusset = box(extents=(p["width_mm"]*0.6, p["thickness_mm"], p["height_mm"]*0.4))
    gusset.apply_translation((0, p["thickness_mm"]/2.0, p["height_mm"]*0.2))
    return _boolean_union([plate, arm, tip, gusset])

def mdl_tablet_stand(p, holes):
    import shapely.geometry as sg
    poly = sg.Polygon([(0,0), (0,p["height_mm"]), (p["width_mm"]*0.7, p["height_mm"]*0.85)])
    rib = trimesh.creation.extrude_polygon(poly, p["thickness_mm"])
    rib.apply_translation((-p["length_mm"]/2.0, 0, -p["width_mm"]/2.0))
    rib2 = rib.copy(); rib2.apply_translation((p["length_mm"] - p["thickness_mm"], 0, 0))
    tray = box(extents=(p["length_mm"], p["thickness_mm"]*2.0, p["width_mm"]*0.5))
    tray.apply_translation((0, p["height_mm"]*0.85, -p["width_mm"]/2.0 + p["width_mm"]*0.35))
    lip = box(extents=(p["length_mm"], p["thickness_mm"], p["thickness_mm"]*2.0))
    lip.apply_translation((0, p["height_mm"]*0.85 + p["thickness_mm"], -p["width_mm"]/2.0 + p["width_mm"]*0.1))
    return _boolean_union([rib, rib2, tray, lip])

def mdl_ssd_holder(p, holes):
    innerL, innerW = 100.0, 70.0
    t = p["thickness_mm"]
    base = box(extents=(innerL + 2*t, t, innerW + 2*t)); base.apply_translation((0, t/2, 0))
    wallL = box(extents=(t, t*8, innerW + 2*t))
    w1 = wallL.copy(); w1.apply_translation((-(innerL+2*t)/2 + t/2, t*4.5, 0))
    w2 = wallL.copy(); w2.apply_translation(((innerL+2*t)/2 - t/2, t*4.5, 0))
    wallW = box(extents=(innerL, t*8, t))
    w3 = wallW.copy(); w3.apply_translation((0, t*4.5, -(innerW+2*t)/2 + t/2))
    mesh = _boolean_union([base, w1, w2, w3])
    return mesh

def mdl_raspi_case(p, holes):
    L, W, H, t = p["length_mm"], p["width_mm"], p["height_mm"], p["thickness_mm"]
    base = box(extents=(L, t, W)); base.apply_translation((0, t/2, 0))
    wall = box(extents=(L, H, t)); w1 = wall.copy(); w1.apply_translation((0, H/2 + t, -(W/2 - t/2)))
    w2 = wall.copy(); w2.apply_translation((0, H/2 + t, (W/2 - t/2)))
    wall2 = box(extents=(t, H, W)); w3 = wall2.copy(); w3.apply_translation((-(L/2 - t/2), H/2 + t, 0))
    w4 = wall2.copy(); w4.apply_translation(((L/2 - t/2), H/2 + t, 0))
    post = cylinder(radius=t*0.6, height=H, sections=32)
    p1 = post.copy(); p1.apply_translation((-L*0.35, H/2 + t, -W*0.35))
    p2 = post.copy(); p2.apply_translation(( L*0.35, H/2 + t, -W*0.35))
    p3 = post.copy(); p3.apply_translation((-L*0.35, H/2 + t,  W*0.35))
    p4 = post.copy(); p4.apply_translation(( L*0.35, H/2 + t,  W*0.35))
    return _boolean_union([base, w1, w2, w3, w4, p1, p2, p3, p4])

def mdl_go_pro_mount(p, holes):
    base = box(extents=(p["length_mm"], p["thickness_mm"]*2, p["width_mm"]*0.4))
    base.apply_translation((0, p["thickness_mm"], 0))
    prong = box(extents=(p["thickness_mm"], p["thickness_mm"]*2, p["width_mm"]*0.4))
    a = prong.copy(); a.apply_translation((-p["thickness_mm"], p["thickness_mm"], 0))
    b = prong.copy(); b.apply_translation((0, p["thickness_mm"], 0))
    c = prong.copy(); c.apply_translation((p["thickness_mm"], p["thickness_mm"], 0))
    return _boolean_union([base, a, b, c])

def mdl_monitor_stand(p, holes):
    top = box(extents=(p["length_mm"], p["thickness_mm"]*2, p["width_mm"]))
    top.apply_translation((0, p["height_mm"] + p["thickness_mm"], 0))
    leg = box(extents=(p["thickness_mm"]*3, p["height_mm"], p["width_mm"]*0.8))
    l1 = leg.copy(); l1.apply_translation((-p["length_mm"]/2 + p["thickness_mm"]*1.5, p["height_mm"]/2, 0))
    l2 = leg.copy(); l2.apply_translation(( p["length_mm"]/2 - p["thickness_mm"]*1.5, p["height_mm"]/2, 0))
    return _boolean_union([top, l1, l2])

def mdl_camera_plate(p, holes):
    plate = box(extents=(p["length_mm"], p["thickness_mm"], p["width_mm"]))
    plate.apply_translation((0, p["thickness_mm"]/2, 0))
    slot = box(extents=(p["length_mm"]*0.6, p["thickness_mm"]*1.2, p["thickness_mm"]*1.5))
    slot.apply_translation((0, p["thickness_mm"]/2, 0))
    out = _boolean_diff(plate, [slot])
    return out or plate

def mdl_hub_holder(p, holes):
    base = box(extents=(p["length_mm"], p["thickness_mm"], p["width_mm"]))
    base.apply_translation((0, p["thickness_mm"]/2, 0))
    wall = box(extents=(p["thickness_mm"]*2, p["height_mm"], p["width_mm"]))
    w1 = wall.copy(); w1.apply_translation((-p["length_mm"]/2 + p["thickness_mm"], p["height_mm"]/2 + p["thickness_mm"], 0))
    w2 = wall.copy(); w2.apply_translation(( p["length_mm"]/2 - p["thickness_mm"], p["height_mm"]/2 + p["thickness_mm"], 0))
    return _boolean_union([base, w1, w2])

def mdl_mic_arm_clip(p, holes):
    outer = cylinder(radius=p["width_mm"]/2, height=p["thickness_mm"]*2, sections=96)
    inner = cylinder(radius=p["width_mm"]/2 - p["thickness_mm"], height=p["thickness_mm"]*2.2, sections=96)
    gap = box(extents=(p["width_mm"], p["height_mm"], p["thickness_mm"]*4))
    gap.apply_translation((0, p["height_mm"]/2, 0))
    ring = _boolean_diff(outer, [inner, gap]) or outer
    return ring

def mdl_phone_dock(p, holes):
    top = box(extents=(p["length_mm"], p["thickness_mm"], p["width_mm"]*0.5))
    top.apply_translation((0, p["height_mm"], -p["width_mm"]*0.2))
    leg = box(extents=(p["thickness_mm"]*3, p["height_mm"], p["thickness_mm"]*2))
    leg.apply_translation((0, p["height_mm"]/2, -p["width_mm"]/2 + p["thickness_mm"]*2))
    base = box(extents=(p["length_mm"], p["thickness_mm"], p["width_mm"]*0.4))
    base.apply_translation((0, p["thickness_mm"]/2, p["width_mm"]*0.3))
    channel = box(extents=(p["thickness_mm"], p["thickness_mm"]*1.2, p["thickness_mm"]*2.0))
    channel.apply_translation((0, p["height_mm"]-p["thickness_mm"], -p["width_mm"]*0.2))
    out = _boolean_union([top, leg, base])
    out = _boolean_diff(out, [channel]) or out
    return out

REGISTRY: Dict[str, Callable[[dict, List[Any]], trimesh.Trimesh]] = {
    "cable_tray": mdl_cable_tray,
    "vesa_adapter": mdl_vesa_adapter,
    "router_mount": mdl_router_mount,
    "camera_mount": mdl_camera_mount,
    "wall_bracket": mdl_wall_bracket,
    "headset_stand": mdl_headset_stand,
    "laptop_stand": mdl_laptop_stand,
    "wall_hook": mdl_wall_hook,
    "tablet_stand": mdl_tablet_stand,
    "ssd_holder": mdl_ssd_holder,
    "raspi_case": mdl_raspi_case,
    "go_pro_mount": mdl_go_pro_mount,
    "monitor_stand": mdl_monitor_stand,
    "camera_plate": mdl_camera_plate,
    "hub_holder": mdl_hub_holder,
    "mic_arm_clip": mdl_mic_arm_clip,
    "phone_dock": mdl_phone_dock,
}

# ============================================================
#               FastAPI + modelos de request/response
# ============================================================

CORS_ALLOW_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()] or ["*"]
BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")
PUBLIC_READ = os.getenv("SUPABASE_PUBLIC_READ", "0") == "1"

# ----- OPERATIONS API -----

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

class Operation(BaseModel):
    type: str
    # campos opcionales (cutout/text/round/array)
    shape: Optional[str] = None
    x_mm: Optional[float] = None
    y_mm: Optional[float] = None
    w_mm: Optional[float] = None
    h_mm: Optional[float] = None
    d_mm: Optional[float] = None
    depth_mm: Optional[float] = None
    r_mm: Optional[float] = None
    text: Optional[str] = None
    size_mm: Optional[float] = None
    engrave: Optional[bool] = True
    # array
    start_x_mm: Optional[float] = None
    start_y_mm: Optional[float] = None
    nx: Optional[int] = None
    ny: Optional[int] = None
    dx_mm: Optional[float] = None
    dy_mm: Optional[float] = None

class GenerateReq(BaseModel):
    model: str
    params: Params
    holes: Optional[List[Hole]] = []
    outputs: Optional[List[str]] = None
    operations: Optional[List[Operation]] = None   # <--- NUEVO

class GenerateRes(BaseModel):
    stl_url: str
    object_key: str
    thumb_url: Optional[str] = None
    svg_url: Optional[str] = None

# ---------- helpers para operaciones ----------

def _mk_cutter(shape: str, x: float, y: float, depth: float, **k) -> trimesh.Trimesh:
    shape = (shape or "").lower()
    if shape in ("circle", "circ", "c"):
        d = float(k.get("d", k.get("d_mm", 0)) or 0)
        r = max(0.05, d * 0.5)
        cutter = cylinder(radius=r, height=depth, sections=64)
    else:
        w = max(0.05, float(k.get("w", k.get("w_mm", 0)) or 0))
        h = max(0.05, float(k.get("h", k.get("h_mm", 0)) or 0))
        cutter = box(extents=(w, h, depth))
    cutter.apply_translation((x, y, depth * 0.5))
    return cutter

def _apply_operations(mesh: trimesh.Trimesh, ops: List[Operation], dims: Dict[str, float]) -> trimesh.Trimesh:
    if not ops:
        return mesh
    L, W, H = dims["L"], dims["W"], dims["H"]
    T = dims["T"]

    current = mesh
    cutters: List[trimesh.Trimesh] = []
    unions: List[trimesh.Trimesh] = []
    round_r: float = 0.0

    for op in ops:
        t = (op.type or "").lower()

        # ------ round/chamfer ------
        if t in ("round", "fillet", "chamfer"):
            r = float(op.r_mm or 0.0)
            round_r = max(round_r, r)
            continue

        # ------ cutout unitario ------
        if t == "cutout":
            x = float(op.x_mm or 0.0) - L * 0.5
            y = float(op.y_mm or 0.0) - W * 0.5
            depth = float(op.depth_mm or (H * 1.2))
            cutters.append(_mk_cutter(op.shape or "circle", x, y, depth, d_mm=op.d_mm, w_mm=op.w_mm, h_mm=op.h_mm))
            continue

        # ------ array de cutouts ------
        if t == "array":
            sx = float(op.start_x_mm or 0.0)
            sy = float(op.start_y_mm or 0.0)
            nx = int(op.nx or 0); ny = int(op.ny or 0)
            dx = float(op.dx_mm or 0.0); dy = float(op.dy_mm or 0.0)
            depth = float(op.depth_mm or (H * 1.2))
            for ix in range(max(0, nx)):
                for iy in range(max(0, ny)):
                    x = (sx + ix * dx) - L * 0.5
                    y = (sy + iy * dy) - W * 0.5
                    cutters.append(_mk_cutter(op.shape or "rect", x, y, depth, d_mm=op.d_mm, w_mm=op.w_mm, h_mm=op.h_mm))
            continue

        # ------ texto grabado/relieve (best-effort) ------
        if t == "text":
            try:
                content = (op.text or "").strip()
                if not content:
                    continue
                size = float(op.size_mm or 10.0)
                depth = float(op.depth_mm or 1.0)
                x = float(op.x_mm or 0.0) - L * 0.5
                y = float(op.y_mm or 0.0) - W * 0.5
                # Path 2D → extrusión
                try:
                    from trimesh.path.creation import text as path_text
                    p: trimesh.path.Path2D = path_text(content, font=None, scale=size)
                    area = p.area
                    if area <= 0:
                        raise RuntimeError("Texto vacío/degenerado")
                    ext = p.extrude(height=depth)
                    # colocar en XY; profundidad comienza en z=0
                    ext.apply_translation((x, y, 0.0))
                    if bool(op.engrave):
                        cutters.append(ext)
                    else:
                        unions.append(ext)
                except Exception as e:
                    # fallback shapely
                    try:
                        import shapely
                        from shapely.geometry import Polygon
                        print("[INFO] Texto: fallback simple (rect) por falta de freetype)", e)
                        rect = box(extents=(size * len(content) * 0.6, size, depth))
                        rect.apply_translation((x, y, depth * 0.5))
                        if bool(op.engrave):
                            cutters.append(rect)
                        else:
                            unions.append(rect)
                    except Exception:
                        print("[WARN] Operación 'text' ignorada (sin deps).")
                continue
            except Exception as e:
                print("[WARN] Texto falló:", e)
                continue

        # otros tipos desconocidos -> ignorar sin romper
        print(f"[INFO] Operación desconocida '{t}' ignorada.")

    # aplicar unions/cutters
    if unions:
        current = _boolean_union([current] + unions)
    if cutters:
        diff = _boolean_diff(current, cutters)
        if diff is not None:
            current = diff
        else:
            print("[WARN] No se pudo aplicar algunos cutouts (CSG no disponible).")

    # fillet global al final (si procede)
    if round_r > 0:
        current = _apply_rounding_if_possible(current, round_r)

    return current

# ---------------------- FastAPI ----------------------

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

    # 1) base
    mesh = builder(p, req.holes or [])

    # 2) fillet "clásico" del panel (se mantiene para retrocompatibilidad)
    base_f = float(p.get("fillet_mm") or 0.0)
    if base_f > 0:
        mesh = _apply_rounding_if_possible(mesh, base_f)

    # 3) APLICAR OPERACIONES universales (si vienen)
    if req.operations:
        dims = {"L": p["length_mm"], "W": p["width_mm"], "H": p["height_mm"], "T": p["thickness_mm"]}
        mesh = _apply_operations(mesh, req.operations, dims)

    # 4) export STL
    stl_bytes = _export_stl(mesh)
    stl_buf = io.BytesIO(stl_bytes); stl_buf.seek(0)
    base_key = (chosen or req.model).replace("_", "-")
    object_key = f"{base_key}/forge-output.stl"
    stl_url = upload_and_get_url(stl_buf, object_key, bucket=BUCKET, public=PUBLIC_READ)

    # 5) thumbnail
    thumb_url = None
    try:
        png_bytes = _render_thumbnail_png(mesh, width=900, height=600, background=(245, 246, 248, 255))
        if png_bytes:
            png_buf = io.BytesIO(png_bytes); png_buf.seek(0)
            png_key = f"{base_key}/thumbnail.png"
            thumb_url = upload_and_get_url(png_buf, png_key, bucket=BUCKET, public=PUBLIC_READ)
    except Exception as e:
        print("[WARN] No se pudo generar miniatura:", e)

    # 6) SVG opcional (por ahora solo cable_tray explícito)
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
