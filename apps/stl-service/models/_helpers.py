from __future__ import annotations

from typing import Iterable, Tuple, List, Any, Optional, Sequence
import numpy as np
import trimesh

# ---------------------------------------------------------
# Manifold3D (opcional): booleanos robustos si está instalado
# ---------------------------------------------------------
try:
    import manifold3d as m3d  # pip: manifold3d
    _HAS_MF = True
except Exception:
    m3d = None  # type: ignore
    _HAS_MF = False


# ---------------------- Utilidades numéricas ----------------------

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
    Acepta:
      - dicts: {x, y, diam_mm|diameter|diameter_mm|d}
      - tuples/list: [x, y, diam]
    Devuelve: [(x, y, d), ...]
    """
    out: List[Tuple[float, float, float]] = []
    for h in holes_in or []:
        if isinstance(h, dict):
            x = num(h.get("x"), 0.0)
            y = num(h.get("y"), 0.0)
            d = num(
                h.get("diam_mm")
                or h.get("diameter")
                or h.get("diameter_mm")
                or h.get("d"),
                0.0,
            )
            if x is not None and y is not None and d and d > 0:
                out.append((float(x), float(y), float(d)))
        elif isinstance(h, (list, tuple)) and len(h) >= 3:
            xv = num(h[0])
            yv = num(h[1])
            dv = num(h[2])
            if xv is not None and yv is not None and dv and dv > 0:
                out.append((float(xv), float(yv), float(dv)))
    return out


# ---------------------- Primitivas ----------------------

def box(extents: Sequence[float]) -> trimesh.Trimesh:
    """Caja centrada en el origen. `extents=(L, W, T)` en mm."""
    return trimesh.creation.box(extents=np.asarray(extents, dtype=float))


def cylinder(radius: float, height: float, sections: int = 64) -> trimesh.Trimesh:
    """Cilindro centrado en el origen, eje Z, altura `height`."""
    r = float(radius)
    h = float(height)
    s = int(sections) if sections and sections > 3 else 32
    return trimesh.creation.cylinder(radius=r, height=h, sections=s)


# ---------------------- Reparación y saneado ----------------------

def _repair(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Intenta dejar la malla en estado sano para booleanos/export:
    - elimina duplicados, arregla normales, rellena pequeños huecos, etc.
    """
    if not isinstance(mesh, trimesh.Trimesh):
        return mesh

    m = mesh.copy()

    try:
        # fuerza triangulación
        if not m.is_watertight or not m.faces.shape[1] == 3:
            m = m.triangulate()
    except Exception:
        pass

    try:
        m.remove_unreferenced_vertices()
    except Exception:
        pass

    try:
        trimesh.repair.fix_normals(m)
    except Exception:
        pass

    try:
        # si hay huecos pequeños, intenta cerrarlos
        if not m.is_watertight:
            trimesh.repair.fill_holes(m)
    except Exception:
        pass

    try:
        m.merge_vertices()  # une vértices coincidentes
    except Exception:
        pass

    return m


# ---------------------- Manifold3D bridges ----------------------

def _to_mf(mesh: trimesh.Trimesh):
    if not _HAS_MF:
        return None
    try:
        v = np.asarray(mesh.vertices, dtype=np.float32)
        f = np.asarray(mesh.faces, dtype=np.int32)
        if v.size == 0 or f.size == 0:
            return None
        return m3d.Manifold.FromMesh(m3d.Mesh(v, f))  # type: ignore[attr-defined]
    except Exception:
        return None


def _from_mf(manifold_obj) -> Optional[trimesh.Trimesh]:
    if manifold_obj is None:
        return None
    try:
        mmesh = manifold_obj.ToMesh()
        v = np.asarray(mmesh.vert, dtype=float)
        f = np.asarray(mmesh.tri, dtype=np.int64)
        if v.size == 0 or f.size == 0:
            return None
        out = trimesh.Trimesh(vertices=v, faces=f, process=False)
        return _repair(out)
    except Exception:
        return None


# ---------------------- Booleanos robustos ----------------------

def _concat(meshes: Iterable[trimesh.Trimesh]) -> trimesh.Trimesh:
    lst = [m for m in meshes if isinstance(m, trimesh.Trimesh) and len(m.vertices)]
    if not lst:
        return trimesh.Trimesh()
    return trimesh.util.concatenate(lst)


def union(meshes: Iterable[trimesh.Trimesh]) -> trimesh.Trimesh:
    mlist = [_repair(m) for m in (meshes or []) if isinstance(m, trimesh.Trimesh)]
    if not mlist:
        return trimesh.Trimesh()

    # A) Manifold3D si existe
    if _HAS_MF:
        try:
            acc = None
            for msh in mlist:
                mm = _to_mf(msh)
                if mm is None:
                    acc = None
                    break
                acc = mm if acc is None else (acc + mm)
            if acc is not None:
                out = _from_mf(acc)
                if isinstance(out, trimesh.Trimesh):
                    return _repair(out)
        except Exception:
            pass

    # B) Fallback: trimesh.boolean
    try:
        from trimesh.boolean import union as _u
        res = _u(mlist, engine=None)
        if isinstance(res, trimesh.Trimesh):
            return _repair(res)
    except Exception:
        pass

    # C) último recurso: concat (no es booleano real)
    return _concat(mlist)


def difference(a: trimesh.Trimesh, b: Iterable[trimesh.Trimesh] | trimesh.Trimesh) -> trimesh.Trimesh:
    A = _repair(a)
    Blist = []
    if isinstance(b, (list, tuple)):
        Blist = [_repair(x) for x in b if isinstance(x, trimesh.Trimesh)]
    elif isinstance(b, trimesh.Trimesh):
        Blist = [_repair(b)]
    if not isinstance(A, trimesh.Trimesh) or not Blist:
        return A if isinstance(A, trimesh.Trimesh) else trimesh.Trimesh()

    # A) Manifold3D
    if _HAS_MF:
        try:
            mA = _to_mf(A)
            if mA is not None:
                mB = None
                for c in Blist:
                    mm = _to_mf(c)
                    if mm is None:
                        mB = None
                        break
                    mB = mm if mB is None else (mB + mm)  # unir cortadores
                if mB is not None:
                    out = _from_mf(mA - mB)
                    if isinstance(out, trimesh.Trimesh):
                        return _repair(out)
        except Exception:
            pass

    # B) Fallback: trimesh.boolean
    try:
        from trimesh.boolean import difference as _d
        res = _d([A], Blist, engine=None)
        if isinstance(res, trimesh.Trimesh):
            return _repair(res)
    except Exception:
        pass

    # C) si falla, devolvemos A sin cortar (mejor que romper)
    return A


def intersection(meshes: Iterable[trimesh.Trimesh]) -> trimesh.Trimesh:
    mlist = [_repair(m) for m in (meshes or []) if isinstance(m, trimesh.Trimesh)]
    if len(mlist) < 2:
        return mlist[0] if mlist else trimesh.Trimesh()

    # A) Manifold3D
    if _HAS_MF:
        try:
            acc = _to_mf(mlist[0])
            for msh in mlist[1:]:
                mm = _to_mf(msh)
                if acc is None or mm is None:
                    acc = None
                    break
                acc = acc & mm
            if acc is not None:
                out = _from_mf(acc)
                if isinstance(out, trimesh.Trimesh):
                    return _repair(out)
        except Exception:
            pass

    # B) Fallback: trimesh.boolean
    try:
        from trimesh.boolean import intersection as _i
        res = _i(mlist, engine=None)
        if isinstance(res, trimesh.Trimesh):
            return _repair(res)
    except Exception:
        pass

    # C) sin intersección válida
    return trimesh.Trimesh()


# ---------------------- Helpers de modelo ----------------------

def plate_with_holes(L: float, W: float, T: float, holes: List[Tuple[float, float, float]]) -> trimesh.Trimesh:
    """
    Crea una placa LxW de espesor T centrada en el origen, con taladros en (x,y,diam).
    El eje Z es la altura, por lo que los cilindros se orientan sobre Z.
    """
    base = box((L, W, T))
    if not holes:
        return _repair(base)

    cutters = []
    hcut = T * 1.6  # un poco más alto que la placa para asegurar corte
    for (x, y, d) in holes:
        r = float(d) * 0.5
        c = cylinder(r, hcut, sections=64)
        # por defecto, cilindro centrado en z=0. La placa también: perfecto
        c.apply_translation((float(x), float(y), 0.0))
        cutters.append(c)

    if len(cutters) == 1:
        return difference(base, cutters[0])
    return difference(base, union(cutters))
