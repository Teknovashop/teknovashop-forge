# apps/stl-service/models.py
from __future__ import annotations
import math
import traceback
from typing import Callable, Dict, List, Mapping, Any

import trimesh
from trimesh.creation import box, cylinder

# ------------------------------------------------------------
# Utilidades robustas para booleanas (evita romper generación)
# ------------------------------------------------------------

def _difference_safe(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
    try:
        # 1) Si Manifold3D está disponible y el binding de trimesh lo soporta
        import manifold3d  # noqa: F401
        if hasattr(a, "difference"):
            return a.difference(b)
    except Exception:
        pass

    try:
        # 2) OpenSCAD si está disponible en el entorno
        if hasattr(trimesh.interfaces, "scad") and trimesh.interfaces.scad.exists:
            return a.difference(b, engine="scad")
    except Exception:
        pass

    try:
        # 3) Diferencia por defecto de trimesh (puede fallar según entorno)
        return a.difference(b)
    except Exception:
        traceback.print_exc()
        # 4) Si todo falla, devolvemos 'a' sin modificar para no romper
        return a


def _union_safe(meshes: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    meshes = [m for m in meshes if m is not None]
    if not meshes:
        return box(extents=(1, 1, 1))

    try:
        import manifold3d  # noqa: F401
        return trimesh.util.concatenate(meshes).convex_hull  # fallback “sólido”
    except Exception:
        pass

    try:
        return trimesh.boolean.union(meshes)
    except Exception:
        try:
            if hasattr(trimesh.interfaces, "scad") and trimesh.interfaces.scad.exists:
                return trimesh.boolean.union(meshes, engine="scad")
        except Exception:
            traceback.print_exc()
    # últimos recursos
    try:
        return trimesh.util.concatenate(meshes)
    except Exception:
        return meshes[0]


# ------------------------------------------------------------
# Agujeros (taladros) desde la cara superior
# ------------------------------------------------------------

def _add_holes_top(base: trimesh.Trimesh, holes: List[Mapping[str, Any]], L: float, H: float) -> trimesh.Trimesh:
    """
    Agujeros con coordenada x (mm) en [0..L], centrados en Y, perforando hacia -Z.
    Cada agujero: {"x_mm": ..., "d_mm": ...}
    """
    if not holes:
        return base

    out = base
    for h in holes:
        try:
            # Acepta dicts o modelos pydantic (vía getattr)
            x_mm = float(h.get("x_mm") if isinstance(h, dict) else getattr(h, "x_mm", 0.0))
            d_mm = float(h.get("d_mm") if isinstance(h, dict) else getattr(h, "d_mm", 0.0))
        except Exception:
            # Silencio cualquier dato chungo
            continue

        if d_mm <= 0:
            continue

        r = max(0.1, d_mm / 2.0)
        # x centrado en [-L/2, L/2]
        cx = x_mm - (L / 2.0)
        # Cilindro largo para asegurar perforación completa
        drill = cylinder(radius=r, height=max(H * 3.0, 60.0), sections=64)
        # En trimesh, cylinder va a lo largo de Z y centrado en el origen;
        # lo subimos para que cruce la pieza
        drill.apply_translation((cx, 0.0, H))

        out = _difference_safe(out, drill)

    return out


# ------------------------------------------------------------
# Fillet básico (aristas superiores) – aproximación
# ------------------------------------------------------------

def _fillet_top_edges(base: trimesh.Trimesh, L: float, W: float, H: float, r: float) -> trimesh.Trimesh:
    """
    Aproximación de “redondeo” en las 4 aristas superiores exteriores de un paralelepípedo:
    se restan 4 cilindros alineados con X/Y en las aristas. No es un fillet perfecto de CAD,
    pero funciona visualmente y evita romper si el motor booleano no está.
    """
    if r <= 0:
        return base

    r = max(0.1, min(r, min(L, W) * 0.25))
    out = base

    # Dos cilindros a lo largo de X (en Y=±W/2) y dos a lo largo de Y (en X=±L/2)
    # 1) cilindros a lo largo de X: rotamos 90° alrededor de Y para que su eje sea X
    cyl_x = cylinder(radius=r, height=L + 2 * r, sections=64)
    cyl_x.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
    # 2) cilindros a lo largo de Y: rotamos 90° alrededor de X para que su eje sea Y
    cyl_y = cylinder(radius=r, height=W + 2 * r, sections=64)
    cyl_y.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))

    # Posiciones (a la altura del canto superior)
    zc = H - r

    # Y = +W/2 y Y = -W/2  (cilindros paralelos al eje X)
    c1 = cyl_x.copy()
    c1.apply_translation((0.0, +W / 2.0, zc))
    c2 = cyl_x.copy()
    c2.apply_translation((0.0, -W / 2.0, zc))

    # X = +L/2 y X = -L/2  (cilindros paralelos al eje Y)
    c3 = cyl_y.copy()
    c3.apply_translation((+L / 2.0, 0.0, zc))
    c4 = cyl_y.copy()
    c4.apply_translation((-L / 2.0, 0.0, zc))

    for cutter in (c1, c2, c3, c4):
        out = _difference_safe(out, cutter)

    return out


# ------------------------------------------------------------
# Constructores de modelos
# ------------------------------------------------------------

def cable_tray(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = p["length_mm"], p["width_mm"], p["height_mm"]
    t = max(0.6, float(p.get("thickness_mm", 3.0)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or 0.0)

    # Bandeja en "U": caja exterior menos caja interior (abierta por arriba)
    outer = box(extents=(L, W, H))
    outer.apply_translation((0, 0, H / 2.0))

    inner_h = max(0.0, H - t)  # mantiene base de grosor t
    inner = box(extents=(L - 2 * t, W - 2 * t, inner_h))
    inner.apply_translation((0, 0, inner_h / 2.0))

    shell = _difference_safe(outer, inner)
    shell = _add_holes_top(shell, holes, L, H)

    if fillet_r > 0:
        shell = _fillet_top_edges(shell, L, W, H, fillet_r)

    return shell


def vesa_adapter(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = p["length_mm"], p["width_mm"], p["height_mm"]
    t = max(2.0, float(p.get("thickness_mm", 3.0)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or 0.0)

    # Placa de espesor t (usamos H como “tamaño visual” y forzamos espesor t real)
    plate = box(extents=(L, W, t))
    plate.apply_translation((0, 0, t / 2.0))

    # Agujeros VESA: calculamos patrón 75 o 100 en función de L/W
    spacing = 100.0 if min(L, W) >= 110 else 75.0
    d = 5.0
    for sx in (-spacing / 2, spacing / 2):
        for sy in (-spacing / 2, spacing / 2):
            drill = cylinder(radius=d / 2, height=max(t * 3, 10), sections=48)
            drill.apply_translation((sx, sy, t))  # taladra desde arriba
            plate = _difference_safe(plate, drill)

    # Agujeros adicionales custom (x solo, se asumen centrados en Y)
    plate = _add_holes_top(plate, holes, L, t)

    if fillet_r > 0:
        plate = _fillet_top_edges(plate, L, W, t, fillet_r)

    return plate


def router_mount(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    L, W, H = p["length_mm"], p["width_mm"], p["height_mm"]
    t = max(2.0, float(p.get("thickness_mm", 3.0)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or 0.0)

    # Soporte en “L”: base + pared
    base = box(extents=(L, W, t))
    base.apply_translation((0, 0, t / 2.0))

    wall = box(extents=(L, t, H))
    wall.apply_translation((0, (W / 2.0) - (t / 2.0), H / 2.0))

    mount = _union_safe([base, wall])

    # Agujeros en la base (por arriba)
    mount = _add_holes_top(mount, holes, L, t)

    if fillet_r > 0:
        mount = _fillet_top_edges(mount, L, W, max(H, t), fillet_r)

    return mount


def wall_bracket(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    # Variante de L con base más ancha y más taladros
    L, W, H = p["length_mm"], p["width_mm"], p["height_mm"]
    t = max(2.0, float(p.get("thickness_mm", 3.0)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or 0.0)

    foot = box(extents=(L, W, t))
    foot.apply_translation((0, 0, t / 2.0))
    up = box(extents=(t, W, H))
    up.apply_translation(((L / 2.0) - (t / 2.0), 0, H / 2.0))
    m = _union_safe([foot, up])

    # Taladros simétricos en el pie
    pattern = [
        {"x_mm": L * 0.25, "d_mm": 6.0},
        {"x_mm": L * 0.75, "d_mm": 6.0},
    ]
    m = _add_holes_top(m, pattern + (holes or []), L, t)

    if fillet_r > 0:
        m = _fillet_top_edges(m, L, W, max(H, t), fillet_r)

    return m


def desk_hook(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    # Gancho sencillo tipo “J” abstracto con 2 sólidos unidos
    L, W, H = p["length_mm"], p["width_mm"], p["height_mm"]
    t = max(3.0, float(p.get("thickness_mm", 4.0)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or 0.0)

    spine = box(extents=(t, W, H))
    spine.apply_translation((-(L / 2.0) + t / 2.0, 0, H / 2.0))
    arm = box(extents=(L * 0.6, W, t))
    arm.apply_translation((-(L * 0.2), 0, t / 2.0))
    m = _union_safe([spine, arm])

    m = _add_holes_top(m, holes, L, t)

    if fillet_r > 0:
        m = _fillet_top_edges(m, L, W, H, fillet_r)

    return m


def fan_guard(p: Mapping[str, float], holes: List[Mapping[str, Any]]) -> trimesh.Trimesh:
    # Rejilla plana para ventilador
    L, W, H = p["length_mm"], p["width_mm"], p["height_mm"]
    t = max(2.0, float(p.get("thickness_mm", 2.5)))
    fillet_r = float(p.get("fillet_r_mm", 0.0) or 0.0)

    plate = box(extents=(L, W, t))
    plate.apply_translation((0, 0, t / 2.0))

    # Apertura central circular
    r_open = max(10.0, min(L, W) * 0.35)
    open_cyl = cylinder(radius=r_open, height=max(t * 3, 10.0), sections=96)
    open_cyl.apply_translation((0, 0, t))
    plate = _difference_safe(plate, open_cyl)

    # Cuatro agujeros de fijación
    pad = min(L, W) * 0.5
    for sx in (-pad / 2, pad / 2):
        for sy in (-pad / 2, pad / 2):
            drill = cylinder(radius=2.5, height=max(t * 3, 10), sections=48)
            drill.apply_translation((sx, sy, t))
            plate = _difference_safe(plate, drill)

    plate = _add_holes_top(plate, holes, L, t)
    if fillet_r > 0:
        plate = _fillet_top_edges(plate, L, W, t, fillet_r)

    return plate


# ------------------------------------------------------------
# REGISTRY visible para el backend
# ------------------------------------------------------------

REGISTRY: Dict[str, Callable[[Mapping[str, float], List[Mapping[str, Any]]], trimesh.Trimesh]] = {
    "cable_tray": cable_tray,
    "vesa_adapter": vesa_adapter,
    "router_mount": router_mount,
    "wall_bracket": wall_bracket,
    "desk_hook": desk_hook,
    "fan_guard": fan_guard,
}
