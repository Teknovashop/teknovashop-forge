# apps/stl-service/models/text_ops.py
"""
Aplicación de texto (engrave/emboss) sobre un mesh con Trimesh.

- Detecta el eje de menor espesor del modelo para “pegar” el texto sobre esa cara.
- EMBOSS (relieve): concatena el texto como volumen positivo (estable).
- ENGRAVE (grabar): intenta boolean.difference; si no hay backend booleano,
  hace fallback a emboss para que el usuario vea algo.

Parámetros esperados por cada op:
{
  "text": str,
  "size": float,     # alto del texto en mm (aprox)
  "depth": float,    # altura de extrusión en mm
  "mode": "engrave" | "emboss",
  "pos": [x,y,z],    # opcional, mm
  "rot": [rx,ry,rz], # opcional, grados (Euler ZYX); normalmente con rz basta
  "font": str | None # opcional; se usa el default del sistema si no hay
}
"""

from __future__ import annotations
import math
from typing import Iterable, List, Dict, Any, Tuple

import numpy as np
import trimesh

try:
    import shapely.affinity as s_aff
except Exception:
    s_aff = None  # sólo afecta a un escalado más preciso

# ----------------------------- utilidades -----------------------------

def _as_mesh_list(obj) -> List[trimesh.Trimesh]:
    if obj is None:
        return []
    if isinstance(obj, trimesh.Trimesh):
        return [obj]
    if isinstance(obj, (list, tuple)):
        out: List[trimesh.Trimesh] = []
        for it in obj:
            if isinstance(it, trimesh.Trimesh):
                out.append(it)
        return out
    # Scene u otros: intentar “dump” de geometrías
    if hasattr(obj, "geometry"):
        try:
            return [g for g in obj.geometry.values() if isinstance(g, trimesh.Trimesh)]
        except Exception:
            pass
    return []

def _bbox_extents(mesh: trimesh.Trimesh) -> np.ndarray:
    # eje-alineado
    return mesh.bounds[1] - mesh.bounds[0]

def _thickness_axis(mesh: trimesh.Trimesh) -> int:
    ex = _bbox_extents(mesh)
    return int(np.argmin(ex))  # 0=x, 1=y, 2=z

def _center(mesh: trimesh.Trimesh) -> np.ndarray:
    return mesh.bounds.mean(axis=0)

def _rot_zxy(rx: float, ry: float, rz: float) -> np.ndarray:
    # Euler ZYX en grados -> matriz 4x4
    Rx = trimesh.transformations.rotation_matrix(math.radians(rx), [1, 0, 0])
    Ry = trimesh.transformations.rotation_matrix(math.radians(ry), [0, 1, 0])
    Rz = trimesh.transformations.rotation_matrix(math.radians(rz), [0, 0, 1])
    return trimesh.transformations.concatenate_matrices(Rz, Ry, Rx)

def _align_Z_to_axis(axis: int) -> np.ndarray:
    """
    Devuelve una matriz que lleva el local +Z del texto a (X|Y|Z) según 'axis'.
    """
    target = np.zeros(3)
    target[axis] = 1.0  # unit vector
    return trimesh.geometry.align_vectors([0, 0, 1], target)

def _safe_boolean_difference(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh | None:
    try:
        diff = trimesh.boolean.difference(a, b, engine=None)  # deja que elija motor
        if isinstance(diff, list) and diff:
            return trimesh.util.concatenate(diff)
        if isinstance(diff, trimesh.Trimesh):
            return diff
    except Exception:
        return None
    return None

# -------------------- construcción del mesh de texto ------------------

def _build_text_mesh(op: Dict[str, Any]) -> trimesh.Trimesh | None:
    text = str(op.get("text", "") or "").strip()
    if not text:
        return None

    size = float(op.get("size", 6.0)) or 6.0  # alto del texto en mm
    depth = float(op.get("depth", 1.2)) or 1.2
    font = op.get("font", None)

    # 1) Path 2D del texto
    path2d = None
    try:
        # Trimesh genera un Path2D del texto; requiere freetype (viene en muchas imágenes)
        path2d = trimesh.path.creation.text(text=text, font=font)
    except Exception:
        path2d = None

    if path2d is None:
        # Fallback MUY simple: una caja que simula “etiqueta” de ancho ~0.6 * size * len(text)
        # Así, al menos, el usuario ve “algo” en relieve.
        approx_w = max(size * 0.6 * max(len(text), 1), size)
        label = trimesh.creation.box((approx_w, size * 0.2, depth))
        # centrar en XY (que su “base” esté en Z=0)
        label.apply_translation((-label.extents[0] / 2, -label.extents[1] / 2, 0))
        return label

    # 2) Escalado del path para que su altura ~ size
    minx, miny = path2d.bounds[0]
    maxx, maxy = path2d.bounds[1]
    h = max(1e-6, (maxy - miny))
    scale = size / h

    if s_aff is not None:
        # con shapely: escalar el path y volver a crear Path2D
        try:
            polys = [s_aff.scale(p, xfact=scale, yfact=scale, origin=(0, 0)) for p in path2d.polygons_full]
        except Exception:
            polys = path2d.polygons_full
    else:
        # sin shapely: escalar vértices del path
        path2d = path2d.copy()
        path2d.vertices[:] *= scale
        polys = path2d.polygons_full

    # 3) Extruir todos los polígonos (con huecos) y concatenar
    parts: List[trimesh.Trimesh] = []
    for poly in polys:
        try:
            m = trimesh.creation.extrude_polygon(poly, depth)
            parts.append(m)
        except Exception:
            continue

    if not parts:
        return None

    mesh = trimesh.util.concatenate(parts)
    # Colocar base del texto sobre Z=0 y centrar en XY
    bb = mesh.bounds
    mesh.apply_translation((- (bb[0][0] + bb[1][0]) / 2.0, - (bb[0][1] + bb[1][1]) / 2.0, -bb[0][2]))
    return mesh

# ------------------------ API principal a exportar --------------------

def apply_text_ops(
    base_mesh_or_meshes: Any,
    ops: Iterable[Dict[str, Any]] | None
):
    """
    Devuelve un único Trimesh resultante de aplicar todas las ops al primer mesh.
    Si recibimos una lista de meshes, trabajamos sobre su concatenación.
    """
    meshes = _as_mesh_list(base_mesh_or_meshes)
    if not meshes:
        return base_mesh_or_meshes

    base = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0].copy()
    if not ops:
        return base

    # Detectar el eje de grosor (menor extensión)
    axis = _thickness_axis(base)
    ext = _bbox_extents(base)
    bb = base.bounds
    center = _center(base)

    # Calcular posiciones “por defecto” en el plano de la cara “superior”
    # - alineamos texto al centro en los otros ejes
    # - lo “hundimos” un poco para que embeba (evita separación visual)
    top = bb[1, axis]  # coordenada “superior” en eje de grosor
    embed = max(0.2, 0.25)  # fracción de depth para embebido

    for raw in ops:
        try:
            label = _build_text_mesh(raw)
            if label is None:
                continue

            mode = str(raw.get("mode", "engrave") or "engrave").lower()
            rx, ry, rz = [float(v) for v in (raw.get("rot") or [0, 0, 0])]
            px, py, pz = [float(v) for v in (raw.get("pos") or [0, 0, 0])]
            depth = float(raw.get("depth", 1.2) or 1.2)

            # 1) Alinear +Z del texto con el eje de grosor del modelo
            M_align = _align_Z_to_axis(axis)
            label.apply_transform(M_align)

            # 2) Rotación extra del usuario (Euler ZYX)
            M_user = _rot_zxy(rx, ry, rz)
            label.apply_transform(M_user)

            # 3) Colocar en el centro del modelo en los ejes “anchos”
            pos = center.copy()
            # sobre la cara superior (un poco embebido)
            pos[axis] = top - depth * embed
            # aplicar offset del usuario
            pos += np.array([px, py, pz], dtype=float)
            label.apply_translation(pos)

            if mode == "emboss":
                base = trimesh.util.concatenate([base, label])
            else:
                diff = _safe_boolean_difference(base, label)
                base = diff if diff is not None else trimesh.util.concatenate([base, label])

        except Exception:
            # si algo falla en una op, seguimos con las demás
            continue

    return base
