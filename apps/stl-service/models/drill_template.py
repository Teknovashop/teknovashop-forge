from __future__ import annotations
import trimesh

def build(p):
    length=float(p.get("length",160)); width=float(p.get("width",45)); thickness=float(p.get("thickness",6)); hole_d=float(p.get("hole_d",5)); spacing=float(p.get("spacing",32))
    plate=trimesh.creation.box(extents=(length,width,thickness)); plate.apply_translation((0,0,thickness/2))
    count=max(2,int((length-20)//spacing)+1)
    cutters=[]
    start=-(count-1)*spacing/2
    for i in range(count):
        c=trimesh.creation.cylinder(radius=hole_d/2,height=thickness*3,sections=48); c.apply_translation((start+i*spacing,0,thickness/2)); cutters.append(c)
    result=plate
    for c in cutters:
        result=trimesh.boolean.difference([result,c],engine="manifold")
    return result
BUILDER=build
