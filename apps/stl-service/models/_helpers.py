from __future__ import annotations
from typing import Iterable, Tuple, List, Any, Optional, Sequence

import numpy as np
import trimesh

# Opcional (para redondeos 2D -> extrusión)
try:
    from shapely.geometry import box as shp_box, Polygon
    from shapely.ops import unary_union
    _HAS_SHAPELY = True
except Exception:
    _HAS_SHAPELY = False


# -------------------- Num & parsing --------------------

def num(x: Any, default: Optional[float] = None) -> Optional[float]:
    if x is None:
        return default
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return default


def parse_holes(holes_in: Iterable[Any]) -> List[Tuple[float, float, float]]:
    """
    Normaliza agujeros a [(x, y, d_mm)].
    - Acepta dicts con x,y,diam_mm/diameter/d/diameter_mm
    - Acepta triples [x,y,d]
    Coordenadas se asumen en el sistema de la pieza (habitualmente centrado).
    """
    out: List[Tuple[float, float, float]] = []
    for h in holes_in or []:
        if isinstance(h, dict):
            x = num(h.get("x"), 0.0)
            y = num(h.get("y"), 0.0)
            d = num(h.get("diam_mm") or h.get("diameter") or h.get("diameter_mm") or h.get("d"), 0.0)
            if x is not None and y is not None and d and d > 0:
                out.append((float(x), float(y), float(d)))
        elif isinstance(h, (list, tuple)) and len(h) >= 3:
            xv = num(h[0]); yv = num(h[1]); dv = num(h[2])
            if xv is not None and yv is not None and dv and dv > 0:
                out.append((float(xv), float(yv), float(dv)))
    return out


# -------------------- Primitivas --------------------

def box(extents: Sequence[float]) -> trimesh.Trimesh:
    """
    Caja centrada en el origen con (L, W, T) = (x, y, z).
    """
    return trimesh.creation.box(extents=tuple(float(v) for v in extents))


def cylinder(radius: float, height: float, sections: int = 64) -> trimesh.Trimesh:
    """
    Cilindro centrado en el origen y alineado con Z.
    """
    return trimesh.creation.cylinder(radius=float(radius), height=float(height), sections=int(sections))


# -------------------- Booleanos robustos --------------------

def _trimesh_union(meshes: List[trimesh.Trimesh]) -> Optional[trimesh.Trimesh]:
    try:
        from trimesh.boolean import union
        out = union(meshes, engine=None)
        if isinstance(out, trimesh.Trimesh) and len(out.vertices):
            return out
    except Exception:
        pass
    return None


def _trimesh_diff(a: trimesh.Trimesh, b: trimesh.Trimesh) -> Optional[trimesh.Trimesh]:
    try:
        from trimesh.boolean import difference
        out = difference([a], [b], engine=None)
        if isinstance(out, trimesh.Trimesh) and len(out.vertices):
            return out
    except Exception:
        pass
    return None


def _trimesh_intersection(meshes: List[trimesh.Trimesh]) -> Optional[trimesh.Trimesh]:
    try:
        from trimesh.boolean import intersection
        out = intersection(meshes, engine=None)
        if isinstance(out, trimesh.Trimesh) and len(out.vertices):
            return out
    except Exception:
        pass
    return None


def union_all(meshes: Iterable[trimesh.Trimesh]) -> trimesh.Trimesh:
    """
    Unión booleana con fallback seguro (concat) si no hay motor.
    """
    lst = [m for m in meshes if isinstance(m, trimesh.Trimesh) and len(m.vertices)]
    if not lst:
        return trimesh.Trimesh()
    out = _trimesh_union(lst)
    return out if out is not None else trimesh.util.concatenate(lst)


def difference(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Diferencia booleana con fallback (devuelve 'a' si no hay motor).
    """
    out = _trimesh_diff(a, b)
    return out if out is not None else a


def intersection_all(meshes: Iterable[trimesh.Trimesh]) -> trimesh.Trimesh:
    """
    Intersección booleana con fallback (devuelve la primera si no hay motor).
    """
    lst = [m for m in meshes if isinstance(m, trimesh.Trimesh) and len(m.vertices)]
    if len(lst) < 2:
        return lst[0] if lst else trimesh.Trimesh()
    out = _trimesh_intersection(lst)
    return out if out is not None else lst[0]


# -------------------- Utilidades de calidad --------------------

def ensure_watertight(m: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Intenta mejorar la imprimibilidad: fusiona vértices muy cercanos y rellena agujeros menores.
    No rompe si ya es watertight.
    """
    if not isinstance(m, trimesh.Trimesh):
        return m
    mm = m.copy()
    try:
        mm.merge_vertices(epsilon=1e-6)
    except Exception:
        pass
    try:
        if not mm.is_watertight:
            mm.fill_holes()
    except Exception:
        pass
    return mm


# -------------------- Placas “reales” --------------------

def _rounded_rect_2d(L: float, W: float, r: float) -> Optional[Polygon]:
    """
    Devuelve un Polígono Shapely rectangular con esquinas redondeadas (radio r).
    Centro en (0,0). Requiere Shapely.
    """
    if not _HAS_SHAPELY:
        return None
    L = float(L); W = float(W); r = max(0.0, float(r))
    rmax = max(0.0, min(L, W) * 0.5 - 1e-6)
    r = min(r, rmax)
    base = shp_box(-L * 0.5 + r, -W * 0.5 + r, L * 0.5 - r, W * 0.5 - r)
    if r > 0:
        poly = base.buffer(r, join_style=2, cap_style=2)  # join_style=2 -> round
    else:
        poly = base
    return poly


def rounded_plate(L: float, W: float, T: float, r: float) -> trimesh.Trimesh:
    """
    Placa sólida con esquinas redondeadas (si Shapely disponible).
    Si no hay Shapely, cae en caja simple.
    """
    poly = _rounded_rect_2d(L, W, r) if _HAS_SHAPELY else None
    if _HAS_SHAPELY and isinstance(poly, Polygon):
        try:
            slab = trimesh.creation.extrude_polygon(poly, height=float(T))
            # Por coherencia: centrar en Z (igual que box extents)
            return slab
        except Exception:
            pass
    return box((L, W, T))


def plate_with_holes(
    L: float,
    W: float,
    T: float,
    holes: List[Tuple[float, float, float]],
    corner_r: float = 0.0,
    hole_sections: int = 64
) -> trimesh.Trimesh:
    """
    Placa con esquinas redondeadas opcionales y taladros pasantes.
    - L, W, T en mm
    - holes: lista [(x, y, d_mm)]
    - corner_r: radio de redondeo en esquinas (0 = sin redondeo)
    """
    base = rounded_plate(L, W, T, corner_r) if corner_r > 0 else box((L, W, T))
    if not holes:
        return ensure_watertight(base)

    cutters = []
    # hacemos los taladros más altos que el espesor para asegurar perforación
    h = float(T) * 1.6
    z0 = 0.0  # la placa está centrada; con h > T nos aseguramos atraviesa
    for (x, y, d) in holes:
        r = float(d) * 0.5
        c = cylinder(radius=r, height=h, sections=hole_sections)
        c.apply_translation((float(x), float(y), z0))
        cutters.append(c)

    cutter = union_all(cutters) if len(cutters) > 1 else (cutters[0] if cutters else None)
    if cutter is None:
        return ensure_watertight(base)

    out = difference(base, cutter)
    return ensure_watertight(out)
