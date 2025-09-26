# apps/stl-service/models/_helpers.py
from typing import Iterable, List, Tuple, Union

HoleLike = Union[Tuple[float, float, float], List[float], dict]

def _coerce_float(v, default=0.0) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)

def parse_holes(holes: Iterable[HoleLike]) -> List[Tuple[float, float, float]]:
    """
    Normaliza agujeros a lista de tuplas (x, y, d) en milímetros.
    Soporta:
      - (x, y, d) o [x, y, d]
      - {x, y, d}
      - {x_mm, z_mm, d_mm}  <- usado por el frontend actual
      - {x, z, d}
    Ignora silenciosamente entradas inválidas.
    """
    out: List[Tuple[float, float, float]] = []

    for h in holes or []:
        # Tupla/lista
        if isinstance(h, (tuple, list)):
            if len(h) >= 3:
                x = _coerce_float(h[0])
                y = _coerce_float(h[1])
                d = _coerce_float(h[2])
                out.append((x, y, d))
            continue

        # Diccionario
        if isinstance(h, dict):
            # variantes con sufijo _mm (frontend)
            if "x_mm" in h and "z_mm" in h and ("d_mm" in h or "diameter" in h or "d" in h):
                x = _coerce_float(h.get("x_mm"))
                y = _coerce_float(h.get("z_mm"))   # usamos Z del visor como Y del modelo 2D
                d = _coerce_float(h.get("d_mm", h.get("diameter", h.get("d"))))
                out.append((x, y, d))
                continue

            # variantes x/z/d (por compatibilidad)
            if "x" in h and "z" in h and ("d_mm" in h or "d" in h):
                x = _coerce_float(h.get("x"))
                y = _coerce_float(h.get("z"))
                d = _coerce_float(h.get("d_mm", h.get("d")))
                out.append((x, y, d))
                continue

            # variante clásica x/y/d
            if "x" in h and "y" in h and ("d" in h or "d_mm" in h):
                x = _coerce_float(h.get("x"))
                y = _coerce_float(h.get("y"))
                d = _coerce_float(h.get("d", h.get("d_mm")))
                out.append((x, y, d))
                continue

    return out
