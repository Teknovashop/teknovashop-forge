from __future__ import annotations
import trimesh

def build(p):
    length=float(p.get("length",220)); height=float(p.get("height",55)); thickness=float(p.get("thickness",3)); foot=float(p.get("foot",14))
    wall=trimesh.creation.box(extents=(length,thickness,height)); wall.apply_translation((0,0,height/2))
    base=trimesh.creation.box(extents=(length,foot,thickness)); base.apply_translation((0,0,thickness/2))
    return trimesh.util.concatenate([wall,base])
BUILDER=build
