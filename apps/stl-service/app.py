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
        smooth = man.Erode(r).Dilate(r)  # cierre morfológico ≈ round
        out = smooth.to_trimesh()
        if isinstance(out, trimesh.Trimesh):
            return out
    except Exception:
        print("[INFO] Fillet ignorado (manifold3d no disponible o falló).")
    return mesh

def _apply_chamfer_if_possible(mesh: trimesh.Trimesh, r_mm: float) -> trimesh.Trimesh:
    r = float(r_mm or 0.0)
    if r <= 0.0:
        return mesh
    try:
        import manifold3d as m3d
        man = m3d.Manifold(mesh)
        cham = man.Erode(r)  # erosión ≈ chaflán
        out = cham.to_trimesh()
        if isinstance(out, trimesh.Trimesh):
            return out
    except Exception:
        print("[INFO] Chamfer ignorado (manifold3d no disponible o falló).")
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
    # laterales
    left = box(extents=(L, T, H)); left.apply_translation((0, -(W/2 - T/2), H/2))
    right = box(extents=(L, T, H)); right.apply_translation((0,  (W/2 - T/2), H/2))
    # base
    base = box(extents=(L, W - 2*T, T)); base.apply_translation((0, 0, T/2))
    tray = _boolean_union([left, right, base])
    tray = _apply_top_holes(tray, holes, L, W, H)
    return tray

def mdl_vesa_adapter(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
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

# ---- Ligeros
def mdl_headset_stand(p: dict, holes) -> trimesh.Trimesh:
    base = box(extents=(p["length_mm"], p["thickness_mm"], p["width_mm"]))
    base.apply_translation((0, p["thickness_mm"]/2.0, 0))
    mast = box(extents=(p["thickness_mm"]*3.0, p["height_mm"], p["thickness_mm"]))
    mast.apply_translation((0, p["thickness_mm"] + p["height_mm"]/2.0, -p["width_mm"]/2.0 + p["thickness_mm"]*2.0))
    y = p["length_mm"]*0.6; r = p["length_mm"]*0.25; t = p["thickness_mm"]
    bridge = box(extents=(2*r + t, t, y))
    bridge.apply_translation((0, p["thickness_mm"] + p["height_mm"], -p["width_mm"]/2.0 + t*2.0))
    return _boolean_union([base, mast, bridge])

def mdl_laptop_stand(p: dict, holes) -> trimesh.Trimesh:
    top = box(extents=(p["length_mm"], p["thickness_mm"], p["thickness_mm"]*2.0))
    top.apply_translation((0, p["height_mm"], -p["width_mm"]/2.0 + p["width_mm"]*0.6))
    lip = box(extents=(p["length_mm"], p["thickness_mm"], p["thickness_mm"]*1.5))
    lip.apply_translation((0, p["thickness_mm"]*1.5, -p["width_mm"]/2.0 + p["thickness_mm"]*2.0))
    base = box(extents=(p["length_mm"], p["thickness_mm"], p["thickness_mm"]*2.5))
    base.apply_translation((0, p["thickness_mm"]/2.0, p["width_mm"]/2.0 - p["thickness_mm"]*1.25))
    rib = box(extents=(p["thickness_mm"], p["height_mm"], p["width_mm"]*0.6))
    a = rib.copy(); a.apply_translation((-p["length_mm"]/2.0 + p["thickness_mm"]/2.0, p["height_mm"]/2.0, 0))
    b = rib.copy(); b.apply_translation(( p["length_mm"]/2.0 - p["thickness_mm"]/2.0, p["height_mm"]/2.0, 0))
    return _boolean_union([top, lip, base, a, b])

def mdl_wall_hook(p: dict, holes) -> trimesh.Trimesh:
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

def mdl_tablet_stand(p: dict, holes) -> trimesh.Trimesh:
    tray = box(extents=(p["length_mm"], p["thickness_mm"]*2.0, p["width_mm"]*0.5))
    tray.apply_translation((0, p["height_mm"]*0.85, -p["width_mm"]/2.0 + p["width_mm"]*0.35))
    lip = box(extents=(p["length_mm"], p["thickness_mm"], p["thickness_mm"]*2.0))
    lip.apply_translation((0, p["height_mm"]*0.85 + p["thickness_mm"], -p["width_mm"]/2.0 + p["width_mm"]*0.1))
    rib = box(extents=(p["thickness_mm"], p["height_mm"], p["width_mm"]*0.7))
    a = rib.copy(); a.apply_translation((-p["length_mm"]/2.0 + p["thickness_mm"]/2.0, p["height_mm"]/2.0, 0))
    b = rib.copy(); b.apply_translation(( p["length_mm"]/2.0 - p["thickness_mm"]/2.0, p["height_mm"]/2.0, 0))
    return _boolean_union([tray, lip, a, b])

def mdl_ssd_holder(p: dict, holes) -> trimesh.Trimesh:
    innerL, innerW = 100.0, 70.0
    t = p["thickness_mm"]
    base = box(extents=(innerL + 2*t, t, innerW + 2*t)); base.apply_translation((0, t/2, 0))
    wallL = box(extents=(t, t*8, innerW + 2*t))
    w1 = wallL.copy(); w1.apply_translation((-(innerL+2*t)/2 + t/2, t*4.5, 0))
    w2 = wallL.copy(); w2.apply_translation(((innerL+2*t)/2 - t/2, t*4.5, 0))
    wallW = box(extents=(innerL, t*8, t))
    w3 = wallW.copy(); w3.apply_translation((0, t*4.5, -(innerW+2*t)/2 + t/2))
    return _boolean_union([base, w1, w2, w3])

def mdl_raspi_case(p: dict, holes) -> trimesh.Trimesh:
    L, W, H, t = p["length_mm"], p["width_mm"], p["height_mm"], p["thickness_mm"]
    base = box(extents=(L, t, W)); base.apply_translation((0, t/2, 0))
    wall = box(extents=(L, H, t)); w1 = wall.copy(); w1.apply_translation((0, H/2 + t, -(W/2 - t/2)))
    w2 = wall.copy(); w2.apply_translation((0, H/2 + t,  (W/2 - t/2)))
    wall2 = box(extents=(t, H, W)); w3 = wall2.copy(); w3.apply_translation((-(L/2 - t/2), H/2 + t, 0))
    w4 = wall2.copy(); w4.apply_translation(((L/2 - t/2),  H/2 + t, 0))
    post = cylinder(radius=t*0.6, height=H, sections=32)
    p1 = post.copy(); p1.apply_translation((-L*0.35, H/2 + t, -W*0.35))
    p2 = post.copy(); p2.apply_translation(( L*0.35, H/2 + t, -W*0.35))
    p3 = post.copy(); p3.apply_translation((-L*0.35, H/2 + t,  W*0.35))
    p4 = post.copy(); p4.apply_translation(( L*0.35, H/2 + t,  W*0.35))
    return _boolean_union([base, w1, w2, w3, w4, p1, p2, p3, p4])

def mdl_go_pro_mount(p: dict, holes) -> trimesh.Trimesh:
    base = box(extents=(p["length_mm"], p["thickness_mm"]*2, p["width_mm"]*0.4))
    base.apply_translation((0, p["thickness_mm"], 0))
    pr = box(extents=(p["thickness_mm"], p["thickness_mm"]*2, p["width_mm"]*0.4))
    a = pr.copy(); a.apply_translation((-p["thickness_mm"], p["thickness_mm"], 0))
    b = pr.copy(); b.apply_translation((0, p["thickness_mm"], 0))
    c = pr.copy(); c.apply_translation((p["thickness_mm"], p["thickness_mm"], 0))
    return _boolean_union([base, a, b, c])

def mdl_monitor_stand(p: dict, holes) -> trimesh.Trimesh:
    top = box(extents=(p["length_mm"], p["thickness_mm"]*2, p["width_mm"]))
    top.apply_translation((0, p["height_mm"] + p["thickness_mm"], 0))
    leg = box(extents=(p["thickness_mm"]*3, p["height_mm"], p["width_mm"]*0.8))
    l1 = leg.copy(); l1.apply_translation((-p["length_mm"]/2 + p["thickness_mm"]*1.5, p["height_mm"]/2, 0))
    l2 = leg.copy(); l2.apply_translation(( p["length_mm"]/2 - p["thickness_mm"]*1.5, p["height_mm"]/2, 0))
    return _boolean_union([top, l1, l2])

def mdl_camera_plate(p: dict, holes) -> trimesh.Trimesh:
    plate = box(extents=(p["length_mm"], p["thickness_mm"], p["width_mm"]))
    plate.apply_translation((0, p["thickness_mm"]/2, 0))
    slot = box(extents=(p["length_mm"]*0.6, p["thickness_mm"]*1.2, p["thickness_mm"]*1.5))
    slot.apply_translation((0, p["thickness_mm"]/2, 0))
    out = _boolean_diff(plate, [slot])
    return out or plate

def mdl_hub_holder(p: dict, holes) -> trimesh.Trimesh:
    base = box(extents=(p["length_mm"], p["thickness_mm"], p["width_mm"]))
    base.apply_translation((0, p["thickness_mm"]/2, 0))
    wall = box(extents=(p["thickness_mm"]*2, p["height_mm"], p["width_mm"]))
    w1 = wall.copy(); w1.apply_translation((-p["length_mm"]/2 + p["thickness_mm"], p["height_mm"]/2 + p["thickness_mm"], 0))
    w2 = wall.copy(); w2.apply_translation(( p["length_mm"]/2 - p["thickness_mm"], p["height_mm"]/2 + p["thickness_mm"], 0))
    return _boolean_union([base, w1, w2])

def mdl_mic_arm_clip(p: dict, holes) -> trimesh.Trimesh:
    outer = cylinder(radius=p["width_mm"]/2, height=p["thickness_mm"]*2, sections=96)
    inner = cylinder(radius=p["width_mm"]/2 - p["thickness_mm"], height=p["thickness_mm"]*2.2, sections=96)
    gap = box(extents=(p["width_mm"], p["height_mm"], p["thickness_mm"]*4))
    gap.apply_translation((0, p["height_mm"]/2, 0))
    ring = _boolean_diff(outer, [inner, gap]) or outer
    return ring

def mdl_phone_dock(p: dict, holes) -> trimesh.Trimesh:
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

# ---- NUEVOS MODELOS FÁCILES ----

def mdl_stackable_bin(p: dict, holes) -> trimesh.Trimesh:
    """ Caja apilable sencilla con labio. """
    L, W, H = p["length_mm"], p["width_mm"], p["height_mm"]
    t = max(2.0, p.get("thickness_mm", 3.0))
    outer = box(extents=(L, W, H)); outer.apply_translation((0, 0, H/2))
    inner = box(extents=(L-2*t, W-2*t, H-2*t)); inner.apply_translation((0, 0, H/2 + t*0.2))
    shell = _boolean_diff(outer, inner) or outer
    lip = box(extents=(L*0.9, W*0.08, t)); lip.apply_translation((0, W/2 - t/2, H - t/2))
    return _boolean_union([shell, lip])

def mdl_desk_cable_grommet(p: dict, holes) -> trimesh.Trimesh:
    """ Pasacables circular para escritorio: aro + tapa simple. """
    D = p["width_mm"]; d = max(20.0, p["length_mm"])  # usamos length como hueco
    t = max(3.0, p.get("thickness_mm", 3.0))
    h = max(8.0, p["height_mm"])
    outer = cylinder(radius=D/2, height=h, sections=96)
    inner = cylinder(radius=(D/2 - t), height=h+2, sections=96)
    ring = _boolean_diff(outer, inner) or outer
    cap = cylinder(radius=(D/2 - t*1.2), height=t, sections=96); cap.apply_translation((0,0,h - t/2))
    return _boolean_union([ring, cap])

# Registro de modelos
REGISTRY: Dict[str, Callable[[dict, List[Any]], trimesh.Trimesh]] = {
    "cable_tray": mdl_cable_tray,
    "vesa_adapter": mdl_vesa_adapter,
    "router_mount": mdl_router_mount,
    "camera_mount": mdl_camera_mount,
    "wall_bracket": mdl_wall_bracket,
    "fan_guard": mdl_fan_guard,
    "desk_hook": mdl_desk_hook,

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

    # nuevos
    "stackable_bin": mdl_stackable_bin,
    "desk_cable_grommet": mdl_desk_cable_grommet,
}

# ============================================================
#       OPERACIONES UNIVERSALES (opcionales por modelo)
# ============================================================

def _op_cutout(mesh: trimesh.Trimesh, L: float, W: float, H: float, op: Dict[str, Any]) -> trimesh.Trimesh:
    """ Recorte desde la cara superior. shape: 'circle'|'rect' """
    shape = (op.get("shape") or "circle").lower()
    x = float(op.get("x_mm", L/2)) - L*0.5
    y = float(op.get("y_mm", W/2)) - W*0.5
    depth = float(op.get("depth_mm", H * 1.5))
    if shape == "rect":
        w = float(op.get("w_mm", 10.0))
        h = float(op.get("h_mm", 10.0))
        cutter = box(extents=(w, h, max(1.0, depth)))
    else:
        d = float(op.get("d_mm", 6.0))
        cutter = cylinder(radius=max(0.2, d*0.5), height=max(1.0, depth), sections=64)
    cutter.apply_translation((x, y, H*0.5))
    out = _boolean_diff(mesh, cutter)
    return out or mesh

def _text_polygon_path(text: str, size_mm: float):
    """ Intenta crear un Path 2D del texto. Fallbacks silenciosos. """
    try:
        from trimesh.path.creation import text as tri_text
        return tri_text(text, font=None, height=size_mm)
    except Exception:
        pass
    try:
        # fallback con matplotlib
        from matplotlib.textpath import TextPath
        from matplotlib.font_manager import FontProperties
        tp = TextPath((0, 0), text, prop=FontProperties(size=size_mm))
        import shapely.geometry as sg
        import shapely.affinity as sa
        poly = sg.Polygon(tp.vertices)
        return poly
    except Exception:
        return None

def _op_text(mesh: trimesh.Trimesh, L: float, W: float, H: float, op: Dict[str, Any]) -> trimesh.Trimesh:
    """ Grabar o extruir texto en la cara superior. """
    txt = str(op.get("text", "")).strip()
    if not txt:
        return mesh
    size = float(op.get("size_mm", 10.0))
    depth = float(op.get("depth_mm", 1.0))
    engrave = bool(op.get("engrave", True))
    x = float(op.get("x_mm", L/2)) - L*0.5
    y = float(op.get("y_mm", W/2)) - W*0.5

    try:
        path_or_poly = _text_polygon_path(txt, size)
        if path_or_poly is None:
            print("[INFO] Texto: no hay backend para trazar fuentes; ignorado.")
            return mesh

        if hasattr(path_or_poly, "polygons_full"):
            # trimesh Path
            solid = path_or_poly.extrude(height=max(0.2, depth))
        else:
            # shapely -> triangulación con trimesh
            solid = trimesh.creation.extrude_polygon(path_or_poly, max(0.2, depth))

        # Colocar en la cara superior
        solid.apply_translation((x, y, H - (depth if engrave else 0.0)))
        if engrave:
            out = _boolean_diff(mesh, solid)
        else:
            out = _boolean_union([mesh, solid])
        return out or mesh
    except Exception as e:
        print("[INFO] Texto ignorado:", e)
        return mesh

def _op_round(mesh: trimesh.Trimesh, r_mm: float) -> trimesh.Trimesh:
    return _apply_rounding_if_possible(mesh, r_mm)

def _op_chamfer(mesh: trimesh.Trimesh, r_mm: float) -> trimesh.Trimesh:
    return _apply_chamfer_if_possible(mesh, r_mm)

def _op_array(mesh: trimesh.Trimesh, L: float, W: float, H: float, op: Dict[str, Any]) -> trimesh.Trimesh:
    """
    Patrón de recortes sencillo: shape circle/rect con nx,ny y pasos dx,dy.
    """
    shape = (op.get("shape") or "circle").lower()
    nx = max(1, int(op.get("nx", 1))); ny = max(1, int(op.get("ny", 1)))
    dx = float(op.get("dx_mm", 10.0)); dy = float(op.get("dy_mm", 10.0))
    start_x = float(op.get("start_x_mm", 10.0))
    start_y = float(op.get("start_y_mm", 10.0))
    depth = float(op.get("depth_mm", H * 1.5))

    cutters = []
    for iy in range(ny):
        for ix in range(nx):
            cx = start_x + ix*dx - L*0.5
            cy = start_y + iy*dy - W*0.5
            if shape == "rect":
                w = float(op.get("w_mm", 6.0)); h = float(op.get("h_mm", 6.0))
                c = box(extents=(w, h, depth))
            else:
                d = float(op.get("d_mm", 4.0))
                c = cylinder(radius=max(0.2, d*0.5), height=depth, sections=48)
            c.apply_translation((cx, cy, H*0.5))
            cutters.append(c)

    out = _boolean_diff(mesh, cutters)
    return out or mesh

def _apply_operations(mesh: trimesh.Trimesh, p: dict, operations: Optional[List[Dict[str, Any]]]) -> trimesh.Trimesh:
    if not operations:
        return mesh
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    current = mesh
    for op in operations:
        try:
            typ = (op.get("type") or "").lower()
            if typ == "cutout":
                current = _op_cutout(current, L, W, H, op)
            elif typ == "text":
                current = _op_text(current, L, W, H, op)
            elif typ in ("round", "fillet"):
                current = _op_round(current, float(op.get("r_mm", op.get("radius_mm", 0))))
            elif typ == "chamfer":
                current = _op_chamfer(current, float(op.get("r_mm", op.get("radius_mm", 0))))
            elif typ == "array":
                current = _op_array(current, L, W, H, op)
            else:
                print("[INFO] Operación desconocida, ignorada:", typ)
        except Exception as e:
            print("[WARN] Operación falló y se ignora:", e)
    return current

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
    model: str = Field(..., description="nombre del modelo")
    params: Params
    holes: Optional[List[Hole]] = []
    outputs: Optional[List[str]] = None          # ["stl","svg"]
    operations: Optional[List[Dict[str, Any]]] = None  # 🔹 NUEVO

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
            builder = REGISTRY[k]
            chosen = k
            break
    if builder is None:
        raise RuntimeError(f"Modelo desconocido: {req.model}. Disponibles: {', '.join(REGISTRY.keys())}")

    # 1) Malla base de modelo
    mesh = builder(p, req.holes or [])

    # 2) Fillet básico desde params
    f = float(p.get("fillet_mm") or 0.0)
    if f > 0:
        mesh = _apply_rounding_if_possible(mesh, f)

    # 3) 🔹 Operaciones universales (opcionales)
    mesh = _apply_operations(mesh, p, req.operations)

    # Exportar STL
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

    # SVG opcional SOLO donde tenga sentido (ej. cable_tray) — mantenemos conservador
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
