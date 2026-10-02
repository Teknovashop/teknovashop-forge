from __future__ import annotations
import trimesh

def build(p):
    length=float(p.get("length",180)); depth=float(p.get("depth",90)); wall=float(p.get("wall",4)); slot=float(p.get("slot",24)); height=float(p.get("height",65))
    base=trimesh.creation.box(extents=(length,depth,wall)); base.apply_translation((0,0,wall/2))
    x=(slot/2)+(wall/2)
    left=trimesh.creation.box(extents=(wall,depth*0.78,height)); left.apply_translation((-x,0,height/2))
    right=trimesh.creation.box(extents=(wall,depth*0.78,height)); right.apply_translation((x,0,height/2))
    return trimesh.util.concatenate([base,left,right])
BUILDER=build
