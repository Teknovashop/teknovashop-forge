import math
import trimesh as tm

def make_model(p: dict) -> tm.Trimesh:
    # params: angle_deg, support_depth, width, thickness
    angle = float(p.get("angle_deg", 60.0))
    depth = float(p.get("support_depth", 110.0))
    width = float(p.get("width", 80.0))
    t = float(p.get("thickness", 4.0))

    # base + plano inclinado (dos placas)
    base = tm.creation.box((depth, t, width))            # X,Y,Z
    base.apply_translation((depth/2, t/2, width/2))

    # panel inclinado
    h = depth * 0.55
    panel = tm.creation.box((h, t, width))
    panel.apply_translation((h/2, t/2, width/2))
    # pivotar alrededor del borde trasero de la base
    pivot = tm.transformations.translation_matrix((t, 0, 0))
    rot = tm.transformations.rotation_matrix(math.radians(-angle), (0,0,1), point=(t,0,0))
    panel.apply_transform(pivot @ rot)

    return tm.util.concatenate([base, panel])
