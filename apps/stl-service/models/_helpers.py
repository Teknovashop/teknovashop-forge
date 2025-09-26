# apps/stl-service/models/_helpers.py
from typing import Any, Dict, Iterable, List, Tuple

def as_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

def hole_to_dict(h: Any) -> Dict[str, float]:
    """
    Devuelve SIEMPRE un dict {x_mm, z_mm, d_mm}.
    Acepta:
      - dict con x_mm/x, z_mm/z, d_mm/d/diameter
      - tuple/list (x, z, d)
      - objetos con atributos x_mm, z_mm, d_mm
    """
    if isinstance(h, (list, tuple)) and len(h) >= 3:
        return {"x_mm": as_float(h[0]), "z_mm": as_float(h[1]), "d_mm": as_float(h[2])}
    if isinstance(h, dict):
        x = h.get("x_mm", h.get("x"))
        z = h.get("z_mm", h.get("z"))
        d = h.get("d_mm", h.get("d", h.get("diameter")))
        return {"x_mm": as_float(x), "z_mm": as_float(z), "d_mm": as_float(d)}
    # Pydantic u objeto con atributos
    if hasattr(h, "x_mm") and hasattr(h, "z_mm") and hasattr(h, "d_mm"):
        return {
            "x_mm": as_float(getattr(h, "x_mm")),
            "z_mm": as_float(getattr(h, "z_mm")),
            "d_mm": as_float(getattr(h, "d_mm")),
        }
    # Valor raro: devolvemos dict vacío para no romper
    return {"x_mm": 0.0, "z_mm": 0.0, "d_mm": 0.0}

def parse_holes(holes_in: Any) -> List[Dict[str, float]]:
    """
    Normaliza 'holes' (lo que venga) a una LISTA DE DICCIONARIOS.
    Nunca devuelve None; si no hay agujeros, devuelve [].
    """
    if holes_in is None:
        return []
    # Si por error llega un dict de un solo agujero
    if isinstance(holes_in, dict) and {"x_mm","z_mm","d_mm"} & holes_in.keys():
        return [hole_to_dict(holes_in)]
    # Iterable (lista/tupla)
    if isinstance(holes_in, (list, tuple)):
        out: List[Dict[str, float]] = []
        for h in holes_in:
            out.append(hole_to_dict(h))
        return out
    # Cualquier otra cosa
    return []
