"""
Aplicador de operaciones de texto (engrave / emboss) para FORGE.

Cada operación es un dict con claves:
{
  "text": "VESA",
  "size": 6.0,            # alto del texto (mm aprox.)
  "depth": 1.2,           # extrusión (mm)
  "mode": "engrave",      # "engrave" | "emboss"
  "pos": [x, y, z],       # mm, centro XY del texto; z = base del texto
  "rot": [rx, ry, rz],    # grados, ejes X/Y/Z
  "font": "DejaVuSans"    # opcional (siempre "best effort")
}

Uso (el backend ya lo llama si existe):
   mesh_out = apply_text_ops(mesh_in, ops)
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import trimesh

# ------------------------------ helpers ------------------------------

def _engine() -> Optional[str]:
    # Si OpenSCAD está disponible, úsalo (robusto con booleanas).
    try:
        if trimesh.interfaces.scad.exists:
            return "scad"
    except Exception:
        pass
    return None  # deja que trimesh elija o haga fallback


def _safe_float(x: Any, fb: float) -> float:
    try:
        return float(x)
    except Exception:
        try:
            return float(str(x).replace(",", "."))
        except Exception:
            return fb


def _pose_matrix(pos: Iterable[float], rot_deg: Iterable[float]) -> np.ndarray:
    """
    Crea una matriz 4x4 con rotaciones (XYZ, grados) y traslación.
    """
    px, py, pz = list(pos or [0, 0, 0])[:3]
    rx, ry, rz = list(rot_deg or [0, 0, 0])[:3]
    rx, ry, rz = map(lambda d: math.radians(_safe_float(d, 0.0)), (rx, ry, rz))

    M = np.eye(4)
    # Z
    M = trimesh.transformations.rotation_matrix(rz, [0, 0, 1]) @ M
    # Y
    M = trimesh.transformations.rotation_matrix(ry, [0, 1, 0]) @ M
    # X
    M = trimesh.transformations.rotation_matrix(rx, [1, 0, 0]) @ M
    # T
    M[:3, 3] = [float(px), float(py), float(pz)]
    return M


def _center_bottom_at_origin(mesh: trimesh.Trimesh) -> None:
    """
    Reposiciona la malla para que:
      - el centro en XY quede en (0,0)
      - la base (mínimo Z) quede en 0
    """
    try:
        b = mesh.bounds
        cx = 0.5 * (b[0, 0] + b[1, 0])
        cy = 0.5 * (b[0, 1] + b[1, 1])
        z0 = float(b[0, 2])
        mesh.apply_translation((-cx, -cy, -z0))
    except Exception:
        pass


def _make_text_mesh(
    text: str,
    size_mm: float = 6.0,
    depth_mm: float = 1.2,
    font: Optional[str] = None,
) -> Optional[trimesh.Trimesh]:
    """
    Crea una malla 3D del texto extruido. Devuelve None si no es posible.
    """
    if not text or not str(text).strip():
        return None

    # 1) Crear el path 2D del texto
    try:
        from trimesh.path.creation import text as text_path  # Path2D
    except Exception:
        return None

    try:
        # Nota: La API de trimesh puede variar; probamos distintas firmas.
        try:
            path = text_path(text=str(text), font=font)
        except TypeError:
            path = text_path(str(text))
    except Exception:
        return None

    # 2) Obtener polígonos del path
    polygons: List[Any] = []
    try:
        # Preferimos polygons_full (con agujeros si hay shapely)
        polys_full = getattr(path, "polygons_full", None)
        if polys_full is not None:
            # Puede ser lista de arrays o un objeto shapely
            if isinstance(polys_full, (list, tuple)):
                polygons = list(polys_full)
            else:
                # shapely geometry (MultiPolygon/Polygon)
                polygons = [polys_full]
        else:
            polygons = path.to_polygons()
    except Exception:
        try:
            polygons = path.to_polygons()
        except Exception:
            polygons = []

    if not polygons:
        return None

    # 3) Normalizar la escala "aprox" para que 'size_mm' sea el alto
    #    medimos bbox del path y escalamos a size_mm
    try:
        pb = path.bounds  # [[minx,miny],[maxx,maxy]]
        ph = float(pb[1][1] - pb[0][1]) if pb is not None else 1.0
        if ph <= 0:
            ph = 1.0
        scale = float(size_mm) / ph
    except Exception:
        scale = 1.0

    # 4) Extruir cada polígono
    meshes: List[trimesh.Trimesh] = []

    # Si hay shapely, es más robusto para agujeros
    try:
        import shapely.geometry as sgeom  # noqa: F401
        has_shapely = True
    except Exception:
        has_shapely = False

    for poly in polygons:
        try:
            if has_shapely:
                # poly puede ser shapely Polygon/MultiPolygon
                from shapely.geometry import Polygon, MultiPolygon  # type: ignore

                if isinstance(poly, MultiPolygon):
                    for g in poly.geoms:
                        m = trimesh.creation.extrude_polygon(g, height=float(depth_mm))
                        meshes.append(m)
                    continue
                if isinstance(poly, Polygon):
                    m = trimesh.creation.extrude_polygon(poly, height=float(depth_mm))
                    meshes.append(m)
                    continue

            # Fallback: listas de N×2 (sin agujeros)
            arr = np.asanyarray(poly)
            if arr.ndim == 2 and arr.shape[1] >= 2:
                m = trimesh.creation.extrude_polygon(arr[:, :2], height=float(depth_mm))
                meshes.append(m)
        except Exception:
            continue

    if not meshes:
        return None

    text_mesh = trimesh.util.concatenate(meshes)
    # aplicar escala y centrar
    try:
        S = np.eye(4)
        S[:3, :3] *= float(scale)
        text_mesh.apply_transform(S)
    except Exception:
        pass

    _center_bottom_at_origin(text_mesh)
    return text_mesh


def _boolean_apply(
    base: trimesh.Trimesh,
    tool: trimesh.Trimesh,
    mode: str = "engrave",
) -> trimesh.Trimesh:
    """
    Aplica la operación booleana y devuelve una malla.
    Si falla, devuelve la base sin cambios.
    """
    mode = (mode or "engrave").strip().lower()
    eng = _engine()
    try:
        if mode == "emboss":
            result = base.union(tool, engine=eng)
        else:
            result = base.difference(tool, engine=eng)
        if isinstance(result, trimesh.Trimesh):
            return result
        if isinstance(result, (list, tuple)) and result:
            return trimesh.util.concatenate([g for g in result if isinstance(g, trimesh.Trimesh)])
    except Exception:
        pass
    return base

# ----------------------------- API pública -----------------------------

def apply_text_ops(mesh: Any, ops: Optional[Iterable[Dict[str, Any]]]) -> Any:
    """
    Aplica una lista de operaciones de texto sobre 'mesh' (Trimesh o compatible).
    Devuelve una nueva malla (o la original si no se pudo aplicar).
    """
    if ops is None:
        return mesh
    # clonamos si es Trimesh
    base = mesh.copy() if isinstance(mesh, trimesh.Trimesh) else mesh

    for op in ops:
        try:
            text = str(op.get("text", "")).strip()
            if not text:
                continue

            size = _safe_float(op.get("size"), 6.0)
            depth = _safe_float(op.get("depth"), 1.2)
            font = op.get("font")
            pos = op.get("pos") or [0, 0, 0]
            rot = op.get("rot") or [0, 0, 0]
            mode = (op.get("mode") or "engrave").lower()

            tmesh = _make_text_mesh(text=text, size_mm=size, depth_mm=depth, font=font)
            if tmesh is None:
                # si no pudimos construir el texto, seguimos con el resto
                continue

            # Colocar: por convenio, pos = centro XY y base en Z
            # (ya hemos centrado en origen y base en z=0)
            M = _pose_matrix(pos, rot)
            tmesh.apply_transform(M)

            # Booleana
            if isinstance(base, trimesh.Trimesh):
                base = _boolean_apply(base, tmesh, mode=mode)
            else:
                # Si base no es Trimesh (p.ej. lista), intentamos concatenar primero
                try:
                    base = trimesh.util.concatenate(base)  # type: ignore
                    base = _boolean_apply(base, tmesh, mode=mode)
                except Exception:
                    pass
        except Exception:
            # no interrumpir por un op concreto
            continue

    return base


__all__ = ["apply_text_ops"]
