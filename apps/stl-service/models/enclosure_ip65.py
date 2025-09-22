# apps/stl-service/models/enclosure_ip65.py
from typing import Dict, Any, Iterable, List, Tuple
import trimesh
from .utils_geo import plate_with_holes, rectangle_plate, concatenate

def make_model(
    length: float = 201.0,
    width: float = 68.0,
    height: float = 31.0,
    wall: float = 5.0,
    grill: float = 16.0,
    ventilated: bool = True,
    holes: Iterable[Dict[str, float]] = (),
) -> trimesh.Trimesh:
    """
    Caja “IP65-like”: no hacemos boolean de caja hueca, sino paredes + tapa como placas.
    - Base (suelo)
    - Paredes: 4 placas
    - Tapa: 1 placa (se puede imprimir aparte si quieres más tarde)
    """
    # base
    base = plate_with_holes(L=length, W=width, T=wall,
                            holes=[(h["x_mm"], h["z_mm"], h["d_mm"]) for h in holes])

    # rejillas en paredes largas si ventilated
    side_holes: List[Tuple[float, float, float]] = []
    if ventilated:
        pitch = 12.0
        d = 5.0
        y_rows = [height * 0.3, height * 0.6]
        xs = [x for x in [i for i in range(-int(length//2), int(length//2)+1, int(pitch))]]
        for y in y_rows:
            for x in xs:
                side_holes.append((float(x), float(y), d))

    # paredes largas (X=length) colocadas a ±width/2
    long1 = rectangle_plate(L=length, H=height, T=wall, holes=side_holes).copy()
    long2 = rectangle_plate(L=length, H=height, T=wall, holes=side_holes).copy()
    long1.apply_translation((0, height/2.0, +width/2.0))
    long2.apply_translation((0, height/2.0, -width/2.0))

    # paredes cortas (Z=width) sin rejilla (o podrías añadir otra)
    short1 = rectangle_plate(L=width, H=height, T=wall, holes=[]).copy()
    short2 = rectangle_plate(L=width, H=height, T=wall, holes=[]).copy()
    # rotar 90º para que “length” de placa sea width y alinearlas
    short1.apply_rotation(trimesh.transformations.rotation_matrix(
        angle=1.57079632679, direction=(0,1,0), point=(0,0,0)
    ))
    short2.apply_rotation(trimesh.transformations.rotation_matrix(
        angle=1.57079632679, direction=(0,1,0), point=(0,0,0)
    ))
    short1.apply_translation((+length/2.0, height/2.0, 0))
    short2.apply_translation((-length/2.0, height/2.0, 0))

    # tapa (misma placa que base), la elevamos a Y=height+wall
    lid = plate_with_holes(L=length, W=width, T=wall, holes=[])
    lid.apply_translation((0, height, 0))

    return concatenate([base, long1, long2, short1, short2, lid])
