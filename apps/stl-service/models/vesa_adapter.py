# apps/stl-service/models/vesa_adapter.py
import math
import trimesh
from typing import List, Tuple, Dict, Any
from trimesh.transformations import translation_matrix as T, rotation_matrix as R


def _get(d: Dict[str, Any], keys: List[str], default: float) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except Exception:
                pass
    return float(default)


def _parse_holes(d: Dict[str, Any]) -> List[Tuple[float, float, float]]:
    raw = d.get("holes") or []
    out: List[Tuple[float, float, float]] = []
    for h in raw:
        x = _get(h, ["x_mm", "x"], 0.0)
        z = _get(h, ["z_mm", "z"], 0.0)
        dmm = _get(h, ["d_mm", "d"], 3.0)
        out.append((x, z, dmm))
    return out


def _plate_with_holes_xz(size_x: float, size_z: float, thickness: float,
                         holes: List[Tuple[float, float, float]], y_center: float) -> trimesh.Trimesh:
    try:
        from shapely.geometry import Polygon, Point
        from shapely.ops import unary_union

        rect = Polygon([
            (-size_x / 2.0, -size_z / 2.0),
            ( size_x / 2.0, -size_z / 2.0),
            ( size_x / 2.0,  size_z / 2.0),
            (-size_x / 2.0,  size_z / 2.0),
        ])
        circles = [Point(x, z).buffer((d / 2.0), resolution=48) for (x, z, d) in holes] if holes else []
        shape = rect.difference(unary_union(circles)) if circles else rect

        m = trimesh.creation.extrude_polygon(shape, height=thickness)
        m.apply_transform(R(math.pi / 2.0, [1, 0, 0]))  # Z → Y
        m.apply_transform(T([0.0, y_center, 0.0]))
        return m
    except Exception:
        m = trimesh.creation.box(extents=[size_x, thickness, size_z])
        m.apply_transform(T([0.0, y_center, 0.0]))
        return m


def make_model(p: dict) -> trimesh.Trimesh:
    """
    Placa VESA centrada en el origen (X,Z), extruida en Y.
    Admite:
      - vesa_mm, thickness_mm|thickness, clearance_mm|clearance, hole_diameter_mm|hole
      - holes?: [{ x_mm|x, z_mm|z, d_mm|d }]  → agujeros adicionales personalizados
    """
    V   = _get(p, ["vesa_mm"], 100.0)
    TCK = _get(p, ["thickness_mm", "thickness"], 4.0)
    CLR = _get(p, ["clearance_mm", "clearance"], 1.0)
    HOLE_D = _get(p, ["hole_diameter_mm", "hole"], 5.0)  # diámetro

    size = V + 2.0 * CLR + 20.0

    # Agujeros del patrón VESA
    off = V / 2.0
    vesa_holes = [
        (+off, +off, HOLE_D),
        (-off, +off, HOLE_D),
        (+off, -off, HOLE_D),
        (-off, -off, HOLE_D),
    ]

    # Agujeros personalizados
    custom_holes = _parse_holes(p)
    all_holes = vesa_holes + custom_holes

    # Placa con agujeros
    plate = _plate_with_holes_xz(
        size_x=size,
        size_z=size,
        thickness=TCK,
        holes=all_holes,
        y_center=0.0,
    )

    return plate
