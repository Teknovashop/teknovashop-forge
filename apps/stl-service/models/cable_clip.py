# apps/stl-service/models/cable_clip.py
import shapely.geometry as sg
import shapely.affinity as sa
import shapely.ops as so
import trimesh

def make_model(
    diameter: float = 8.0,
    width: float = 12.0,
    thickness: float = 2.4,
) -> trimesh.Trimesh:
    """
    Clip tipo “C”: se hace como un anillo circular con hueco y se extruye.
    """
    r = diameter / 2.0
    outer = sg.Point(0,0).buffer(r + thickness, resolution=128)
    inner = sg.Point(0,0).buffer(r, resolution=128)
    ring = outer.difference(inner)
    # abrimos la “C” eliminando un sector
    gap = sg.box(-1e3, -r, r*0.25, +r)  # ranura en un lado
    cshape = ring.difference(gap)
    # dar ancho en Z: hacemos la extrusión en Y y el “ancho” es el espesor de extrusión T,
    # luego el usuario puede girarlo si quiere.
    mesh = trimesh.creation.extrude_polygon(cshape, width)
    mesh.apply_translation((0, width/2.0, 0))
    return mesh
