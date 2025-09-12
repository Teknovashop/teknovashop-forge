import cadquery as cq

def build(length=300, width=60, height=40):
    tray = cq.Workplane("XY").rect(length, width).extrude(2)
    side = cq.Workplane("XY").rect(length, 2).extrude(height)
    side_r = side.translate((0, (width/2)-1, 0))
    side_l = side.mirror('YZ').translate((0, -(width/2)+1, 0))
    return tray.union(side_r).union(side_l)
