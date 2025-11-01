# apps/stl-service/models/vesa_shelf.py
# Estante VESA para mini-PC/NUC con quick-release básico (opcional)
# Implementado con trimesh, evitando motores externos (OpenSCAD).
from __future__ import annotations

from typing import Dict, Any, Tuple, List, Optional
import trimesh

# Booleanos tolerantes (sin engine="scad")
from ._booleans import union as bool_union, difference as bool_difference

DEFAULTS: Dict[str, Any] = {
    "vesa": 100.0,        # 75 / 100 / 200 (mm)
    "thickness": 4.0,     # grosor de placa y estante (mm)
    "shelf_width": 180.0, # ancho útil del estante (mm, eje X)
    "shelf_depth": 120.0, # fondo del estante (mm, eje Y; se extiende hacia -Y)
    "lip_height": 15.0,   # pestaña frontal anti-caída (mm)
    "rib_count": 3,       # nº de refuerzos verticales (tabiques)
    "hole_d": 5.0,        # diámetro taladros VESA (mm)
    "qr_enabled": True,   # quick-release mediante ranura
    "qr_slot_w": 18.0,
    "qr_slot_h": 6.0,
    "qr_offset_y": 12.0,  # desplazamiento de la ranura en +Z respecto al centro de la placa
}

def _box(extents: Tuple[float, float, float]) -> trimesh.Trimesh:
    return trimesh.creation.box(extents=extents)

def _cyl(radius: float, height: float, sections: int = 64) -> trimesh.Trimesh:
    return trimesh.creation.cylinder(radius=radius, height=height, sections=sections)

def _move(m: trimesh.Trimesh, x=0.0, y=0.0, z=0.0) -> trimesh.Trimesh:
    out = m.copy()
    out.apply_translation([x, y, z])
    return out

def _vesa_hole_positions(pitch: float) -> List[Tuple[float, float]]:
    """Coordenadas X/Z para los 4 agujeros VESA respecto al centro de la placa."""
    half = pitch / 2.0
    return [(-half, -half), (half, -half), (-half, half), (half, half)]

def _safe_union(parts: List[Optional[trimesh.Trimesh]]) -> trimesh.Trimesh:
    ps = [p for p in parts if isinstance(p, trimesh.Trimesh) and p.vertices.shape[0] > 0]
    if not ps:
        return trimesh.Trimesh()
    if len(ps) == 1:
        return ps[0]
    res = bool_union(ps)
    return res if isinstance(res, trimesh.Trimesh) else trimesh.util.concatenate(ps)

def _safe_diff(a: trimesh.Trimesh, cutters: List[Optional[trimesh.Trimesh]]) -> trimesh.Trimesh:
    out = a.copy()
    for c in cutters:
        if not isinstance(c, trimesh.Trimesh) or c.vertices.shape[0] == 0:
            continue
        res = bool_difference(out, c)
        out = res if isinstance(res, trimesh.Trimesh) else out
    return out

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    """
    Construye el estante VESA.
    Convenciones:
      - Unidades en mm.
      - Ejes: X (ancho), Y (fondo; el estante se extiende hacia -Y), Z (alto).
      - La base del conjunto queda en Z=0.
    """
    p = DEFAULTS.copy()
    if params:
      p.update(params)

    # Normaliza numéricos con mínimos para evitar degenerados
    vesa      = max(50.0, float(p.get("vesa", DEFAULTS["vesa"])))
    t         = max(1.2, float(p.get("thickness", DEFAULTS["thickness"])))
    w         = max(40.0, float(p.get("shelf_width", DEFAULTS["shelf_width"])))
    d         = max(30.0, float(p.get("shelf_depth", DEFAULTS["shelf_depth"])))
    lip_h     = max(0.0, float(p.get("lip_height", DEFAULTS["lip_height"])))
    ribs      = int(p.get("rib_count", DEFAULTS["rib_count"]))
    hole_d    = max(2.0, float(p.get("hole_d", DEFAULTS["hole_d"])))
    qr_enable = bool(p.get("qr_enabled", DEFAULTS["qr_enabled"]))
    slot_w    = max(4.0, float(p.get("qr_slot_w", DEFAULTS["qr_slot_w"])))
    slot_h    = max(2.0, float(p.get("qr_slot_h", DEFAULTS["qr_slot_h"])))
    qr_off    = float(p.get("qr_offset_y", DEFAULTS["qr_offset_y"]))

    # 1) Placa trasera (vesa + margen)
    margin = 40.0
    back_w = vesa + margin
    back_h = vesa + margin
    back = _box((back_w, t, back_h))
    back = _move(back, 0, 0, back_h / 2.0)

    # 2) Taladros VESA
    vesa_holes: List[trimesh.Trimesh] = []
    for hx, hz in _vesa_hole_positions(vesa):
        cyl = _cyl(radius=hole_d / 2.0, height=t * 2.0)
        cyl = _move(cyl, hx, 0, back_h / 2.0 + hz)
        vesa_holes.append(cyl)
    back = _safe_diff(back, vesa_holes)

    # 3) Estante (sale hacia -Y)
    shelf = _box((w, d, t))
    shelf = _move(shelf, 0, -(d / 2.0 + t / 2.0), t / 2.0)

    # 4) Pestaña frontal
    lip = _box((w, t, lip_h))
    lip = _move(lip, 0, -(d + t) / 2.0, t / 2.0 + lip_h / 2.0)

    # 5) Refuerzos
    ribs_meshes: List[trimesh.Trimesh] = []
    if ribs > 0:
        step = w / (ribs + 1)
        xs = [(-w / 2.0 + step * (i + 1)) for i in range(ribs)]
        for x in xs:
            rib = _box((t, d, t))
            rib = _move(rib, x, -(d / 2.0 + t / 2.0), t / 2.0)
            ribs_meshes.append(rib)

    model = _safe_union([back, shelf, lip] + ribs_meshes)

    # 6) Quick-release (ranura rectangular)
    if qr_enable:
        slot = _box((slot_w, t * 2.0, slot_h))
        slot = _move(slot, 0, 0, back_h / 2.0 + qr_off)
        model = _safe_diff(model, [slot])

    model = model.copy()
    model.metadata = {"name": "vesa_shelf", "unit": "mm"}
    return model
