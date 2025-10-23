"""
Aplicador de operaciones de texto (engrave / emboss) para FORGE.

Op schema (dict):
{
  "text": "VESA",
  "size": 6.0,            # alto del texto (mm aprox.)
  "depth": 1.2,           # extrusión (mm)
  "mode": "engrave",      # "engrave" | "emboss"
  "pos": [x, y, z],       # mm; si falta, se auto-coloca en la cara superior (centro XY)
  "rot": [rx, ry, rz],    # grados
  "font": "DejaVuSans"    # opcional
}
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import trimesh


# ------------------------------ helpers ------------------------------

def _engine() -> Optional[str]:
    # Si OpenSCAD está disponible, úsalo (más robusto en booleanas).
    try:
        if trimesh.interfaces.scad.exists:
            return "scad"
    except Exception:
        pass
    return None


def _f(x: Any, fb: float) -> float:
    try:
        return float(x)
    except Exception:
        try:
            return float(str(x).replace(",", "."))
        except Exception:
            return fb


def _pose(pos: Iterable[float], rot_deg: Iterable[float]) -> np.ndarray:
    """Matriz 4x4 con rotaciones XYZ (grados) y traslación."""
    px, py, pz = list(pos or [0, 0, 0])[:3]
    rx, ry, rz = list(rot_deg or [0, 0, 0])[:3]
    rx, ry, rz = map(lambda d: math.radians(_f(d, 0.0)), (rx, ry, rz))

    M = np.eye(4)
    M = trimesh.transformations.rotation_matrix(rz, [0, 0, 1]) @ M
    M = trimesh.transformations.rotation_matrix(ry, [0, 1, 0]) @ M
    M = trimesh.transformations.rotation_matrix(rx, [1, 0, 0]) @ M
    M[:3, 3] = [float(px), float(py), float(pz)]
    return M


def _center_bottom_at_origin(mesh: trimesh.Trimesh) -> None:
    """Centra en XY y apoya la base del texto en z=0 (para un posicionamiento intuitivo)."""
    try:
        b = mesh.bounds
        cx = 0.5 * (b[0, 0] + b[1, 0])
        cy = 0.5 * (b[0, 1] + b[1, 1])
        z0 = float(b[0, 2])
        mesh.apply_translation((-cx, -cy, -z0))
    except Exception:
        pass


def _make_text_mesh(text: str, size_mm: float, depth_mm: float, font: Optional[str]) -> Optional[trimesh.Trimesh]:
    """Crea una malla 3D del texto extruido. Devuelve None si no es posible."""
    if not text or not str(text).strip():
        return None

    try:
        from trimesh.path.creation import text as text_path  # Path2D
    except Exception:
        return None

    # Construye el path 2D
    try:
        try:
            path = text_path(text=str(text), font=font)
        except TypeError:
            path = text_path(str(text))
    except Exception:
        return None

    # Polígonos del path
    polygons: List[Any] = []
    try:
        polys_full = getattr(path, "polygons_full", None)
        if polys_full is not None:
            polygons = polys_full if isinstance(polys_full, (list, tuple)) else [polys_full]
        else:
            polygons = path.to_polygons()
    except Exception:
        try:
            polygons = path.to_polygons()
        except Exception:
            polygons = []

    if not polygons:
        return None

    # Escala para que el alto ≈ size_mm
    try:
        pb = path.bounds  # [[minx,miny],[maxx,maxy]]
        ph = float(pb[1][1] - pb[0][1]) if pb is not None else 1.0
        if ph <= 0:
            ph = 1.0
        scale = float(size_mm) / ph
    except Exception:
        scale = 1.0

    meshes: List[trimesh.Trimesh] = []

    # Mejor con shapely (maneja agujeros)
    try:
        import shapely.geometry as sgeom  # noqa
        from shapely.geometry import Polygon, MultiPolygon  # type: ignore
        has_shapely = True
    except Exception:
        has_shapely = False
        Polygon = MultiPolygon = tuple()  # type: ignore

    for poly in polygons:
        try:
            if has_shapely and isinstance(poly, MultiPolygon):
                for g in poly.geoms:
                    m = trimesh.creation.extrude_polygon(g, height=float(depth_mm))
                    meshes.append(m)
                continue
            if has_shapely and isinstance(poly, Polygon):
                m = trimesh.creation.extrude_polygon(poly, height=float(depth_mm))
                meshes.append(m)
                continue

            arr = np.asanyarray(poly)
            if arr.ndim == 2 and arr.shape[1] >= 2:
                m = trimesh.creation.extrude_polygon(arr[:, :2], height=float(depth_mm))
                meshes.append(m)
        except Exception:
            continue

    if not meshes:
        return None

    text_mesh = trimesh.util.concatenate(meshes)

    # Aplicar escala y centrar en origen con base en z=0
    try:
        S = np.eye(4)
        S[:3, :3] *= float(scale)
        text_mesh.apply_transform(S)
    except Exception:
        pass

    _center_bottom_at_origin(text_mesh)
    return text_mesh


def _boolean(base: trimesh.Trimesh, tool: trimesh.Trimesh, mode: str) -> trimesh.Trimesh:
    """Aplica booleana; si falla, devuelve la base sin cambios."""
    eng = _engine()
    mode = (mode or "engrave").strip().lower()
    try:
        if mode == "emboss":
            res = base.union(tool, engine=eng)
        else:
            res = base.difference(tool, engine=eng)
        if isinstance(res, trimesh.Trimesh):
            return res
        if isinstance(res, (list, tuple)) and res:
            return trimesh.util.concatenate([g for g in res if isinstance(g, trimesh.Trimesh)])
    except Exception:
        pass
    return base


# ----------------------------- API pública -----------------------------

def apply_text_ops(mesh: Any, ops: Optional[Iterable[Dict[str, Any]]]) -> Any:
    """
    Aplica una lista de operaciones de texto sobre 'mesh' (Trimesh o compatible).
    Si una op no especifica 'pos', se auto-coloca en la **cara superior** (z_max), centrado en XY.
    """
    if ops is None or not ops:
        return mesh

    base = mesh.copy() if isinstance(mesh, trimesh.Trimesh) else mesh

    # Bounds del modelo para auto-colocar
    try:
        bmin, bmax = base.bounds  # type: ignore
        cx = 0.5 * (bmin[0] + bmax[0])
        cy = 0.5 * (bmin[1] + bmax[1])
        z_top = float(bmax[2])
        width_xy = max(float(bmax[0] - bmin[0]), 1e-6)
        height_xy = max(float(bmax[1] - bmin[1]), 1e-6)
        ref_size = 0.25 * min(width_xy, height_xy)  # tamaño “razonable” por defecto
    except Exception:
        cx = cy = z_top = 0.0
        ref_size = 12.0

    EPS = 0.2  # pequeño solape para booleanas robustas

    for op in ops:
        try:
            text = str(op.get("text", "")).strip()
            if not text:
                continue

            size = _f(op.get("size"), ref_size)
            depth = max(0.1, _f(op.get("depth"), 1.2))
            font = op.get("font")
            mode = (op.get("mode") or "engrave").lower()

            # Construir texto
            tmesh = _make_text_mesh(text, size, depth, font)
            if tmesh is None:
                continue

            # Pos auto si no hay pos explícita
            pos = op.get("pos")
            if not pos:
                if mode == "emboss":
                    # Ligeramente embebido para que la unión conecte
                    z0 = z_top - 0.1 * depth + EPS
                else:
                    # Grabado: metemos la mayor parte dentro del sólido
                    z0 = z_top - 0.6 * depth
                pos = [cx, cy, z0]

            rot = op.get("rot") or [0, 0, 0]

            # Colocar el texto (ya está centrado en XY y apoyado en z=0)
            M = _pose(pos, rot)
            tmesh.apply_transform(M)

            # Aplicar booleana
            if isinstance(base, trimesh.Trimesh):
                base = _boolean(base, tmesh, mode)
            else:
                try:
                    base = trimesh.util.concatenate(base)  # type: ignore
                    base = _boolean(base, tmesh, mode)
                except Exception:
                    pass
        except Exception:
            # no romper el pipeline por un op
            continue

    return base


__all__ = ["apply_text_ops"]
