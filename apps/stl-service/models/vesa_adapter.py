import cadquery as cq

def build(width=180, height=180, thickness=6, pattern='100x100'):
    plate = cq.Workplane("XY").rect(width, height).extrude(thickness)
    mapping = {'75x75':75, '100x100':100, '200x200':200}
    pitch = mapping.get(pattern, 100)
    for (x,y) in [(-pitch/2,-pitch/2),(pitch/2,-pitch/2),(-pitch/2,pitch/2),(pitch/2,pitch/2)]:
        plate = plate.faces('>Z').workplane().pushPoints([(x,y)]).hole(5)
    plate = plate.edges('|Z').chamfer(1)
    return plate
