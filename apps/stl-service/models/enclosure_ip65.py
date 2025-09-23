# apps/stl-service/models/enclosure_ip65.py
from typing import Iterable, Tuple, List
import trimesh as tm
from .utils_geo import plate_with_holes, rectangle_plate, concatenate
import math

def make_model(p: dict) -> tm.Trimesh:
    length = float(p.get("length", p.get("box_length", 201.0)))
    width  = float(p.get("width",  p.get("box_width", 68.0)))
    height = float(p.get("height", p.get("box_height", 31.0)))
    wall   = float(p.get("wall",   p.get("thickness", 5.0)))
    ventilated = bool(p.get("ventilated", True))
    free: Iterable[Tuple[float,float,float]] = p.get("holes") or []

    base = plate_with_holes(L=length, W=width, T=wall,
                            holes=[(float(x), float(z), float(d)) for (x,z,d) in free])

    side_holes: List[Tuple[float,float,float]] = []
    if ventilated:
        pitch = 12.0
        d = 5.0
        y_rows = [height * 0.3, height * 0.6]
        xs = [x for x in range(-int(length//2), int(length//2)+1, int(pitch))]
        for y in y_rows:
            for x in xs:
                side_holes.append((float(x), float(y), d))

    long1 = rectangle_plate(L=length, H=height, T=wall, holes=side_holes).copy()
    long2 = rectangle_plate(L=length, H=height, T=wall, holes=side_holes).copy()
    long1.apply_translation((0, height/2.0, +width/2.0))
    long2.apply_translation((0, height/2.0, -width/2.0))

    short1 = rectangle_plate(L=width, H=height, T=wall, holes=[]).copy()
    short2 = rectangle_plate(L=width, H=height, T=wall, holes=[]).copy()
    R = tm.transformations.rotation_matrix(math.pi/2.0, (0,1,0))
    short1.apply_transform(R)
    short2.apply_transform(R)
    short1.apply_translation((+length/2.0, height/2.0, 0))
    short2.apply_translation((-length/2.0, height/2.0, 0))

    lid = plate_with_holes(L=length, W=width, T=wall, holes=[])
    lid.apply_translation((0, height, 0))

    return concatenate([base, long1, long2, short1, short2, lid])
