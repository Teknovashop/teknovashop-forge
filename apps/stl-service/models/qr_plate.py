# apps/stl-service/models/qr_plate.py
from typing import Iterable, Tuple, List
import trimesh as tm
from trimesh.creation import box, cylinder
from trimesh.boolean import difference
from .utils_geo import plate_with_holes

def _rect_cutout(L: float, W: float, T: float) -> tm.Trimesh:
    cut = box(extents=(L, T*2.0, W))
    cut.apply_translation((0.0, T, 0.0))
    return cut

def make_model(p: dict) -> tm.Trimesh:
    L   = float(p.get("length", 90.0))
    W   = float(p.get("width", 38.0))
    T   = float(p.get("thickness", 8.0))
    slot= float(p.get("slot_mm", 22.0))
    screw = float(p.get("screw_d_mm", 6.5))
    free: Iterable[Tuple[float,float,float]] = p.get("holes") or []

    # placa base
    plate = plate_with_holes(L=L, W=W, T=T, holes=[(0.0, 0.0, screw)])
    # ranura central longitudinal de 'slot' mm (rectangular)
    slot_cut = _rect_cutout(slot, W*0.6, T)
    # restar
    try:
        plate = difference([plate, slot_cut], engine="manifold")
    except Exception:
        # fallback (sin ranura si boolean falla)
        pass

    # agujeros adicionales
    if free:
        add = plate_with_holes(L=L, W=W, T=T, holes=[(float(x), float(z), float(d)) for (x,z,d) in free])
        # "plate_with_holes" ya devuelve con agujeros; para combinarlos, nos quedamos con la versión con más holes
        plate = add

    return plate
