from __future__ import annotations
import trimesh

def build(p):
    width=float(p.get("width",180)); depth=float(p.get("depth",95)); height=float(p.get("height",42)); wall=float(p.get("wall",4)); front_lip=float(p.get("front_lip",12))
    base=trimesh.creation.box(extents=(width,depth,wall)); base.apply_translation((0,0,wall/2))
    l=trimesh.creation.box(extents=(wall,depth,height)); l.apply_translation((-width/2+wall/2,0,height/2))
    r=trimesh.creation.box(extents=(wall,depth,height)); r.apply_translation((width/2-wall/2,0,height/2))
    f=trimesh.creation.box(extents=(width,wall,front_lip)); f.apply_translation((0,-depth/2+wall/2,front_lip/2))
    return trimesh.util.concatenate([base,l,r,f])
BUILDER=build
