import math
from typing import Dict, Any
import trimesh


def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    """
    VESA adapter "MVP": placa rectangular simple.
    Parámetros admitidos:
      - width (mm)      default 180
      - height (mm)     default 180
      - thickness (mm)  default 6
    """
    w = float(params.get("width", 180))
    h = float(params.get("height", 180))
    t = float(params.get("thickness", 6))

    # Caja (placa)
    plate = trimesh.creation.box(extents=(w, h, t))
    # Centrar XY en origen y apoyar en Z=0
    plate.apply_translation((-w / 2.0, -h / 2.0, 0.0))

    # (MVP sin agujeros para máxima compatibilidad)
    # Si más adelante quieres agujeros VESA 75/100:
    #   - mejor hacerlo en cliente con parámetros y usar CSG externo,
    #   - o exportar sin CSG y dejar guías/relieves.
    return plate
