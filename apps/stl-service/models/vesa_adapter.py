# apps/stl-service/models/vesa_adapter.py
from __future__ import annotations

from typing import Dict, Any, List, Tuple, Iterable, Optional
import math
import trimesh

# Si tienes estos helpers en tu repo, se usan. Si no, el builder funciona igualmente
try:
    from ._helpers import parse_holes as _parse_holes  # type: ignore
except Exception:  # fallback simple por si no existe
    def _parse_holes(holes_in: Iterable[Any]) -> List[Tuple[float, float, float]]:
        """
        Acepta:
          - [(x,y,d), ...]
          - [{"x_mm":..,"y_mm":..,"d_mm":..}, ...]
        Devuelve lista [(x,y,d), ...] en mm.
        """
        out: List[Tuple[float, float, float]] = []
        for h in holes_in or []:
            if isinstance(h, dict):
                x = float(h.get("x_mm", 0.0))
                y = float(h.get("y_mm", 0.0))
                d = float(h.get("d_mm", 0.0))
                out.append((x, y, d))
            elif isinstance(h, (list, tuple)) and len(h) >= 3:
                out.append((float(h[0]), float(h[1]), float(h[2])))
        return out

try:
    # Debe existir en tu repo. Reemplaza por tu util si el nombre difiere.
    from .utils_geo import plate_with_holes  # type: ignore
except Exception:
    # Fallback mínimo por si no existe: genera una placa agujereada con trimesh
    def plate_with_holes(L: float, W: float, T: float, holes: List[Tuple[float, float, float]]) -> trimesh.Trimesh:
        """
        Placa rectangular centrada en (0,0) de LxW y espesor T.
        Agujeros cilíndricos pasantes en posiciones (x,y) con diámetro d.
        (Fallback simplificado usando booleanas de trimesh)
        """
        base = trimesh.creation.box(extents=(L, W, T))
        cutters: List[trimesh.Trimesh] = []
        for (x, y, d) in holes:
            r = d / 2.0
            h = T * 1.2  # un poco más alto para garantizar corte pasante
            cyl = trimesh.creation.cylinder(radius=r, height=h, sections=64)
            cyl.apply_translation((x, y, 0.0))
            cutters.append(cyl)

        if not cutters:
            return base

        # Unir todos los cilindros en un solo mesh si es posible
        if len(cutters) > 1:
            cutter = trimesh.util.concatenate(cutters)
        else:
            cutter = cutters[0]

        # Colocar centrado en Z para que atraviese
        cutter.apply_translation((0.0, 0.0, 0.0))
        result = base.difference(cutter, engine="scad" if trimesh.interfaces.scad.exists else None)
        return result if isinstance(result, trimesh.Trimesh) else base


NAME = "vesa_adapter"

TYPES: Dict[str, str] = {
    "vesa_mm": "float",       # separación entre centros (100, 75, 50...)
    "thickness": "float",     # espesor de la placa
    "clearance": "float",     # margen alrededor (placa > patrón)
    "hole": "float",          # diámetro agujeros VESA
    "holes": "list[(x,y,d), ...]",  # opcional: si viene, se usa tal cual
}

DEFAULTS: Dict[str, Any] = {
    "vesa_mm": 100.0,
    "thickness": 5.0,
    "clearance": 10.0,
    "hole": 5.0,
    "holes": None,  # si no viene, generamos a partir de vesa_mm + hole
}


# ----------------------------- helpers -----------------------------
def _coalesce_float(params: Dict[str, Any], *keys: str, default: float) -> float:
    for k in keys:
        if k in params and params[k] is not None:
            try:
                return float(params[k])
            except Exception:
                pass
    return float(default)


def _infer_dims_from_ui(params: Dict[str, Any]) -> Dict[str, float]:
    """
    Permite usar el builder con los campos genéricos del configurador:
    - length_mm, width_mm, height_mm, thickness_mm
    Mapea a (vesa_mm, thickness, clearance) cuando falten los específicos.
    Reglas:
      - vesa_mm: si no viene, usa width_mm (o length_mm) como patrón VESA
      - thickness: usa thickness_mm si viene
      - clearance: si length_mm (u otra) > vesa_mm, clearance = (outer - vesa_mm)/2
                   en otro caso usa DEFAULTS["clearance"]
    """
    vesa = _coalesce_float(params, "vesa_mm", "vesa", "width_mm", "length_mm", default=DEFAULTS["vesa_mm"])
    thickness = _coalesce_float(params, "thickness", "thickness_mm", default=DEFAULTS["thickness"])

    # intenta deducir el tamaño exterior de la placa (LxW)
    outer_L = _coalesce_float(params, "length_mm", default=vesa + 2 * DEFAULTS["clearance"])
    outer_W = _coalesce_float(params, "height_mm", "plate_height_mm", default=vesa + 2 * DEFAULTS["clearance"])

    # si alguno es mayor que vesa, deducimos clearance; tomamos el menor de ambos para evitar negativos
    inferred_clearance_L = max(0.0, (outer_L - vesa) / 2.0)
    inferred_clearance_W = max(0.0, (outer_W - vesa) / 2.0)
    inferred_clearance = min(
        _coalesce_float(params, "clearance", "margin", default=DEFAULTS["clearance"]),
        max(inferred_clearance_L, inferred_clearance_W) if (outer_L > vesa or outer_W > vesa) else DEFAULTS["clearance"]
    )

    hole_d = _coalesce_float(params, "hole", "hole_mm", default=DEFAULTS["hole"])

    return {
        "vesa_mm": vesa,
        "thickness": thickness,
        "clearance": inferred_clearance,
        "hole": hole_d,
        "outer_L": outer_L,
        "outer_W": outer_W,
    }


def _resolve_holes(params: Dict[str, Any], vesa: float, hole_d: float) -> List[Tuple[float, float, float]]:
    # Si vienen agujeros explícitos, respeta eso
    holes_in = params.get("holes")
    if holes_in:
        parsed = _parse_holes(holes_in)
        if parsed:
            return parsed

    # Patrón VESA estándar: cuatro agujeros en las esquinas del cuadrado vesa×vesa
    s = vesa / 2.0
    return [( s,  s, hole_d), (-s,  s, hole_d), ( s, -s, hole_d), (-s, -s, hole_d)]


# ----------------------------- builder -----------------------------
def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    """
    Builder principal. Devuelve un trimesh.Trimesh listo para exportar.
    Acepta tanto parámetros específicos como genéricos del configurador.
    """
    # Normaliza parámetros (acepta UI genérica)
    norm = _infer_dims_from_ui(params)
    vesa = norm["vesa_mm"]
    t = norm["thickness"]
    c = norm["clearance"]
    hole_d = norm["hole"]

    # Tamaño exterior de la placa (cuadrada, usando vesa + 2*clearance)
    L = W = vesa + 2.0 * c

    # Agujeros
    holes = _resolve_holes(params, vesa=vesa, hole_d=hole_d)

    # Construir la placa agujereada
    mesh = plate_with_holes(L, W, t, holes)
    # Centra en Z=0 para que la mitad de espesor sobresalga arriba/abajo (opcional)
    try:
        # trimesh.box crea con centro en (0,0,0), pero por si el util no lo hace:
        bbox = mesh.bounds
        z_center = (bbox[0, 2] + bbox[1, 2]) / 2.0
        if abs(z_center) > 1e-6:
            mesh.apply_translation((0.0, 0.0, -z_center))
    except Exception:
        pass

    return mesh


# Nombre que usará el registro si importa un callable directamente
def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)


# También podemos exportar un diccionario para registros tipo dict
BUILD = {"make": make}


__all__ = ["NAME", "TYPES", "DEFAULTS", "make", "make_model", "BUILD"]
