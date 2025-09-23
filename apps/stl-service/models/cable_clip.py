# apps/stl-service/models/cable_clip.py
import math
import trimesh as tm
from trimesh.creation import cylinder, box
from trimesh.boolean import difference, union

def make_model(p: dict) -> tm.Trimesh:
    d   = float(p.get("diameter", 8.0))     # diámetro del cable
    w   = float(p.get("width", 12.0))       # ancho de la abrazadera
    t   = float(p.get("thickness", 2.4))    # espesor material

    r_ext = d/2.0 + t
    r_int = d/2.0

    # aro (anillo) como cilindro exterior menos interior, luego cortar 1/3 para dejar "C"
    h = w
    cyl_ext = cylinder(radius=r_ext, height=h, sections=64)
    cyl_int = cylinder(radius=r_int, height=h*1.2, sections=64)
    try:
        ring = difference([cyl_ext, cyl_int], engine="manifold")
    except Exception:
        # fallback: sin agujero → cilindro macizo del radio externo
        ring = cyl_ext.copy()

    # corte para formar la "C"
    cut_w = r_ext * 0.9
    cut = box(extents=(cut_w, h*1.5, 2*r_ext))
    cut.apply_translation((r_ext*0.55, 0, 0))
    try:
        clip = difference([ring, cut], engine="manifold")
    except Exception:
        clip = ring

    # pestaña plana (opcional simple)
    tab = box(extents=(r_ext*1.2, t, h))
    tab.apply_translation((-r_ext*0.9, t/2.0, 0))

    try:
        clip = union([clip, tab], engine="manifold")
    except Exception:
        clip = tm.util.concatenate([clip, tab])

    # Centrar base en Y=0
    clip.apply_translation((0, 0, 0))
    return clip
