from __future__ import annotations
import trimesh

def build(p):
    length=float(p.get("length",240)); width=float(p.get("width",55)); height=float(p.get("height",35)); wall=float(p.get("wall",3))
    base=trimesh.creation.box(extents=(length,width,wall)); base.apply_translation((0,0,wall/2))
    a=trimesh.creation.box(extents=(length,wall,height)); a.apply_translation((0,-width/2+wall/2,height/2))
    b=trimesh.creation.box(extents=(length,wall,height)); b.apply_translation((0,width/2-wall/2,height/2))
    return trimesh.util.concatenate([base,a,b])
BUILDER=build
