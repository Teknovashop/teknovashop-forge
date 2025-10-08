# apps/stl-service/models/wall_hook.py
from typing import Dict, Any, List, Tuple
import math
import trimesh
from trimesh.creation import box, cylinder
from .utils_geo import plate_with_holes, concatenate
from ._helpers import parse_holes

NAME = "wall_hook"

DEFAULTS: Dict[str, float] = {
    "length_mm": 60.0,     # alto de placa
    "width_mm": 40.0,      # ancho de placa
    "height_mm": 50.0,     # salida del gancho
    "thickness_mm": 5.0,   # espesor placa y gancho
    "fillet_mm": 3.0
}

TYPES: Dict[str, str] = {
    "length_mm": "float",
    "width_mm": "float",
    "height_mm": "float",
    "thickness_mm": "float",
    "fillet_mm": "float",
    "holes": "list[tuple[float,float,float]]",
}

def _hook_arm(Lout: float, T: float) -> trimesh.Trimesh:
    """
    Brazo del gancho: L en Z con ligera curva final aproximada con cilindros.
    """
    # tramo recto
    arm = box(extents=(T, T, Lout*0.75))
    arm.apply_translation((0, T/2.0, Lout*0.75/2.0))
    # extremo curvo
    tip = cylinder(radius=T/2.0, height=T, sections=64)
    tip.apply_rotation(trimesh.transformations.rotation_matrix(math.pi/2, [1,0,0]))
    tip.apply_translation((0, T, Lout*0.75))
    return concatenate([arm, tip])

def make_model(params: Dict[str, Any], holes: List[Tuple[float, float, float]] = ()) -> trimesh.Trimesh:
    Hplate = float(params.get("length_mm", DEFAULTS["length_mm"]))   # alto
    Wplate = float(params.get("width_mm", DEFAULTS["width_mm"]))     # ancho
    Lout   = float(params.get("height_mm", DEFAULTS["height_mm"]))   # salida
    T      = float(params.get("thickness_mm", DEFAULTS["thickness_mm"]))

    # Placa de pared con agujeros (x,z,d)
    hxz = parse_holes(holes) if holes else [(0, Hplate*0.25, 5.0), (0, -Hplate*0.25, 5.0)]
    plate = plate_with_holes(Wplate, Hplate, T, hxz)
    # rotarla para que la altura vaya en Y: nuestra util ya coloca espesor en Y, altura en Z;
    # aquí la usamos tal cual para simplificar la colocación del brazo.
    plate.apply_translation((0, 0, 0))

    # Brazo del gancho
    arm = _hook_arm(Lout, T)
    # Colocar el brazo saliendo del centro de la placa
    arm.apply_translation((0, T, 0))

    # refuerzo bajo el brazo
    gusset = box(extents=(Wplate*0.6, T, Lout*0.4))
    gusset.apply_translation((0, T/2.0, Lout*0.2))

    mesh = concatenate([plate, arm, gusset])
    # Por simplicidad, ya queda apoyado sobre Y=0; placa centrada en XZ
    return mesh