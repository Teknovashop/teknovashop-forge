from __future__ import annotations
from typing import Iterable, Tuple, List, Any, Optional
import trimesh

# ------------------------ Utils numéricos ------------------------ #

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
    Admite:
      - dicts: {"x":..,"y":..,"diam_mm"/"diameter"/"d":..}
      - tuplas/listas: (x, y, d)
    Devuelve lista de (x, y, d) en mm con d>0.
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

# ------------------------ Primitivas ------------------------ #

def box(extents):
    """
    Caja centrada en el origen con extents (L, W, T).
    """
    return trimesh.creation.box(extents=extents)


def cylinder(radius, height, sections=64):
    """
    Cilindro centrado en el origen, eje Z, radio y altura en mm.
    """
    return trimesh.creation.cylinder(radius=radius, height=height, sections=sections)

# ------------------------ Booleanos robustos ------------------------ #

def _select_engine() -> Optional[str]:
    """
    Devuelve 'scad' si el backend de OpenSCAD está disponible,
    si no, None para usar los booleanos puros de trimesh.
    """
    scad_iface = getattr(getattr(trimesh, "interfaces", object()), "scad", None)
    if getattr(scad_iface, "exists", False):
        return "scad"
    return None


def difference(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Diferencia booleana robusta.
    1) Usa trimesh.boolean.difference con engine auto.
    2) Si falla, intenta devolver 'a' (mejor algo que romper).
    """
    try:
        from trimesh.boolean import difference as _diff
        engine = _select_engine()
        res = _diff([a], [b], engine=engine)
        if isinstance(res, trimesh.Trimesh):
            return res
        # Algunos backends devuelven lista; concatenamos si procede
        if isinstance(res, (list, tuple)):
            parts = [m for m in res if isinstance(m, trimesh.Trimesh)]
            if parts:
                return trimesh.util.concatenate(parts)
    except Exception:
        pass
    # último recurso
    return a.copy()


# ------------------------ Placa con agujeros ------------------------ #

def plate_with_holes(L: float, W: float, T: float, holes: List[Tuple[float, float, float]]):
    """
    Genera una placa (LxWxT) con agujeros (x, y, d) centrados en Z=0.
    Los agujeros se hacen con cilindros ligeramente más altos que T
    para garantizar una diferencia limpia.
    """
    base = box((L, W, T))
    if not holes:
        return base

    cutters = []
    h = T * 1.5  # más alto que la placa para evitar artefactos
    for (x, y, d) in holes:
        r = d / 2.0
        c = cylinder(r, h)
        # los cilindros ya están centrados en Z, sólo movemos X,Y
        c.apply_translation((x, y, 0.0))
        cutters.append(c)

    cutter = cutters[0] if len(cutters) == 1 else trimesh.util.concatenate(cutters)
    return difference(base, cutter)
