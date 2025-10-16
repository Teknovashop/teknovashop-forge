# apps/stl-service/models/__init__.py
import math
import numpy as np
import trimesh
from trimesh.creation import box, cylinder

# ---------------- utilidades geométricas ----------------
def _box_xyz(x, y, z) -> trimesh.Trimesh:
    # box() usa extents (anchos), centrado en (0,0,0)
    m = box(extents=[x, y, z])
    # dejamos la base apoyada en Z=0 para que los agujeros y el texto sean más previsibles
    minz = float(m.bounds[0][2])
    if minz != 0.0:
        m.apply_translation((0.0, 0.0, -minz))
    return m

def _rounded_plate(length, width, thickness, r=0.0) -> trimesh.Trimesh:
    # Placa rectangular con posible redondeo aproximado (circulos + box)
    base = _box_xyz(length, width, thickness)
    if r <= 0.0:
        return base
    r = min(r, length/2.0, width/2.0)
    # aproximación: union de un rectángulo (encogido) + 4 cilindros tumbados en las esquinas
    rect = _box_xyz(length - 2*r, width, thickness)
    rect.apply_translation((0.0, 0.0, 0.0))
    c1 = cylinder(radius=r, height=thickness, sections=64)
    c2 = c1.copy(); c3 = c1.copy(); c4 = c1.copy()
    # tumbar cilindros: por defecto cilindro está en Z, queremos "discos" en Z
    # en realidad cylinder(radius, height) ya crea “tubo” en Z, que nos vale para esquinas como discos.
    # posicionar discos en esquinas (x,y) del rectángulo
    L = (length/2.0 - r)
    W = (width/2.0)
    for c, sx, sy in [(c1, +L, +W), (c2, -L, +W), (c3, +L, -W), (c4, -L, -W)]:
        c.apply_translation((sx, sy, thickness*0.5))
    try:
        out = rect.union([c1, c2, c3, c4])
        if isinstance(out, list):
            out = trimesh.util.concatenate(out)
        # centrar a (0,0) en XY como el base
        out.apply_translation((-out.bounds.mean(axis=0)[0], -out.bounds.mean(axis=0)[1], -out.bounds[0][2]))
        return out
    except Exception:
        # fallback: sin redondeo
        return base

# ---------------- builders ----------------
def make_vesa_adapter(p):
    # placa con agujeros VESA 75 y 100
    L = float(p.get("length_mm") or 120)
    W = float(p.get("width_mm") or 100)
    T = float(p.get("thickness_mm") or 3)
    fillet = float(p.get("fillet_mm") or 0.0)

    plate = _rounded_plate(L, W, T, r=fillet*0.5)  # pequeño redondeo aproximado en contorno si se define

    # creamos agujeros estándar (se restarán en app.py), aquí solo devolvemos placa
    return plate

def make_cable_tray(p):
    # Bandeja en U simple paramétrica
    L = float(p.get("length_mm") or 120)
    W = float(p.get("width_mm") or 60)
    H = float(p.get("height_mm") or 40)
    T = float(p.get("thickness_mm") or 3)

    base = _box_xyz(L, W, T)
    wall1 = _box_xyz(L, T, H)
    wall2 = wall1.copy()

    # colocar paredes a ambos lados del eje Y
    wall1.apply_translation((0, + (W/2.0 - T/2.0), H/2.0))
    wall2.apply_translation((0, - (W/2.0 - T/2.0), H/2.0))

    try:
        u = base.union([wall1, wall2])
        if isinstance(u, list):
            u = trimesh.util.concatenate(u)
        return u
    except Exception:
        return trimesh.util.concatenate([base, wall1, wall2])

def make_router_mount_l(p):
    # Soporte en “L” simple
    L = float(p.get("length_mm") or 120)
    W = float(p.get("width_mm") or 40)
    H = float(p.get("height_mm") or 60)
    T = float(p.get("thickness_mm") or 3)

    plate1 = _box_xyz(L, W, T)
    plate2 = _box_xyz(H, W, T)
    # colocamos plate2 al final de L y elevamos para que forme L
    plate2.apply_translation((L/2.0 - T/2.0, 0.0, H/2.0))
    try:
        u = plate1.union(plate2)
        if isinstance(u, list):
            u = trimesh.util.concatenate(u)
        return u
    except Exception:
        return trimesh.util.concatenate([plate1, plate2])

def make_cable_clip(p):
    # Clip sencillo tipo "C"
    W = float(p.get("width_mm") or 20)
    H = float(p.get("height_mm") or 15)
    T = float(p.get("thickness_mm") or 3)
    gap = max(4.0, float(p.get("gap_mm") or 8.0))

    outer = _box_xyz(W, H, T)
    inner = _box_xyz(W - 2*T, H - gap, T + 0.2)
    inner.apply_translation((0.0, (gap/2.0), 0.0))  # deja una abertura

    try:
        diff = outer.difference(inner)
        if isinstance(diff, list):
            diff = trimesh.util.concatenate(diff)
        return diff
    except Exception:
        return outer

# ---------------- REGISTRY ----------------
REGISTRY = {
    # Slugs que el frontend usa (normalizados a lower+underscore)
    "vesa_adapter": {
        "defaults": {"length_mm": 120, "width_mm": 100, "thickness_mm": 3, "height_mm": 60},
        "make": make_vesa_adapter,
    },
    "cable_tray_bandeja": {  # opción del menú “Cable Tray (bandeja)”
        "defaults": {"length_mm": 120, "width_mm": 60, "height_mm": 40, "thickness_mm": 3},
        "make": make_cable_tray,
    },
    "router_mount_l": {
        "defaults": {"length_mm": 120, "width_mm": 40, "height_mm": 60, "thickness_mm": 3},
        "make": make_router_mount_l,
    },
    "cable_clip": {
        "defaults": {"width_mm": 20, "height_mm": 15, "thickness_mm": 3, "gap_mm": 8},
        "make": make_cable_clip,
    },

    # Placeholders seguros para que NUNCA “no pinte”
    # Sustituye/añade tus builders reales a medida que quieras
    "headset_stand":        {"defaults": {"length_mm": 100, "width_mm": 40, "height_mm": 60, "thickness_mm": 3}, "make": make_router_mount_l},
    "phone_dock_usb_c":     {"defaults": {"length_mm": 100, "width_mm": 60, "height_mm": 40, "thickness_mm": 3}, "make": make_cable_tray},
    "tablet_stand":         {"defaults": {"length_mm": 140, "width_mm": 60, "height_mm": 80, "thickness_mm": 3}, "make": make_router_mount_l},
    "ssd_holder_2_5":       {"defaults": {"length_mm": 100, "width_mm": 70, "height_mm": 15, "thickness_mm": 3}, "make": make_cable_tray},
    "raspberry_pi_case":    {"defaults": {"length_mm": 90, "width_mm": 61, "height_mm": 30, "thickness_mm": 3},  "make": make_cable_tray},
    "gopro_mount":          {"defaults": {"length_mm": 60, "width_mm": 30, "height_mm": 20, "thickness_mm": 3},  "make": make_cable_tray},
    "wall_hook":            {"defaults": {"length_mm": 60, "width_mm": 20, "height_mm": 30, "thickness_mm": 3},  "make": make_router_mount_l},
    "monitor_stand":        {"defaults": {"length_mm": 160, "width_mm": 80, "height_mm": 80, "thickness_mm": 3}, "make": make_router_mount_l},
    "laptop_stand":         {"defaults": {"length_mm": 200, "width_mm": 100, "height_mm": 80, "thickness_mm": 3}, "make": make_router_mount_l},
    "mic_arm_clip":         {"defaults": {"length_mm": 40, "width_mm": 20, "height_mm": 20, "thickness_mm": 3},  "make": make_cable_clip},
    "camera_plate_1_4":     {"defaults": {"length_mm": 60, "width_mm": 40, "height_mm": 5, "thickness_mm": 5},  "make": make_vesa_adapter},
    "usb_hub_holder":       {"defaults": {"length_mm": 120, "width_mm": 40, "height_mm": 30, "thickness_mm": 3}, "make": make_cable_tray},
}
