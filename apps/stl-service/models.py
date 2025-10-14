# apps/stl-service/models.py
from __future__ import annotations
import math
import traceback
from typing import Callable, Dict, List, Mapping, Any

import trimesh
from trimesh.creation import box, cylinder, icosphere

# ------------------------------
# Utilidades booleanas robustas
# ------------------------------

def _difference_safe(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Intenta a - b usando varios motores. Si todo falla, devuelve 'a' sin romper.
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
        if isinstance(res, list) and len(res) > 0:
            return trimesh.util.concatenate(res)
        if isinstance(res, trimesh.Scene):
            return res.dump(concatenate=True)
    except Exception:
        pass

    # 3) último recurso: no romper
    traceback.print_exc()
    return a


def _union_safe(meshes: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    """
    Une varias mallas. Evita convex_hull salvo último último recurso,
    para no “rellenar huecos” y cambiar la forma.
    """
    meshes = [m for m in meshes if m is not None]
    if not meshes:
        return box(extents=(1, 1, 1))

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

    try:
        return trimesh.util.concatenate(meshes)
    except Exception:
        pass

    return meshes[0]


def _ensure_watertight(m: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Intenta devolver algo imprimible aunque las booleanas no sean perfectas.
    """
    try:
        if not m.is_watertight:
            m = m.fill_holes()
        if not m.is_watertight:
            m = m.convex_hull
    except Exception:
        traceback.print_exc()
    return m


# -------------------------------------
# Agujeros por la cara superior (Z+)
# -------------------------------------

def _add_holes_top(base: trimesh.Trimesh, holes: List[Mapping[str, Any]], L: float, H: float) -> trimesh.Trimesh:
    if not holes:
        return base

    out = base
    for h in holes:
        try:
            x_mm = float(h.get("x_mm") if isinstance(h, dict) else getattr(h, "x_mm", 0.0))
            d_mm = float(h.get("d_mm") if isinstance(h, dict) else getattr(h, "d_mm", 0.0))
        except Exception:
            continue

        if d_mm <= 0:
            continue

        r = max(0.15, d_mm / 2.0)
        cx = x_mm - (L / 2.0)
        drill = cylinder(radius=r, height=max(H * 3.0, 60.0), sections=64)
        drill.apply_translation((cx, 0.0, H))
        out = _difference_safe(out, drill)

    return out


# ---------------------------------------------
# Fillet superior: aristas + esquinas (robusto)
# ---------------------------------------------

def _fillet_top_edges(base: trimesh.Trimesh, L: float, W: float, H: float, r: float) -> trimesh.Trimesh:
    """
    Aproximación de fillet en las 4 aristas superiores exteriores.
    """
    if r <= 0:
        return base

    r = float(max(0.2, min(r, min(L, W) * 0.25)))
    out = base

    # Cilindros alineados con X
    cyl_x = cylinder(radius=r, height=L + 2 * r, sections=64)
    cyl_x.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
    c1 = cyl_x.copy(); c1.apply_translation((0.0, +W / 2.0, H - r))
    c2 = cyl_x.copy(); c2.apply_translation((0.0, -W / 2.0, H - r))

    # Cilindros alineados con Y
    cyl_y = cylinder(radius=r, height=W + 2 * r, sections=64)
    cyl_y.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
    c3 = cyl_y.copy(); c3.apply_translation((+L / 2.0, 0.0, H - r))
    c4 = cyl_y.copy(); c4.apply_translation((-L / 2.0, 0.0, H - r))

    # Esferas en esquinas
    s = icosphere(subdivisions=3, radius=r)
    s1 = s.copy(); s1.apply_translation((+L / 2.0, +W / 2.0, H - r))
    s2 = s.copy(); s2.apply_translation((+L / 2.0, -W / 2.0, H - r))
    s3 = s.copy(); s3.apply_translation((-L / 2.0, +W / 2.0, H - r))
    s4 = s.copy(); s4.apply_translation((-L / 2.0, -W / 2.0, H - r))

    cutters = [c1, c2, c3, c4, s1, s2, s3, s4]
    for cutter in cutters:
        try:
            out = _difference_safe(out, cutter)
        except Exception:
            traceback.print_exc()
            continue

    return out


# ----------------------------
# Constructores de modelos
# ----------------------------

def cable_tray(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(0.6, float(p.get("thickness_mm", 3.0)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or 0.0)

    outer = box(extents=(L, W, H)); outer.apply_translation((0, 0, H / 2.0))
    inner_h = max(0.0, H - t)
    inner = box(extents=(max(0.1, L - 2 * t), max(0.1, W - 2 * t), inner_h))
    inner.apply_translation((0, 0, inner_h / 2.0))

    shell = _difference_safe(outer, inner)
    shell = _add_holes_top(shell, holes, L, H)
    if fillet_r > 0:
        shell = _fillet_top_edges(shell, L, W, H, fillet_r)
    return _ensure_watertight(shell)


def vesa_adapter(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W = float(p["length_mm"]), float(p["width_mm"])
    t = max(2.0, float(p.get("thickness_mm", 3.0)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or 0.0)

    plate = box(extents=(L, W, t)); plate.apply_translation((0, 0, t / 2.0))

    spacing = 100.0 if min(L, W) >= 110 else 75.0
    for sx in (-spacing / 2, spacing / 2):
        for sy in (-spacing / 2, spacing / 2):
            drill = cylinder(radius=2.5, height=max(t * 3, 10), sections=48)
            drill.apply_translation((sx, sy, t))
            plate = _difference_safe(plate, drill)

    plate = _add_holes_top(plate, holes, L, t)
    if fillet_r > 0:
        plate = _fillet_top_edges(plate, L, W, t, fillet_r)
    return _ensure_watertight(plate)


def router_mount(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(2.0, float(p.get("thickness_mm", 3.0)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or 0.0)

    base = box(extents=(L, W, t)); base.apply_translation((0, 0, t / 2.0))
    wall = box(extents=(L, t, H)); wall.apply_translation((0, (W / 2.0) - (t / 2.0), H / 2.0))

    m = _union_safe([base, wall])
    m = _add_holes_top(m, holes, L, t)
    if fillet_r > 0:
        m = _fillet_top_edges(m, L, W, max(H, t), fillet_r)
    return _ensure_watertight(m)


def wall_bracket(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(2.0, float(p.get("thickness_mm", 3.0)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or 0.0)

    foot = box(extents=(L, W, t)); foot.apply_translation((0, 0, t / 2.0))
    up = box(extents=(t, W, H)); up.apply_translation(((L / 2.0) - (t / 2.0), 0, H / 2.0))
    m = _union_safe([foot, up])

    pattern = [{"x_mm": L * 0.25, "d_mm": 6.0}, {"x_mm": L * 0.75, "d_mm": 6.0}]
    m = _add_holes_top(m, (holes or []) + pattern, L, t)

    if fillet_r > 0:
        m = _fillet_top_edges(m, L, W, max(H, t), fillet_r)
    return _ensure_watertight(m)


def desk_hook(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    """
    Gancho simple en J.
    """
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(3.0, float(p.get("thickness_mm", 4.0)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or 0.0)

    spine = box(extents=(t, W, H)); spine.apply_translation((-(L / 2.0) + t / 2.0, 0, H / 2.0))
    arm = box(extents=(L * 0.6, W, t)); arm.apply_translation((-(L * 0.2), 0, t / 2.0))

    m = _union_safe([spine, arm])
    m = _add_holes_top(m, holes, L, max(H, t))
    if fillet_r > 0:
        m = _fillet_top_edges(m, L, W, max(H, t), fillet_r)
    return _ensure_watertight(m)


def fan_guard(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    """
    Rejilla plana: placa de espesor t con apertura circular central y 4 taladros.
    """
    L, W = float(p["length_mm"]), float(p["width_mm"])
    t = max(2.0, float(p.get("thickness_mm", 2.5)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or 0.0)

    plate = box(extents=(L, W, t)); plate.apply_translation((0, 0, t / 2.0))

    # Apertura central
    r_open = max(10.0, min(L, W) * 0.35)
    open_cyl = cylinder(radius=r_open, height=max(t * 3, 10.0), sections=96)
    open_cyl.apply_translation((0, 0, t))
    plate = _difference_safe(plate, open_cyl)

    # 4 agujeros de fijación
    pad = min(L, W) * 0.6
    for sx in (-pad / 2, pad / 2):
        for sy in (-pad / 2, pad / 2):
            drill = cylinder(radius=2.5, height=max(t * 3, 10), sections=48)
            drill.apply_translation((sx, sy, t))
            plate = _difference_safe(plate, drill)

    plate = _add_holes_top(plate, holes, L, t)
    if fillet_r > 0:
        plate = _fillet_top_edges(plate, L, W, t, fillet_r)
    return _ensure_watertight(plate)


# -----------------------------
# Registro visible al backend
# -----------------------------
REGISTRY: Dict[str, Callable[[Mapping[str, float], List[Mapping[str, Any]]], trimesh.Trimesh]] = {
    "cable_tray": cable_tray,
    "vesa_adapter": vesa_adapter,
    "router_mount": router_mount,
    "wall_bracket": wall_bracket,
    "desk_hook": desk_hook,
    "fan_guard": fan_guard,
}
