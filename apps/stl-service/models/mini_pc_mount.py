from __future__ import annotations
import trimesh

def build(p):
    width=float(p.get("width",130)); depth=float(p.get("depth",125)); height=float(p.get("height",45)); wall=float(p.get("wall",4)); lip=float(p.get("lip",16))
    base=trimesh.creation.box(extents=(width,depth,wall)); base.apply_translation((0,0,wall/2))
    left=trimesh.creation.box(extents=(wall,depth,height)); left.apply_translation((-width/2+wall/2,0,height/2))
    right=trimesh.creation.box(extents=(wall,depth,height)); right.apply_translation((width/2-wall/2,0,height/2))
    front=trimesh.creation.box(extents=(width,wall,lip)); front.apply_translation((0,-depth/2+wall/2,lip/2))
    return trimesh.util.concatenate([base,left,right,front])
BUILDER=build
