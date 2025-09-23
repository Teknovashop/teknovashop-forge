# apps/stl-service/models/_helpers.py
from typing import Iterable, List, Tuple, Union

HoleLike = Union[Tuple[float, float, float], dict]

def parse_holes(holes: Iterable[HoleLike]) -> List[Tuple[float, float, float]]:
    """
    Normaliza agujeros a lista de tuplas (x, y, d).
    Soporta: (x, y, d) o {"x":..,"y":..,"d":..}
    Ignora silenciosamente entradas inválidas.
    """
    out: List[Tuple[float, float, float]] = []
    for h in holes or []:
        if isinstance(h, tuple) or isinstance(h, list):
            if len(h) >= 3:
                try:
                    x, y, d = float(h[0]), float(h[1]), float(h[2])
                    out.append((x, y, d))
                except Exception:
                    continue
        elif isinstance(h, dict):
            try:
                x = float(h.get("x"))
                y = float(h.get("y"))
                d = float(h.get("d"))
                out.append((x, y, d))
            except Exception:
                continue
    return out
