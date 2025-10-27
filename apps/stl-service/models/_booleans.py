# apps/stl-service/models/_booleans.py
from __future__ import annotations
import trimesh
from typing import Iterable, Optional, List

def _valid(mesh: trimesh.Trimesh) -> bool:
    return isinstance(mesh, trimesh.Trimesh) and mesh.vertices.shape[0] > 0

def _prep(meshes: Iterable[trimesh.Trimesh]) -> List[trimesh.Trimesh]:
    return [m for m in meshes if _valid(m)]

def union(meshes: Iterable[trimesh.Trimesh]) -> Optional[trimesh.Trimesh]:
    ms = _prep(meshes)
    if not ms:
        return trimesh.Trimesh()
    try:
        from trimesh.boolean import union as _u
        res = _u(ms, engine=None)
        if isinstance(res, trimesh.Trimesh):
            return res
        if isinstance(res, (list, tuple)):
            return trimesh.util.concatenate([m for m in res if _valid(m)])
    except Exception:
        pass
    return trimesh.util.concatenate(ms)

def difference(a: trimesh.Trimesh, b: trimesh.Trimesh) -> Optional[trimesh.Trimesh]:
    if not _valid(a) or not _valid(b):
        return a.copy() if _valid(a) else trimesh.Trimesh()
    try:
        from trimesh.boolean import difference as _d
        res = _d([a], [b], engine=None)
        if isinstance(res, trimesh.Trimesh):
            return res
    except Exception:
        pass
    # último recurso: concatenar (no graba)
    return trimesh.util.concatenate([a, b])

def intersection(a: trimesh.Trimesh, b: trimesh.Trimesh) -> Optional[trimesh.Trimesh]:
    if not _valid(a) or not _valid(b):
        return trimesh.Trimesh()
    try:
        from trimesh.boolean import intersection as _i
        res = _i([a], [b], engine=None)
        if isinstance(res, trimesh.Trimesh):
            return res
    except Exception:
        pass
    # sin intersección real, devuelve vacío
    return trimesh.Trimesh()
