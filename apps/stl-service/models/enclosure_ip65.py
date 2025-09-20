import trimesh as tm

def make_model(p: dict) -> tm.Trimesh:
    # params: length,width,height, wall, pcb_grid_mm (opcional), holes:[]
    L = float(p.get("length", 201))
    W = float(p.get("width", 68))
    H = float(p.get("height", 31))
    wall = float(p.get("wall", 5))

    outer = tm.creation.box((L, H, W))
    outer.apply_translation((L/2, H/2, W/2))

    inner = tm.creation.box((L-2*wall, H-2*wall, W-2*wall))
    inner.apply_translation((L/2, H/2, W/2))

    body = outer.difference(inner, engine="scad" if tm.interfaces.solid.is_available() else None)

    # taladros libres (pasantes)
    holes = p.get("holes") or []
    for h in holes:
        d = float(h.get("d_mm", 5))
        x = float(h.get("x_mm", 0))
        z = float(h.get("z_mm", 0))
        c = tm.creation.cylinder(radius=max(0.1, d/2), height=H*3, sections=32)
        c.apply_translation((x+L/2, H*1.5, z+W/2))
        body = body.difference(c, engine="scad" if tm.interfaces.solid.is_available() else None)

    return body
