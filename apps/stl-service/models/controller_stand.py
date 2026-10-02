from __future__ import annotations
import math, trimesh

def build(p):
    width=float(p.get("width",95)); depth=float(p.get("depth",110)); height=float(p.get("height",85)); wall=float(p.get("wall",5)); angle=float(p.get("angle_deg",28))
    base=trimesh.creation.box(extents=(width,depth,wall)); base.apply_translation((0,0,wall/2))
    spine=trimesh.creation.box(extents=(width*0.7,wall,height)); spine.apply_translation((0,depth*0.2,height/2))
    cradle=trimesh.creation.box(extents=(width*0.78,depth*0.5,wall))
    cradle.apply_transform(trimesh.transformations.rotation_matrix(math.radians(angle),[1,0,0]))
    cradle.apply_translation((0,-depth*0.12,height*0.55))
    return trimesh.util.concatenate([base,spine,cradle])
BUILDER=build
