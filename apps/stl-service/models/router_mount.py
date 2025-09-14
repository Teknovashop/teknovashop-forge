from typing import Dict, Any
import trimesh


def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    """
    Router wall-mount "MVP": escuadra en L (dos placas unidas).
    Parámetros:
      - width (mm)      default 160 (ancho base contra pared)
      - height (mm)     default 220 (alto)
      - depth (mm)      default 40  (saliente/estante)
      - thickness (mm)  default 4   (grosor placas)
    """
    w = float(params.get("width", 160))
    h = float(params.get("height", 220))
    d = float(params.get("depth", 40))
    t = float(params.get("thickness", 4))

    # Placa vertical (contra pared): w x h x t
    vertical = trimesh.creation.box(extents=(w, h, t))
    vertical.apply_translation((-w / 2.0, -h / 2.0, 0.0))  # Z=0 al ras

    # Placa horizontal (estante): w x d x t
    horizontal = trimesh.creation.box(extents=(w, d, t))
    # Posición: pegada en la base de la placa vertical, saliendo en +Y
    horizontal.apply_translation((-w / 2.0, 0.0, t))  # encima, apoyada en Z=t

    # Unir ambas (sólo concatenar mallas; no CSG)
    mesh = trimesh.util.concatenate([vertical, horizontal])

    return mesh
