# apps/stl-service/models/router_mount.py
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


def _get_bool(d: Dict[str, Any], key: str, default: bool) -> bool:
    return bool(d.get(key, default))


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
    Soporte en L:
      X = ancho del router, Z = fondo, Y = altura de la pared.
    Admite:
      - router_width_mm|router_width, router_depth_mm|router_depth, thickness_mm|thickness
      - holes?: [{ x_mm|x, z_mm|z, d_mm|d }]  → aplicados a la base
    """
    W   = _get(p, ["router_width_mm", "router_width"], 120.0)
    D   = _get(p, ["router_depth_mm", "router_depth"], 80.0)
    TCK = _get(p, ["thickness_mm", "thickness"], 4.0)
    H   = _get(p, ["height_mm", "height"], D * 0.6)
    holes = _parse_holes(p)

    # Base con agujeros
    base = _plate_with_holes_xz(
        size_x=W,
        size_z=D,
        thickness=TCK,
        holes=holes,
        y_center=(-D * 0.3),
    )

    # Pared (sin agujeros por ahora)
    wall = trimesh.creation.box(extents=[W, H, TCK])
    wall.apply_transform(T([0.0, 0.0, -D / 2.0 + TCK / 2.0]))

    return trimesh.util.concatenate([base, wall])
