# apps/stl-service/models/text_ops.py
from __future__ import annotations
import math
from typing import Iterable, Mapping, Optional, Literal, Tuple, List

import numpy as np
import trimesh

# Trimesh: texto vectorial 2D
try:
    from trimesh.path.creation import text as path_text
except Exception:  # compat viejo
    path_text = None

from shapely.geometry import Polygon  # asegúrate de tener shapely instalado
from shapely.ops import unary_union


Anchor = Literal["top", "bottom", "front", "back", "left", "right"]


def _concat(meshes: Iterable[trimesh.Trimesh]) -> trimesh.Trimesh:
    lst = [m for m in meshes if isinstance(m, trimesh.Trimesh) and len(m.vertices)]
    if not lst:
        return trimesh.Trimesh()
    return trimesh.util.concatenate(lst)


def _bounds_center_extents(mesh: trimesh.Trimesh) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mn, mx = mesh.bounds
    mn = np.asarray(mn, dtype=float)
    mx = np.asarray(mx, dtype=float)
    c = (mn + mx) * 0.5
    e = (mx - mn)
    return mn, mx, e, c


def _make_text_solid(text: str, height: float, depth: float, font: Optional[str]) -> Optional[trimesh.Trimesh]:
    """
    Crea un sólido 3D del texto:
      - altura (mm) ≈ tamaño del bloque de mayúsculas
      - profundidad = extrusión
    """
    if not text or not path_text:
        return None

    # Path 2D de glifos (en el plano XY)
    path = path_text(text=text, font=font)  # Path2D/Path3D
    if path is None or (hasattr(path, "entities") and len(path.entities) == 0):
        return None

    # Escalar a 'height'
    b = np.array(path.bounds)  # [[minx,miny],[maxx,maxy]]
    ext2 = b[1] - b[0]
    scale = (height / max(1e-6, ext2[1]))  # normalizamos por la altura del texto
    path = path.copy()
    path.apply_scale(scale)

    # Centrar en el origen (para anclar fácil)
    b2 = np.array(path.bounds)
    c2 = (b2[0] + b2[1]) * 0.5
    path.apply_translation([-c2[0], -c2[1], 0])

    # Polígonos con huecos
    polys: List[Polygon] = list(getattr(path, "polygons_full", []))
    if not polys:
        # último intento: fusionar segmentos
        try:
            polys = [unary_union(polys)]
        except Exception:
            return None

    solids: List[trimesh.Trimesh] = []
    for poly in polys:
        try:
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty:
                continue
            m = trimesh.creation.extrude_polygon(poly, height=depth)
            solids.append(m)
        except Exception:
            continue

    return _concat(solids)


def _axis_from_anchor(mesh: trimesh.Trimesh, anchor: Anchor) -> Tuple[np.ndarray, np.ndarray]:
    """
    Devuelve (origin, normal) para el anclaje solicitado, en coords del mesh.
    Convención:
      X: izquierda(-)/derecha(+)
      Y: atrás(-)/delante(+)
      Z: abajo(-)/arriba(+)
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
    # rotar Z -> n
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
    """
    Coloca y orienta el sólido de texto sobre la cara (anchor) del 'base'.
    'pos' son mm en el plano tangente (x=lado, y=arriba dentro del plano de texto).
    Para evitar z-fighting, aplicamos un pequeño offset normal.
    """
    origin, normal = _axis_from_anchor(base, anchor)
    R = _frame_from_normal(normal)

    # Ejes tangentes del marco (columnas 0 y 1 tras R)
    u = R[:3, 0]
    v = R[:3, 1]
    n = R[:3, 2]

    # Offset normal: si es relieve, lo sacamos; si es grabado, lo metemos
    n_clear = 0.05  # 0.05 mm para evitar coplanar
    offset_n = (depth * 0.5 + n_clear) * (1.0 if mode == "emboss" else -1.0)

    T = np.eye(4)
    # colócalo en el origen del anclaje
    T[:3, 3] = origin + u * float(pos[0]) + v * float(pos[1]) + n * float(offset_n)

    M = T @ R  # primero rota el texto (XY->plano), luego traslada

    tm = text_mesh.copy()
    tm.apply_transform(M)
    return tm


def _boolean_union(a: trimesh.Trimesh, b: trimesh.Trimesh) -> Optional[trimesh.Trimesh]:
    try:
        from trimesh.boolean import union
        res = union([a, b], engine=None)  # deja que escoja motor disponible
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
        "size": 6,              # altura del texto (mm)
        "depth": 1.2,           # extrusión (mm)
        "mode": "engrave"|"emboss",
        "pos": [x_mm, y_mm, 0], # desplazamiento en el plano anclado
        "rot": [0,0,0],         # (no usado: la orientación la da el anchor)
        "font": "DejaVuSans.ttf" | None,
        "anchor": "front"|"back"|"left"|"right"|"top"|"bottom"   # NUEVO
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
        font = op.get("font") or None
        pos = op.get("pos") or [0, 0, 0]
        try:
            px, py, pz = float(pos[0]), float(pos[1]), float(pos[2] if len(pos) > 2 else 0.0)
        except Exception:
            px, py, pz = 0.0, 0.0, 0.0
        anchor: Anchor = op.get("anchor") or "front"  # por defecto frente

        solid = _make_text_solid(text=text, height=size, depth=depth, font=font)
        if not isinstance(solid, trimesh.Trimesh) or len(solid.vertices) == 0:
            # si no pudimos generar texto, no rompemos la pieza
            continue

        placed = _place_text_on_face(
            text_mesh=solid, base=out, anchor=anchor, pos=(px, py, pz), depth=depth, mode=mode
        )

        if mode == "emboss":
            # Intentar unión booleana; si falla, concatenamos (queda "pegado" pero visible)
            merged = _boolean_union(out, placed)
            out = merged if merged is not None else _concat([out, placed])
        else:
            # Grabado: probar diferencia booleana; si falla, mantenemos sin grabar
            carved = _boolean_diff(out, placed)
            if carved is not None:
                out = carved
            else:
                # Fallback: si no hay motor booleano disponible, al menos deja el relieve
                out = _concat([out, placed])

    return out
