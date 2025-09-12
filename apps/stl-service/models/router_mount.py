import cadquery as cq

def build(width=120, depth=60, lip=6):
    base = cq.Workplane("XY").rect(width, depth).extrude(3)
    wall = cq.Workplane("XY").rect(width, 3).extrude(depth).translate((0, (depth/2)-1.5, 0))
    lip_solid = cq.Workplane("XY").rect(width, lip).extrude(20).translate((0, -(depth/2)+lip/2, 10))
    return base.union(wall).union(lip_solid)
