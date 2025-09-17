# apps/stl-service/models/cable_tray.py
import math
import trimesh
from typing import List, Tuple, Dict, Any
from trimesh.transformations import translation_matrix as T, rotation_matrix as R


def _get(d: Dict[str, Any], keys: List[str], default: float) -> float:
    """Devuelve el primer valor existente (como float) entre una lista de claves."""
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except Exception:
                pass
    return float(default)


def _get_bool(d: Dict[str, Any], key: str, default: bool) -> bool:
    v = d.get(key, default)
    return bool(v)


def _parse_holes(d: Dict[str, Any]) -> List[Tuple[float, float, float]]:
    """
    holes: [{ x_mm|x, z_mm|z, d_mm|d }]
    Devuelve lista de (x, z, d) en mm.
    """
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
    """
    Construye una placa (X-Z) con agujeros circulares recortados (Shapely) y extruida a 'thickness' en Y.
    Si Shapely no está disponible, hace fallback a placa sólida sin agujeros.
    """
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

        # extrude_polygon extruye a lo largo del eje Z → rotamos +90º en X para llevar Z→Y
        m = trimesh.creation.extrude_polygon(shape, height=thickness)
        m.apply_transform(R(math.pi / 2.0, [1, 0, 0]))  # Z → Y
        m.apply_transform(T([0.0, y_center, 0.0]))
        return m
    except Exception:
        # fallback: sin agujeros
        m = trimesh.creation.box(extents=[size_x, thickness, size_z])
        m.apply_transform(T([0.0, y_center, 0.0]))
        return m


def make_model(p: dict) -> trimesh.Trimesh:
    """
    Canal en U: X=length, Y=height, Z=width.
    Admite:
      - length_mm|length, height_mm|height, width_mm|width, thickness_mm|thickness
      - ventilated (bool)
      - holes?: [{ x_mm|x, z_mm|z, d_mm|d }]
    Los 'holes' se aplican en la PLACA BASE únicamente.
    """
    L   = _get(p, ["length_mm", "length"], 180.0)
    H   = _get(p, ["height_mm", "height"], 25.0)
    W   = _get(p, ["width_mm",  "width"],   60.0)
    TCK = _get(p, ["thickness_mm", "thickness"], 3.0)
    ventilated = _get_bool(p, "ventilated", True)
    holes = _parse_holes(p)

    # Base con agujeros (si vienen)
    base = _plate_with_holes_xz(
        size_x=L,
        size_z=W,
        thickness=TCK,
        holes=holes,
        y_center=(-H / 2.0 + TCK / 2.0),
    )

    # Paredes
    side1 = trimesh.creation.box(extents=[L, H, TCK])
    side1.apply_transform(T([0.0, 0.0, -W / 2.0 + TCK / 2.0]))

    side2 = trimesh.creation.box(extents=[L, H, TCK])
    side2.apply_transform(T([0.0, 0.0,  W / 2.0 - TCK / 2.0]))

    parts: List[trimesh.Trimesh] = [base, side1, side2]

    # Listones superficiales (decorativos; no CSG)
    if ventilated:
        n = max(3, int(L // 40))
        gap = L / (n + 1)
        rib_w = max(2.0, min(6.0, W * 0.08))
        for i in range(1, n + 1):
            rib = trimesh.creation.box(extents=[rib_w, TCK * 1.05, W - 2 * TCK])
            rib.apply_transform(T([-L / 2.0 + i * gap, -H / 2.0 + TCK / 2.0 + 0.01, 0.0]))
            parts.append(rib)

    return trimesh.util.concatenate(parts)
