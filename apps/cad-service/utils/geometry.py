import cadquery as cq

def make_box(params: dict):
    L = float(params.get("length_mm", 100))
    W = float(params.get("width_mm", 80))
    H = float(params.get("height_mm", 40))
    T = float(params.get("thickness_mm", 3))
    fillet = float(params.get("fillet_mm", 0))
    chamfer = float(params.get("chamfer_mm", 0))

    outer = cq.Workplane("XY").box(L, W, H)
    inner = cq.Workplane("XY").box(max(L-2*T, 0.1), max(W-2*T, 0.1), max(H- T, 0.1)).translate((0,0,T/2))
    part = outer.cut(inner)

    if fillet > 0:
        part = part.edges("|Z").fillet(fillet)
    if chamfer > 0:
        part = part.edges("|Z").chamfer(chamfer)

    return part

def apply_text(part: cq.Workplane, txt: dict):
    if not txt or not txt.get("value"):
        return part
    value = str(txt["value"])[:64]
    height = float(txt.get("height_mm", 8))
    depth = float(txt.get("depth_mm", 0.6))
    mode = txt.get("mode", "engrave")  # engrave|emboss

    face = part.faces(">Z").workplane()
    text_solid = face.text(value, height, depth, cut=(mode=="engrave"), combine=True, font=txt.get("font","Sans"))
    return part if text_solid is None else part
