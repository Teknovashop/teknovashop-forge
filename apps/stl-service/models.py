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
    # 1) motor por defecto de trimesh
    try:
        return a.difference(b)
    except Exception:
        pass

    # 2) OpenSCAD si existe
    try:
        if hasattr(trimesh.interfaces, "scad") and trimesh.interfaces.scad.exists:
            return a.difference(b, engine="scad")
    except Exception:
        pass

    # 3) último recurso: no romper
    traceback.print_exc()
    return a


def _union_safe(meshes: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    """
    Une varias mallas. Evita convex_hull salvo último recurso,
    para no “rellenar huecos” y cambiar la forma.
    """
    meshes = [m for m in meshes if m is not None]
    if not meshes:
        return box(extents=(1, 1, 1))

    # 1) union de trimesh
    try:
        return trimesh.boolean.union(meshes)
    except Exception:
        pass

    # 2) OpenSCAD si existe
    try:
        if hasattr(trimesh.interfaces, "scad") and trimesh.interfaces.scad.exists:
            return trimesh.boolean.union(meshes, engine="scad")
    except Exception:
        pass

    # 3) concatenar (no booleano pero mantiene geometría combinada)
    try:
        return trimesh.util.concatenate(meshes)
    except Exception:
        pass

    # 4) último recurso: primera
    return meshes[0]


def _ensure_watertight(m: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Intenta devolver algo imprimible aunque las booleanas no sean perfectas.
    """
    try:
        if not m.is_watertight:
            m = m.fill_holes()
        if not m.is_watertight:
            # como último recurso: convex_hull
            m = m.convex_hull
    except Exception:
        traceback.print_exc()
    return m


# -------------------------------------
# Agujeros por la cara superior (Z+)
# -------------------------------------

def _add_holes_top(base: trimesh.Trimesh, holes: List[Mapping[str, Any]], L: float, H: float, W: float | None = None) -> trimesh.Trimesh:
    """
    Taladros pasantes desde Z+, respetando x_mm e y_mm si vienen.
    El sistema del backend centra el mesh en (0,0), por eso restamos L/2 y W/2.
    """
    if not holes:
        return base

    out = base
    for h in holes:
        try:
            # Acepta dict o pydantic
            x_mm = float(h.get("x_mm") if isinstance(h, dict) else getattr(h, "x_mm", 0.0))
            y_mm = float(h.get("y_mm") if isinstance(h, dict) else getattr(h, "y_mm", 0.0))
            d_mm = float(h.get("d_mm") if isinstance(h, dict) else getattr(h, "d_mm", 0.0))
        except Exception:
            continue

        if d_mm <= 0:
            continue

        r = max(0.15, d_mm / 2.0)
        cx = x_mm - (L / 2.0)
        cy = (y_mm - (W / 2.0)) if (W is not None) else 0.0

        # cilindro largo para atravesar con margen
        drill = cylinder(radius=r, height=max(H * 3.0, 60.0), sections=64)
        drill.apply_translation((cx, cy, H))  # taladro “desde arriba”
        out = _difference_safe(out, drill)

    return out


# ---------------------------------------------
# Fillet superior: aristas + esquinas (robusto)
# ---------------------------------------------

def _fillet_top_edges(base: trimesh.Trimesh, L: float, W: float, H: float, r: float) -> trimesh.Trimesh:
    """
    Aproximación de fillet en las 4 aristas superiores exteriores:
      - Restamos 4 cilindros en aristas
      - Restamos 4 esferas en esquinas
    Más estable que solo cilindros.
    """
    if r <= 0:
        return base

    r = float(max(0.2, min(r, min(L, W) * 0.25)))
    out = base

    # Cilindros alineados con X (en Y=±W/2)
    cyl_x = cylinder(radius=r, height=L + 2 * r, sections=64)
    cyl_x.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))

    c1 = cyl_x.copy(); c1.apply_translation((0.0, +W / 2.0, H - r))
    c2 = cyl_x.copy(); c2.apply_translation((0.0, -W / 2.0, H - r))

    # Cilindros alineados con Y (en X=±L/2)
    cyl_y = cylinder(radius=r, height=W + 2 * r, sections=64)
    cyl_y.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))

    c3 = cyl_y.copy(); c3.apply_translation((+L / 2.0, 0.0, H - r))
    c4 = cyl_y.copy(); c4.apply_translation((-L / 2.0, 0.0, H - r))

    # Esferas en esquinas superiores (suaviza la intersección de cilindros)
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
            # seguimos si una resta falla
            continue

    return out


# ----------------------------
# Constructores de modelos
# ----------------------------

def cable_tray(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(0.6, float(p.get("thickness_mm", 3.0)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or p.get("fillet_mm", 0.0) or 0.0)

    outer = box(extents=(L, W, H)); outer.apply_translation((0, 0, H / 2.0))
    inner_h = max(0.0, H - t)
    inner = box(extents=(max(0.1, L - 2 * t), max(0.1, W - 2 * t), inner_h))
    inner.apply_translation((0, 0, inner_h / 2.0))

    shell = _difference_safe(outer, inner)
    shell = _add_holes_top(shell, holes, L, H, W)
    if fillet_r > 0:
        shell = _fillet_top_edges(shell, L, W, H, fillet_r)
    return _ensure_watertight(shell)


def vesa_adapter(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W = float(p["length_mm"]), float(p["width_mm"])
    t = max(2.0, float(p.get("thickness_mm", 3.0)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or p.get("fillet_mm", 0.0) or 0.0)

    plate = box(extents=(L, W, t)); plate.apply_translation((0, 0, t / 2.0))

    spacing = 100.0 if min(L, W) >= 110 else 75.0
    for sx in (-spacing / 2, spacing / 2):
        for sy in (-spacing / 2, spacing / 2):
            drill = cylinder(radius=2.5, height=max(t * 3, 10), sections=48)
            drill.apply_translation((sx, sy, t))
            plate = _difference_safe(plate, drill)

    plate = _add_holes_top(plate, holes, L, t, W)
    if fillet_r > 0:
        plate = _fillet_top_edges(plate, L, W, t, fillet_r)
    return _ensure_watertight(plate)


def router_mount(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(2.0, float(p.get("thickness_mm", 3.0)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or p.get("fillet_mm", 0.0) or 0.0)

    base = box(extents=(L, W, t)); base.apply_translation((0, 0, t / 2.0))
    wall = box(extents=(L, t, H)); wall.apply_translation((0, (W / 2.0) - (t / 2.0), H / 2.0))

    m = _union_safe([base, wall])
    m = _add_holes_top(m, holes, L, t, W)
    if fillet_r > 0:
        m = _fillet_top_edges(m, L, W, max(H, t), fillet_r)
    return _ensure_watertight(m)


def wall_bracket(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(2.0, float(p.get("thickness_mm", 3.0)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or p.get("fillet_mm", 0.0) or 0.0)

    foot = box(extents=(L, W, t)); foot.apply_translation((0, 0, t / 2.0))
    up = box(extents=(t, W, H)); up.apply_translation(((L / 2.0) - (t / 2.0), 0, H / 2.0))
    m = _union_safe([foot, up])

    pattern = [{"x_mm": L * 0.25, "y_mm": W * 0.5, "d_mm": 6.0},
               {"x_mm": L * 0.75, "y_mm": W * 0.5, "d_mm": 6.0}]
    m = _add_holes_top(m, (holes or []) + pattern, L, t, W)

    if fillet_r > 0:
        m = _fillet_top_edges(m, L, W, max(H, t), fillet_r)
    return _ensure_watertight(m)


def desk_hook(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    """
    Gancho simple en J: “columna” + “brazo”. Sin boolean union agresivo.
    """
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(3.0, float(p.get("thickness_mm", 4.0)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or p.get("fillet_mm", 0.0) or 0.0)

    spine = box(extents=(t, W, H)); spine.apply_translation((-(L / 2.0) + t / 2.0, 0, H / 2.0))
    arm = box(extents=(L * 0.6, W, t)); arm.apply_translation((-(L * 0.2), 0, t / 2.0))

    m = _union_safe([spine, arm])  # usa concatenate si falla union → no 500
    m = _add_holes_top(m, holes, L, max(H, t), W)
    if fillet_r > 0:
        m = _fillet_top_edges(m, L, W, max(H, t), fillet_r)
    return _ensure_watertight(m)


def fan_guard(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    """
    Rejilla plana: placa de espesor t con apertura circular central y 4 taladros.
    """
    L, W = float(p["length_mm"]), float(p["width_mm"])
    t = max(2.0, float(p.get("thickness_mm", 2.5)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or p.get("fillet_mm", 0.0) or 0.0)

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

    plate = _add_holes_top(plate, holes, L, t, W)
    if fillet_r > 0:
        plate = _fillet_top_edges(plate, L, W, t, fillet_r)
    return _ensure_watertight(plate)


# ---------- NUEVOS MODELOS PARA COMPLETAR LOS 16 ----------

def camera_mount(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(2.0, float(p.get("thickness_mm", 3.0)))
    base = box(extents=(L, W, t)); base.apply_translation((0, 0, t/2))
    col_h = max(10.0, H - t)
    col = box(extents=(t*2, t*2, col_h)); col.apply_translation((0, 0, t + col_h/2))
    mesh = _union_safe([base, col])
    mesh = _add_holes_top(mesh, holes, L, max(H, t), W)
    return _ensure_watertight(mesh)

def camera_plate(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W = float(p["length_mm"]), float(p["width_mm"])
    t = max(3.0, float(p.get("thickness_mm", 4.0)))
    plate = box(extents=(L, W, t)); plate.apply_translation((0, 0, t/2))
    # Orificio central (simula 1/4"): ~6.35 mm → r 3.2 mm
    center = cylinder(radius=3.2, height=max(t*3, 12), sections=64)
    center.apply_translation((0, 0, t))
    plate = _difference_safe(plate, center)
    plate = _add_holes_top(plate, holes, L, t, W)
    return _ensure_watertight(plate)

def go_pro_mount(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(3.0, float(p.get("thickness_mm", 4.0)))
    base = box(extents=(L, W, t)); base.apply_translation((0, 0, t/2))
    # Dos orejas/prongs sencillas
    ear_w, ear_t, ear_h = max(W*0.18, 8), t, max(H*0.4, 10)
    e1 = box(extents=(ear_t, ear_w, ear_h)); e1.apply_translation((-L*0.15, 0, t + ear_h/2))
    e2 = box(extents=(ear_t, ear_w, ear_h)); e2.apply_translation(( L*0.15, 0, t + ear_h/2))
    mesh = _union_safe([base, e1, e2])
    mesh = _add_holes_top(mesh, holes, L, max(H, t), W)
    return _ensure_watertight(mesh)

def headset_stand(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(3.0, float(p.get("thickness_mm", 4.0)))
    base = box(extents=(L, W, t)); base.apply_translation((0, 0, t/2))
    col = box(extents=(t*2.0, t*2.0, max(60.0, H))); col.apply_translation((0, 0, t + max(60.0, H)/2))
    top = box(extents=(L*0.5, t*2.0, t*2.0)); top.apply_translation((0, 0, t + max(60.0, H) + t))
    mesh = _union_safe([base, col, top])
    mesh = _add_holes_top(mesh, holes, L, max(H, t), W)
    return _ensure_watertight(mesh)

def hub_holder(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(2.0, float(p.get("thickness_mm", 3.0)))
    u_outer = box(extents=(L, W, H)); u_outer.apply_translation((0, 0, H/2))
    u_inner = box(extents=(L - 2*t, W - 2*t, H - t)); u_inner.apply_translation((0, 0, H/2 + t/2))
    mesh = _difference_safe(u_outer, u_inner)
    mesh = _add_holes_top(mesh, holes, L, H, W)
    return _ensure_watertight(mesh)

def laptop_stand(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(3.0, float(p.get("thickness_mm", 4.0)))
    base = box(extents=(L, W, t)); base.apply_translation((0, 0, t/2))
    wedge = box(extents=(L*0.8, t*2, H)); wedge.apply_translation((-L*0.1, W*0.25, H/2))
    mesh = _union_safe([base, wedge])
    mesh = _add_holes_top(mesh, holes, L, max(H, t), W)
    return _ensure_watertight(mesh)

def mic_arm_clip(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    D = float(p["width_mm"])   # usamos width como diámetro exterior aprox
    H = float(p["height_mm"])  # ancho del clip
    t = max(3.0, float(p.get("thickness_mm", 4.0)))
    outer = cylinder(radius=max(10.0, D/2), height=H, sections=96)
    inner = cylinder(radius=max(5.0, D/2 - t), height=H + 2.0, sections=96)
    inner.apply_translation((0, 0, 0))
    c = _difference_safe(outer, inner)
    # abertura
    slot = box(extents=(t*1.2, D, H + 2.0)); slot.apply_translation((D/2 - t*0.6, 0, 0))
    c = _difference_safe(c, slot)
    c.apply_translation((0, 0, H/2))
    return _ensure_watertight(c)

def monitor_stand(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(4.0, float(p.get("thickness_mm", 5.0)))
    base = box(extents=(L, W, t)); base.apply_translation((0, 0, t/2))
    col = box(extents=(t*3, t*3, max(H*0.8, 60))); col.apply_translation((0, 0, t + max(H*0.8, 60)/2))
    shelf = box(extents=(L*0.7, t*3, t*2)); shelf.apply_translation((0, 0, t + max(H*0.8, 60) + t))
    mesh = _union_safe([base, col, shelf])
    mesh = _add_holes_top(mesh, holes, L, max(H, t), W)
    return _ensure_watertight(mesh)

def phone_dock(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(3.0, float(p.get("thickness_mm", 4.0)))
    base = box(extents=(L, W, t)); base.apply_translation((0, 0, t/2))
    back = box(extents=(t*2, W*0.9, H)); back.apply_translation((-L*0.35, 0, H/2))
    slot = box(extents=(t*1.2, W*0.4, t)); slot.apply_translation((-L*0.35, 0, t*0.8))
    mesh = _difference_safe(_union_safe([base, back]), slot)
    mesh = _add_holes_top(mesh, holes, L, max(H, t), W)
    return _ensure_watertight(mesh)

def raspi_case(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(2.4, float(p.get("thickness_mm", 2.4)))
    outer = box(extents=(L, W, H)); outer.apply_translation((0, 0, H/2))
    inner = box(extents=(L - 2*t, W - 2*t, H - t)); inner.apply_translation((0, 0, H/2 + t/2))
    box_shell = _difference_safe(outer, inner)
    box_shell = _add_holes_top(box_shell, holes, L, H, W)
    return _ensure_watertight(box_shell)

def ssd_holder(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(2.0, float(p.get("thickness_mm", 3.0)))
    tray = box(extents=(L, W, t)); tray.apply_translation((0, 0, t/2))
    lip = box(extents=(L, t*2, t*2)); lip.apply_translation((0, -W/2 + t, t))
    mesh = _union_safe([tray, lip])
    mesh = _add_holes_top(mesh, holes, L, max(H, t), W)
    return _ensure_watertight(mesh)

def tablet_stand(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(3.0, float(p.get("thickness_mm", 4.0)))
    base = box(extents=(L, W, t)); base.apply_translation((0, 0, t/2))
    back = box(extents=(t*2, W*0.8, H)); back.apply_translation((-L*0.35, 0, H/2))
    lip = box(extents=(t*2, W*0.8, t*1.5)); lip.apply_translation((-L*0.1, 0, t*1.0))
    mesh = _union_safe([base, back, lip])
    mesh = _add_holes_top(mesh, holes, L, max(H, t), W)
    return _ensure_watertight(mesh)

def wall_hook(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    t = max(3.0, float(p.get("thickness_mm", 4.0)))
    plate = box(extents=(L, W, t)); plate.apply_translation((0, 0, t/2))
    arm = box(extents=(t*1.5, W*0.5, H)); arm.apply_translation((L*0.3, 0, H/2))
    tip = cylinder(radius=max(t*0.8, 3.0), height=W*0.5, sections=64)
    tip.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2, [1, 0, 0]))
    tip.apply_translation((L*0.3, 0, H))
    mesh = _union_safe([plate, arm, tip])
    mesh = _add_holes_top(mesh, holes, L, max(H, t), W)
    return _ensure_watertight(mesh)


# -----------------------------
# Registro visible al backend
# -----------------------------
REGISTRY: Dict[str, Callable[[Mapping[str, float], List[Mapping[str, Any]]], trimesh.Trimesh]] = {
    # existentes
    "cable_tray":    cable_tray,
    "vesa_adapter":  vesa_adapter,
    "router_mount":  router_mount,
    "wall_bracket":  wall_bracket,
    "desk_hook":     desk_hook,
    "fan_guard":     fan_guard,

    # añadidos para completar catálogo
    "camera_mount":  camera_mount,
    "camera_plate":  camera_plate,
    "go_pro_mount":  go_pro_mount,
    "headset_stand": headset_stand,
    "hub_holder":    hub_holder,
    "laptop_stand":  laptop_stand,
    "mic_arm_clip":  mic_arm_clip,
    "monitor_stand": monitor_stand,
    "phone_dock":    phone_dock,
    "raspi_case":    raspi_case,
    "ssd_holder":    ssd_holder,
    "tablet_stand":  tablet_stand,
    "wall_hook":     wall_hook,
}
