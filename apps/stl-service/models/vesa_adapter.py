# apps/stl-service/models/vesa_adapter.py
from __future__ import annotations

from typing import Dict, Any, List, Tuple
import trimesh

from .utils_geo import plate_with_holes

NAME = "vesa_adapter"
SLUGS = ["vesa-adapter", "adaptador_vesa"]

DEFAULTS: Dict[str, Any] = {
    "pattern_from": 75.0,
    "pattern_to": 100.0,
    "width": 120.0,
    "height": 120.0,
    "thickness": 5.0,
    "hole_d": 5.0,
    "margin": 10.0,
}

TYPES: Dict[str, str] = {
    "pattern_from": "float",
    "pattern_to": "float",
    "width": "float",
    "height": "float",
    "thickness": "float",
    "hole_d": "float",
    "margin": "float",
}


def _num(params: Dict[str, Any], *keys: str, default: float) -> float:
    for key in keys:
        if key in params and params[key] is not None:
            try:
                return float(str(params[key]).replace(",", "."))
            except Exception:
                pass
    return float(default)


def _pattern_holes(pattern: float, hole_d: float) -> List[Tuple[float, float, float]]:
    half = pattern / 2.0
    return [
        (-half, -half, hole_d),
        (+half, -half, hole_d),
        (-half, +half, hole_d),
        (+half, +half, hole_d),
    ]


def _dedupe_holes(holes: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
    seen = set()
    out: List[Tuple[float, float, float]] = []
    for x, y, d in holes:
        key = (round(x, 4), round(y, 4), round(d, 4))
        if key in seen:
            continue
        seen.add(key)
        out.append((x, y, d))
    return out


def _extra_holes(
    params: Dict[str, Any],
    plate_w: float,
    plate_h: float,
) -> List[Tuple[float, float, float]]:
    """Agujeros libres adicionales, con coordenadas X/Y desde el centro."""
    raw = params.get("holes") or []
    out: List[Tuple[float, float, float]] = []

    for item in raw:
        try:
            x, y, d = item
            x = float(x)
            y = float(y)
            d = float(d)
        except Exception as exc:
            raise ValueError(f"Invalid extra hole definition: {item!r}") from exc

        if d <= 0:
            raise ValueError("Extra hole diameter must be greater than 0")

        r = d / 2.0
        if abs(x) + r > plate_w / 2.0 or abs(y) + r > plate_h / 2.0:
            raise ValueError(
                f"Extra hole ({x}, {y}, Ø{d}) does not fit inside "
                f"{plate_w} x {plate_h} mm plate"
            )

        out.append((x, y, d))

    return out


def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    """
    Adaptador VESA real entre DOS patrones cuadrados.

    Ejemplos:
      pattern_from=75, pattern_to=100  -> 8 agujeros
      pattern_from=100, pattern_to=200 -> 8 agujeros

    La placa se agranda automáticamente si width/height no dejan margen
    suficiente alrededor del patrón mayor.

    Compatibilidad con el configurador genérico actual:
      length_mm -> width
      width_mm  -> height
      thickness_mm -> thickness
    """
    p_from = max(
        25.0,
        _num(params, "pattern_from", "vesa_from", default=DEFAULTS["pattern_from"]),
    )
    p_to = max(
        25.0,
        _num(params, "pattern_to", "vesa_to", "vesa_mm", default=DEFAULTS["pattern_to"]),
    )
    thickness = max(
        1.5,
        _num(params, "thickness", "thickness_mm", default=DEFAULTS["thickness"]),
    )
    hole_d = max(
        2.0,
        _num(params, "hole_d", "hole", "hole_mm", default=DEFAULTS["hole_d"]),
    )
    margin = max(
        hole_d,
        _num(params, "margin", "clearance", default=DEFAULTS["margin"]),
    )

    requested_w = _num(
        params,
        "width",
        "plate_width",
        "length_mm",
        default=DEFAULTS["width"],
    )
    requested_h = _num(
        params,
        "height",
        "plate_height",
        "width_mm",
        default=DEFAULTS["height"],
    )

    largest_pattern = max(p_from, p_to)
    minimum_outer = largest_pattern + 2.0 * margin
    plate_w = max(requested_w, minimum_outer)
    plate_h = max(requested_h, minimum_outer)

    holes = _dedupe_holes(
        _pattern_holes(p_from, hole_d)
        + _pattern_holes(p_to, hole_d)
        + _extra_holes(params, plate_w, plate_h)
    )

    mesh = plate_with_holes(plate_w, plate_h, thickness, holes)
    try:
        mesh.metadata = {
            "name": "vesa_adapter",
            "unit": "mm",
            "pattern_from": p_from,
            "pattern_to": p_to,
            "hole_count": len(holes),
        }
    except Exception:
        pass
    return mesh


def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)


BUILD = {"make": make, "build": make_model}

__all__ = [
    "NAME",
    "SLUGS",
    "DEFAULTS",
    "TYPES",
    "make",
    "make_model",
    "BUILD",
]
