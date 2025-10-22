
from __future__ import annotations
from typing import Iterable, Tuple, List, Any, Optional
import trimesh

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

def box(extents):
    return trimesh.creation.box(extents=extents)

def cylinder(radius, height, sections=64):
    return trimesh.creation.cylinder(radius=radius, height=height, sections=sections)

def difference(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
    engine = "scad" if getattr(trimesh.interfaces.scad, "exists", False) else None
    res = a.difference(b, engine=engine)
    if isinstance(res, trimesh.Trimesh):
        return res
    try:
        return res.dump().sum()
    except Exception:
        return a

def plate_with_holes(L: float, W: float, T: float, holes: List[Tuple[float, float, float]]):
    base = box((L, W, T))
    if not holes:
        return base
    cutters = []
    for (x, y, d) in holes:
        r = d / 2.0
        h = T * 1.5
        c = cylinder(r, h)
        c.apply_translation((x, y, 0.0))
        cutters.append(c)
    cutter = cutters[0] if len(cutters) == 1 else trimesh.util.concatenate(cutters)
    return difference(base, cutter)
