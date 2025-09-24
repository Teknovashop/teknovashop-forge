# apps/stl-service/models/vesa_shelf.py
import cadquery as cq

DEFAULTS = {
    "vesa": 100,            # 75 / 100 / 200
    "thickness": 4.0,
    "shelf_width": 180.0,   # mm
    "shelf_depth": 120.0,
    "lip_height": 15.0,     # pestaña frontal anti-caída
    "rib_count": 3,         # refuerzos
    "hole_d": 5.0,
    "qr_enabled": True,     # quick-release simple
    "qr_slot_w": 18.0,
    "qr_slot_h": 6.0,
    "qr_offset_y": 12.0
}

def build(params):
    p = {**DEFAULTS, **(params or {})}
    t = p["thickness"]

    # placa VESA trasera
    back = cq.Workplane("XY").rect(p["vesa"] + 40, p["vesa"] + 40).extrude(t)

    # taladros VESA
    pitch = p["vesa"]
    for dx in (-pitch/2, pitch/2):
        for dy in (-pitch/2, pitch/2):
            back = back.faces(">Z").workplane().pushPoints([(dx, dy)]).hole(p["hole_d"])

    # Estante (sale hacia -Y)
    shelf = (cq.Workplane("XY")
             .center(0, -(p["vesa"]/2 + t))
             .rect(p["shelf_width"], p["shelf_depth"])
             .extrude(t))

    # Labio frontal
    lip = (cq.Workplane("XY")
           .center(0, -(p["vesa"]/2 + t + p["shelf_depth"]))
           .rect(p["shelf_width"], t)
           .extrude(p["lip_height"]))

    # Refuerzos (ribs)
    ribs = cq.Workplane("XY")
    if p["rib_count"] > 0:
        step = p["shelf_width"] / (p["rib_count"] + 1)
        xs = [(-p["shelf_width"]/2 + step * (i+1)) for i in range(p["rib_count"])]
        for x in xs:
            rib = (cq.Workplane("YZ")
                   .center(-(p["vesa"]/2 + t/2), x)
                   .rect(p["shelf_depth"], t).extrude(t))
            ribs = ribs.union(rib)

    model = back.union(shelf).union(lip).union(ribs)

    # Quick-release (ranura simple en placa)
    if p["qr_enabled"]:
        slot_w = p["qr_slot_w"]; slot_h = p["qr_slot_h"]
        model = (model.faces(">Z").workplane(centerOption="CenterOfMass")
                 .center(0, p["qr_offset_y"])
                 .slot2D(slot_w, slot_h, 0)
                 .cutThruAll())

    return model
