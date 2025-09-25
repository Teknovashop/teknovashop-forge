# apps/stl-service/models/_helpers.py
from __future__ import annotations
from typing import Any, List, Tuple, Optional

Number = float
Hole = Tuple[Number, Number, Number]  # (x_mm, z_mm, d_mm)

def _as_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

def _hole_from(obj: Any) -> Optional[Hole]:
    """
    Normaliza distintos formatos de agujero a una tupla (x_mm, z_mm, d_mm).
    Acepta:
      - (x, z, d) / [x, z, d]
      - {"x_mm":..,"z_mm":..,"d_mm":..}  (o "x","z","d"/"diameter")
    """
    if obj is None:
        return None

    if isinstance(obj, (list, tuple)) and len(obj) >= 3:
        x, z, d = obj[0], obj[1], obj[2]
        return (_as_float(x), _as_float(z), _as_float(d))

    if isinstance(obj, dict):
        x = obj.get("x_mm", obj.get("x"))
        z = obj.get("z_mm", obj.get("z"))
        d = obj.get("d_mm", obj.get("d") or obj.get("diameter"))
        if x is None or z is None or d is None:
            return None
        return (_as_float(x), _as_float(z), _as_float(d))

    return None

def parse_holes(params: dict, key: str = "holes") -> List[Hole]:
    """
    Extrae y normaliza la lista de agujeros desde params[key].
    Devuelve una lista de tuplas (x_mm, z_mm, d_mm).
    """
    raw = params.get(key, [])
    out: List[Hole] = []

    # Por si llega un contenedor {'items':[...]} o {'data':[...]}
    if isinstance(raw, dict):
        raw = raw.get("items") or raw.get("data") or []

    if isinstance(raw, (list, tuple)):
        for item in raw:
            h = _hole_from(item)
            if h:
                out.append(h)

    return out

# Utilidades genéricas que usan algunos modelos
def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(v)))

def mm(x: Any) -> float:
    """Alias para convertir a float (mm)."""
    return _as_float(x)
