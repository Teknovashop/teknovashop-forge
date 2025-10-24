from __future__ import annotations
import os
from typing import Iterable, Mapping, Optional, Literal, Tuple, List

import numpy as np
import trimesh

# Trimesh: texto vectorial 2D
try:
    from trimesh.path.creation import text as path_text
except Exception:  # compat
    path_text = None

from shapely.geometry import Polygon
from shapely.ops import unary_union, polygonize


Anchor = Literal["top", "bottom", "front", "back", "left", "right"]


def _concat(meshes: Iterable[trimesh.Trimesh]) -> trimesh.Trimesh:
    lst = [m for m in meshes if isinstance(m, trimesh.Trimesh) and len(m.vertices)]
    if not lst:
        return trimesh.Trimesh()
    return trimesh.util.concatenate(lst)


def _bounds_center_extents(mesh: trimesh.Trimesh) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mn, mx = mesh.bounds
    mn = np.asarray(mn, dtype=float)
    mx = np.asarray(mx, dtype=float)
    c = (mn + mx) * 0.5
    e = (mx - mn)
    return mn, mx, e, c


def _try_make_path(text: str, font: Optional[str]):
    """
    Crea un Path2D con varios intentos de fuente.
    """
    if not path_text or not text:
        return None

    candidates: List[Optional[str]] = []
    # 1) Lo que venga en la op
    if font:
        candidates.append(font)
    # 2) ENV
    candidates.append(os.getenv("FORGE_DEFAULT_FONT"))
    # 3) rutas típicas Linux
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    # 4) Por último, sin especificar fuente (default de PIL)
    candidates.append(None)

    for cand in candidates:
        try:
            # Algunos builds aceptan ruta en 'font', otros nombre
            if cand:
                p = path_text(text=text, font=cand)
            else:
                p = path_text(text=text)
            if p is None:
                continue
            if hasattr(p, "entities") and len(p.entities) == 0:
                continue
            return p
        except TypeError:
            # intentos alternativos de firma
            try:
                if cand:
                    p = path_text(text, font=cand)
                else:
                    p = path_text(text)
                if p and (not hasattr(p, "entities") or len(p.entities) > 0):
                    return p
            except Exception:
                pass
        except Exception:
            continue
    return None


def _polygons_from_path(path) -> List[Polygon]:
    """
    Extrae polígonos de un Path2D de trimesh de forma robusta.
    """
    polys: List[Polygon] = []

    for attr in ("polygons_full", "polygons_closed"):
        try:
            vals = list(getattr(path, attr, []) or [])
            if vals:
                polys.extend(vals)
        except Exception:
            pass

    # Fallbacks
    if not polys:
        try:
            if hasattr(path, "to_polygons"):
                vals = path.to_polygons()
                if vals:
                    polys.extend(vals)
        except Exception:
            pass

    if not polys:
        # Como último recurso, usar segmentos discretos y polygonize
        try:
            if hasattr(path, "discrete"):
                geoms = list(polygonize(path.discrete))
                for g in geoms:
                    if isinstance(g, Polygon):
                        polys.append(g)
        except Exception:
            pass

    # Sanea
    cleaned: List[Polygon] = []
    for poly in polys:
        try:
            if not poly.is_valid:
                poly = poly.buffer(0)
            if not poly.is_empty:
                cleaned.append(poly)
        except Exception:
            continue

    # Unión si hay muchos fragmentos minúsculos
    if len(cleaned) > 20:
        try:
            u = unary_union(cleaned)
            if isinstance(u, Polygon):
                return [u]
            # multipolygons -> lista
            return [g for g in getattr(u, "geoms", []) if isinstance(g, Polygon)]
        except Exception:
            pass

    return cleaned


def _make_text_solid(text: str, height: float, depth: float, font: Optional[str]) -> Optional[trimesh.Trimesh]:
    """
    Crea un sólido 3D del texto:
      - height (mm) ≈ alto de caja de glifos
      - depth (mm)  = extrusión
    """
    path = _try_make_path(text, font)
    if path is None:
        return None

    # Escala a 'height' (usamos la altura del bounds en Y)
    try:
        b = np.array(path.bounds)  # [[minx,miny],[maxx,maxy]]
        ext2 = b[1] - b[0]
        ref = float(ext2[1]) if ext2[1] != 0 else 1.0
        scale = float(height) / max(1e-6, ref)
        path = path.copy()
        path.apply_scale(scale)
        # Centrar en origen
        b2 = np.array(path.bounds)
        c2 = (b2[0] + b2[1]) * 0.5
        path.apply_translation([-float(c2[0]), -float(c2[1]), 0.0])
    except Exception:
        pass

    polys = _polygons_from_path(path)
    if not polys:
        return None

    solids: List[trimesh.Trimesh] = []
    for poly in polys:
        try:
            m = trimesh.creation.extrude_polygon(poly, height=depth)
            if isinstance(m, trimesh.Trimesh) and len(m.vertices):
                solids.append(m)
        except Exception:
            continue

    return _concat(solids)


def _axis_from_anchor(mesh: trimesh.Trimesh, anchor: Anchor) -> Tuple[np.ndarray, np.ndarray]:
    """
    Devuelve (origin, normal) para el anclaje solicitado.
    """
    mn, mx, _, c = _bounds_center_extents(mesh)
    if anchor == "top":
        origin = np.array([c[0], c[1], mx[2]])
        normal = np.array([0, 0, 1.0])
    elif anchor == "bottom":
        origin = np.array([c[0], c[1], mn[2]])
        normal = np.array([0, 0, -1.0])
    elif anchor == "front":
        origin = np.array([c[0], mx[1], c[2]])
        normal = np.array([0, 1.0, 0])
    elif anchor == "back":
        origin = np.array([c[0], mn[1], c[2]])
        normal = np.array([0, -1.0, 0])
    elif anchor == "right":
        origin = np.array([mx[0], c[1], c[2]])
        normal = np.array([1.0, 0, 0])
    else:  # "left"
        origin = np.array([mn[0], c[1], c[2]])
        normal = np.array([-1.0, 0, 0])
    return origin, normal


def _frame_from_normal(normal: np.ndarray) -> np.ndarray:
    """
    Matriz 4x4 que rota el plano XY para que su normal +Z pase a 'normal'.
    """
    n = np.asarray(normal, dtype=float)
    n /= max(1e-9, np.linalg.norm(n))
    R = trimesh.geometry.align_vectors(np.array([0.0, 0.0, 1.0]), n)
    if R is None:
        R = np.eye(4)
    return R


def _place_text_on_face(
    text_mesh: trimesh.Trimesh,
    base: trimesh.Trimesh,
    anchor: Anchor,
    pos: Tuple[float, float, float],
    depth: float,
    mode: str,
) -> trimesh.Trimesh:
    """
    Coloca y orienta el sólido de texto sobre la cara (anchor) del 'base'.
    'pos' son mm en el plano tangente (u,v).
    """
    origin, normal = _axis_from_anchor(base, anchor)
    R = _frame_from_normal(normal)

    # Ejes tangentes del marco (columnas 0 y 1 tras R)
    u = R[:3, 0]
    v = R[:3, 1]
    n = R[:3, 2]

    # Offset normal pequeño para evitar z-fighting
    n_clear = 0.05  # 0.05 mm
    offset_n = (depth * 0.5 + n_clear) * (1.0 if mode == "emboss" else -1.0)

    px, py, pz = float(pos[0]), float(pos[1]), float(pos[2] if len(pos) > 2 else 0.0)

    T = np.eye(4)
    T[:3, 3] = origin + u * px + v * py + n * (offset_n + pz)

    M = T @ R  # primero rota (XY→plano), luego traslada

    tm = text_mesh.copy()
    tm.apply_transform(M)
    return tm


def _boolean_union(a: trimesh.Trimesh, b: trimesh.Trimesh) -> Optional[trimesh.Trimesh]:
    try:
        from trimesh.boolean import union
        res = union([a, b], engine=None)
        if isinstance(res, trimesh.Trimesh) and len(res.vertices):
            return res
    except Exception:
        pass
    return None


def _boolean_diff(a: trimesh.Trimesh, b: trimesh.Trimesh) -> Optional[trimesh.Trimesh]:
    try:
        from trimesh.boolean import difference
        res = difference([a], [b], engine=None)
        if isinstance(res, trimesh.Trimesh) and len(res.vertices):
            return res
    except Exception:
        pass
    return None


def apply_text_ops(
    base_mesh: trimesh.Trimesh,
    ops: Iterable[Mapping],
) -> trimesh.Trimesh:
    """
    Aplica una lista de operaciones de texto.
      op = {
        "text": "VESA",
        "size": 8,              # altura texto (mm)
        "depth": 1.2,           # extrusión (mm)
        "mode": "engrave"|"emboss",
        "pos": [x_mm, y_mm, 0], # desplazamiento en el plano anclado
        "rot": [0,0,0],         # (no usado)
        "font": "/ruta/DejaVuSans.ttf" | "DejaVu Sans" | None,
        "anchor": "front"|"back"|"left"|"right"|"top"|"bottom"
      }
    """
    out = base_mesh.copy()

    for op in ops or []:
        text = (op.get("text") or "").strip()
        if not text:
            continue

        try:
            size = float(op.get("size", 8.0))
        except Exception:
            size = 8.0
        try:
            depth = float(op.get("depth", 1.2))
        except Exception:
            depth = 1.2

        mode = str(op.get("mode", "engrave")).lower().strip()
        font = op.get("font") or None
        pos = op.get("pos") or [0, 0, 0]
        try:
            px, py, pz = float(pos[0]), float(pos[1]), float(pos[2] if len(pos) > 2 else 0.0)
        except Exception:
            px, py, pz = 0.0, 0.0, 0.0
        anchor: Anchor = (op.get("anchor") or "front")  # default frente

        solid = _make_text_solid(text=text, height=size, depth=depth, font=font)
        if not isinstance(solid, trimesh.Trimesh) or len(solid.vertices) == 0:
            # si no pudimos generar texto, no rompemos la pieza
            continue

        placed = _place_text_on_face(
            text_mesh=solid, base=out, anchor=anchor, pos=(px, py, pz), depth=depth, mode=mode
        )

        if mode == "emboss":
            merged = _boolean_union(out, placed)
            out = merged if merged is not None else _concat([out, placed])
        else:
            carved = _boolean_diff(out, placed)
            if carved is not None:
                out = carved
            else:
                # Fallback: si no hay motor booleano, al menos deja el relieve
                out = _concat([out, placed])

    return out
