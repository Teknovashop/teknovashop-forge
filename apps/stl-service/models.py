# apps/stl-service/models.py
from __future__ import annotations
import math
from typing import Dict, Any, List, Callable, Optional
import trimesh
from trimesh.creation import box

# ---------- utilidades geométricas ----------

def deg(rad):  # por si alguna vez nos pasan radianes
    return rad * 180.0 / math.pi

def rotz(deg_):
    a = math.radians(deg_)
    return trimesh.transformations.rotation_matrix(a, (0, 0, 1))

def roty(deg_):
    a = math.radians(deg_)
    return trimesh.transformations.rotation_matrix(a, (0, 1, 0))

def rotx(deg_):
    a = math.radians(deg_)
    return trimesh.transformations.rotation_matrix(a, (1, 0, 0))

def translate(v):
    return trimesh.transformations.translation_matrix(v)

# ---------- TextOps: grabado / extrusión de texto ----------
def apply_text_ops(mesh: trimesh.Trimesh, ops: List[Dict[str, Any]]) -> trimesh.Trimesh:
    """Cada op: { text, font?, depth, height, pos:[x,y,z], rot:[rx,ry,rz], mode:'engrave'|'emboss' }"""
    if not ops: 
        return mesh

    acc = mesh.copy()
    for op in ops:
        txt = op.get("text", "")
        if not txt:
            continue
        depth = float(op.get("depth", 1.0))      # mm de extrusión
        height = float(op.get("height", 10.0))   # mm de alto de letra
        mode = op.get("mode", "engrave")         # engrave (resta) o emboss (suma)
        px, py, pz = map(float, op.get("pos", [0, 0, 0]))
        rx, ry, rz = map(float, op.get("rot", [0, 0, 0]))

        # Texto → Path2D → extrude
        path = trimesh.path.creation.text(text=txt, font=op.get("font", None), font_size=height)
        if path is None or len(path.entities) == 0:
            # fallback a una barrita si la lib no tiene font
            glyph = box(extents=(height, depth, depth/2.0))
            glyph.apply_transform(translate([px, py, pz]))
        else:
            poly = path.to_polygons()
            if not poly:
                continue
            text_vol = trimesh.creation.extrude_polygon(poly, height=depth)
            # rotación y posicionamiento
            T = translate([px, py, pz]) @ rotx(rx) @ roty(ry) @ rotz(rz)
            text_vol.apply_transform(T)
            glyph = text_vol

        if mode == "engrave":
            acc = acc.difference(glyph, engine="scad")
        else:
            acc = acc.union(glyph, engine="scad")
    return acc

# ---------- builders reales existentes ----------
def build_cable_tray(p: Dict[str, Any]) -> trimesh.Trimesh:
    L = float(p.get("length", p.get("largo", 120)))
    W = float(p.get("width", p.get("ancho", 100)))
    H = float(p.get("height", p.get("alto", 60)))
    t = float(p.get("wall", p.get("grosor", 3)))
    outer = box(extents=(L, W, t))
    ribs = box(extents=(L, t, H))
    ribs.apply_transform(translate([0, 0, H/2]))
    tray = outer.union(ribs, engine="scad")
    return tray

def build_vesa_adapter(p: Dict[str, Any]) -> trimesh.Trimesh:
    L = float(p.get("largo", 120))
    W = float(p.get("ancho", 100))
    t = float(p.get("grosor", 3))
    plate = box(extents=(L, W, t))
    plate.apply_transform(translate([0, 0, t/2]))
    # cuatro agujeros 75x75 o 100x100 según ancho/largo
    pitch = 75.0 if min(L, W) < 110 else 100.0
    hole_r = 3.25
    holes = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            c = trimesh.creation.cylinder(radius=hole_r, height=t * 2)
            c.apply_transform(translate([sx * pitch/2, sy * pitch/2, t/2]))
            holes.append(c)
    mask = trimesh.util.concatenate(holes)
    return plate.difference(mask, engine="scad")

def build_router_mount(p: Dict[str, Any]) -> trimesh.Trimesh:
    L = float(p.get("largo", 120))
    W = float(p.get("ancho", 60))
    t = float(p.get("grosor", 3))
    base = box(extents=(L, W, t))
    lip = box(extents=(L, t, W/2))
    lip.apply_transform(translate([0, (W/2 - t/2), W/4]))
    return base.union(lip, engine="scad")

# ---------- fallback y registry con alias ----------
def build_plate_fallback(p: Dict[str, Any]) -> trimesh.Trimesh:
    L = float(p.get("largo", p.get("length", 100)))
    W = float(p.get("ancho", p.get("width", 100)))
    t = float(p.get("grosor", p.get("wall", 3)))
    m = box(extents=(L, W, t))
    m.apply_transform(translate([0,0,t/2]))
    return m

REGISTRY: Dict[str, Callable[[Dict[str, Any]], trimesh.Trimesh]] = {
    "cable_tray": build_cable_tray,
    "vesa_adapter": build_vesa_adapter,
    "router_mount": build_router_mount,

    # alias desde el front para no romper UI:
    "Cable Tray (bandeja)": build_cable_tray,
    "VESA Adapter": build_vesa_adapter,
    "Router Mount (L)": build_router_mount,

    # alias que existen en el selector pero aún sin diseño “real”:
    "Cable Clip": build_plate_fallback,
    "Headset Stand": build_plate_fallback,
    "Phone Dock (USB-C)": build_plate_fallback,
    "Tablet Stand": build_plate_fallback,
    "SSD Holder (2.5\")": build_plate_fallback,
    "Raspberry Pi Case": build_plate_fallback,
    "GoPro Mount": build_plate_fallback,
    "Wall Hook": build_plate_fallback,
    "Monitor Stand": build_plate_fallback,
    "Laptop Stand": build_plate_fallback,
    "Mic Arm Clip": build_plate_fallback,
    "Camera Plate 1/4\"": build_plate_fallback,
    "USB Hub Holder": build_plate_fallback,
}

def build_model(slug: str, params: Dict[str, Any], *, text_ops: Optional[List[Dict[str, Any]]] = None) -> trimesh.Trimesh:
    builder = REGISTRY.get(slug)
    if builder is None and slug in ("raspi_case", "hub_holder", "camera_plate", "mic_arm_clip"):
        builder = build_plate_fallback  # alias por slug interno
    if builder is None:
        raise KeyError(f"Model '{slug}' not found")
    mesh = builder(params or {})
    mesh = apply_text_ops(mesh, text_ops or [])
    return mesh
