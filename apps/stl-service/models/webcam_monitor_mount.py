from __future__ import annotations
import math, trimesh

def build(p):
    width=float(p.get("width",55)); depth=float(p.get("depth",45)); back=float(p.get("back",35)); wall=float(p.get("wall",4)); angle=float(p.get("angle_deg",10))
    top=trimesh.creation.box(extents=(width,depth,wall)); top.apply_translation((0,0,wall/2))
    rear=trimesh.creation.box(extents=(width,wall,back)); rear.apply_translation((0,depth/2-wall/2,-back/2+wall))
    pad=trimesh.creation.box(extents=(width*0.72,depth*0.55,wall*1.4))
    pad.apply_transform(trimesh.transformations.rotation_matrix(math.radians(angle),[1,0,0]))
    pad.apply_translation((0,-depth*0.22,wall*1.4))
    return trimesh.util.concatenate([top,rear,pad])
BUILDER=build
