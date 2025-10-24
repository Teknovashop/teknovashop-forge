from __future__ import annotations
import os
from pathlib import Path
import math
from typing import Iterable, Mapping, Optional, Literal, Tuple, List, Union

import numpy as np
import trimesh

# Trimesh: texto vectorial 2D
try:
    from trimesh.path.creation import text as path_text
except Exception:  # compat viejo
    path_text = None

from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

Anchor = Literal["top", "bottom", "front", "back", "left", "right"]

DEBUG = os.getenv("DEBUG_FORGE_TEXT", "0") == "1"


def _log(*a):
    if DEBUG:
        print("[forge:text]", *a)


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


# ------------------------ Resolución de fuente ------------------------ #

def _resolve_font(user_font: Optional[str]) -> Optional[str]:
    """
    Devuelve una ruta absoluta a una fuente TTF válida:
    1) La que venga en la op
    2) FORGE_DEFAULT_FONT (env)
    3) Fuente embebida en el repo (apps/stl-service/models/assets/fonts/…)
    4) Rutas típicas del sistema
    """
    candidates: List[Union[str, Path]] = []

    if user_font:
        candidates.append(user_font)

    env_font = os.getenv("FORGE_DEFAULT_FONT", "").strip()
    if env_font:
        candidates.append(env_font)

    here = Path(__file__).resolve().parent
    candidates += [
        here / "assets" / "fonts" / "DejaVuSans.ttf",
        here / "assets" / "fonts" / "NotoSans-Regular.ttf",
    ]

    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/local/share/fonts/DejaVuSans.ttf",
    ]

    # Si nos pasaron solo el nombre (sin ruta), busca en carpetas conocidas
    extra_dirs = [
        here / "assets" / "fonts",
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
    ]

    for c in candidates:
        if not c:
            continue
        p = Path(str(c))
        if p.is_file():
            _log("font:", p)
            return str(p)
        if not p.is_absolute():
            for d in extra_dirs:
                pp = d / p
                if pp.is_file():
                    _log("font:", pp)
                    return str(pp)

    _log("font: NONE found")
    return None


# ------------------------ Texto -> sólido ------------------------ #

def _make_text_solid(text: str, height: float, depth: float, font_spec: Optional[str]) -> Optional[trimesh.Trimesh]:
    """
    Crea un sólido 3D del texto:
      - height (mm) ≈ altura de mayúsculas
      - depth  (mm) = extrusión
    """
    if not text or not path_text:
        _log("no text() available in trimesh" if not path_text else "empty text")
        return None

    font_path = _resolve_font(font_spec)

    # Path 2D de glifos (en el plano XY)
    try:
        path = path_text(text=text, font=font_path)  # Path2D
    except Exception as e:
        _log("path_text error:", e)
        return None

    if path is None or (hasattr(path, "entities") and len(path.entities) == 0):
        _log("empty path from text()")
        return None

    # Escalar a 'height'
    try:
        b = np.array(path.bounds)  # [[minx,miny], [maxx,maxy]]
        ext2 = b[1] - b[0]
        src_h = float(ext2[1]) if float(ext2[1]) > 0 else 1.0
    except Exception:
        src_h = 1.0
    scale = float(height) / src_h
    try:
        path = path.copy()
        path.apply_scale(scale)
    except Exception:
        pass

    # Centrar en el origen
    try:
        b2 = np.array(path.bounds)
        c2 = (b2[0] + b2[1]) * 0.5
        path.apply_translation([-c2[0], -c2[1], 0])
    except Exception:
        pass

    # Polígonos (con huecos)
    polys: List[Polygon] = []
    try:
        if hasattr(path, "polygons_full"):
            polys = list(path.polygons_full)  # shapely Polygons
        elif hasattr(path, "polygons_closed"):
            polys = list(path.polygons_closed)
        elif hasattr(path, "to_polygons"):
            # a veces devuelve listas de puntos; conviértelas a Polygons
            poly_lists = path.to_polygons()
            for ring in poly_lists or []:
                try:
                    polys.append(Polygon(ring))
                except Exception:
                    continue
    except Exception as e:
        _log("polygons extract error:", e)

    if not polys:
        _log("no polygons from text()")
        return None

    # Une y garantiza geometrías válidas (MultiPolygon o Polygon)
    try:
        geom = unary_union(polys)
    except Exception:
        geom = polys

    if isinstance(geom, (Polygon, MultiPolygon)):
        geom_list = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    else:
        # ya es lista de Polygons
        geom_list = [g for g in (geom or []) if isinstance(g, Polygon)]

    solids: List[trimesh.Trimesh] = []
    for poly in geom_list:
        try:
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty:
                continue
            m = trimesh.creation.extrude_polygon(poly, height=float(depth))
            solids.append(m)
        except Exception as e:
            _log("extrude_polygon error:", e)
            continue

    if not solids:
        _log("no solids after extrude")
        return None

    return _concat(solids)


# ------------------------ Posicionamiento ------------------------ #

def _axis_from_anchor(mesh: trimesh.Trimesh, anchor: Anchor) -> Tuple[np.ndarray, np.ndarray]:
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
    else:  # left
        origin = np.array([mn[0], c[1], c[2]])
        normal = np.array([-1.0, 0, 0])
    return origin, normal


def _frame_from_normal(normal: np.ndarray) -> np.ndarray:
    n = np.asarray(normal, dtype=float)
    n /= max(1e-9, np.linalg.norm(n))
    R = trimesh.geometry.align_vectors(np.array([0, 0, 1.0]), n)
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
    origin, normal = _axis_from_anchor(base, anchor)
    R = _frame_from_normal(normal)

    # Ejes tangentes del plano
    u = R[:3, 0]
    v = R[:3, 1]
    n = R[:3, 2]

    # Evitar z-fighting
    n_clear = 0.05  # mm
    offset_n = (float(depth) * 0.5 + n_clear) * (1.0 if mode == "emboss" else -1.0)

    T = np.eye(4)
    T[:3, 3] = origin + u * float(pos[0]) + v * float(pos[1]) + n * float(offset_n)

    M = T @ R

    tm = text_mesh.copy()
    tm.apply_transform(M)
    return tm


# ------------------------ Booleanos ------------------------ #

def _boolean_union(a: trimesh.Trimesh, b: trimesh.Trimesh) -> Optional[trimesh.Trimesh]:
    try:
        from trimesh.boolean import union
        res = union([a, b], engine=None)
        if isinstance(res, trimesh.Trimesh) and len(res.vertices):
            return res
    except Exception as e:
        _log("union fail:", e)
    return None


def _boolean_diff(a: trimesh.Trimesh, b: trimesh.Trimesh) -> Optional[trimesh.Trimesh]:
    try:
        from trimesh.boolean import difference
        res = difference([a], [b], engine=None)
        if isinstance(res, trimesh.Trimesh) and len(res.vertices):
            return res
    except Exception as e:
        _log("diff fail:", e)
    return None


# ------------------------ API principal ------------------------ #

def apply_text_ops(
    base_mesh: trimesh.Trimesh,
    ops: Iterable[Mapping],
) -> trimesh.Trimesh:
    """
    Aplica una lista de operaciones de texto.
      op = {
        "text": "VESA",
        "size": 8,               # altura del texto (mm)
        "depth": 1.2,            # extrusión (mm)
        "mode": "engrave"|"emboss",
        "pos": [x_mm, y_mm, 0],  # desplazamiento sobre el plano anclado
        "rot": [0,0,0],          # (no usado: anchor decide la orientación)
        "font": "/ruta/a.ttf" | None,
        "anchor": "front"|"back"|"left"|"right"|"top"|"bottom"
      }
    """
    out = base_mesh.copy()

    for op in ops or []:
        text = (op.get("text") or "").strip()
        if not text:
            continue

        size = float(op.get("size", 6.0))
        depth = float(op.get("depth", 1.2))
        mode = str(op.get("mode", "engrave")).lower().strip()
        font_spec = op.get("font") or None
        pos = op.get("pos") or [0, 0, 0]
        try:
            px, py, pz = float(pos[0]), float(pos[1]), float(pos[2] if len(pos) > 2 else 0.0)
        except Exception:
            px, py, pz = 0.0, 0.0, 0.0
        anchor: Anchor = op.get("anchor") or "front"

        solid = _make_text_solid(text=text, height=size, depth=depth, font_spec=font_spec)
        if not isinstance(solid, trimesh.Trimesh) or len(solid.vertices) == 0:
            _log("skip: no solid for text")
            continue

        placed = _place_text_on_face(
            text_mesh=solid, base=out, anchor=anchor, pos=(px, py, pz), depth=depth, mode=mode
        )

        if mode == "emboss":
            merged = _boolean_union(out, placed)
            out = merged if merged is not None else _concat([out, placed])
        else:
            carved = _boolean_diff(out, placed)
            out = carved if carved is not None else _concat([out, placed])

    return out
