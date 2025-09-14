from typing import Dict, Any
import trimesh


def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    """
    Cable tray "MVP": canal en U hecho con 3 placas (fondo + 2 laterales).
    Parámetros:
      - width (mm)      default 60   (ancho interior aprox)
      - height (mm)     default 25   (altura lateral)
      - length (mm)     default 180  (largo del canal)
      - thickness (mm)  default 3    (grosor de paredes)
    """
    W = float(params.get("width", 60))
    H = float(params.get("height", 25))
    L = float(params.get("length", 180))
    T = float(params.get("thickness", 3))

    # Fondo: L x W x T
    bottom = trimesh.creation.box(extents=(L, W, T))
    # Centrar en X (L), Y (W). Dejar Z en 0
    bottom.apply_translation((-L / 2.0, -W / 2.0, 0.0))

    # Lateral izquierdo: L x T x H
    side_left = trimesh.creation.box(extents=(L, T, H))
    side_left.apply_translation((-L / 2.0, -W / 2.0, T))  # sobre el fondo

    # Lateral derecho: L x T x H
    side_right = trimesh.creation.box(extents=(L, T, H))
    side_right.apply_translation((-L / 2.0, (W / 2.0 - T), T))

    mesh = trimesh.util.concatenate([bottom, side_left, side_right])
    return mesh
