from __future__ import annotations
import trimesh

def build(p):
    width=float(p.get("width",190)); depth=float(p.get("depth",105)); height=float(p.get("height",55)); wall=float(p.get("wall",4)); slots=int(round(float(p.get("slots",3))))
    slots=max(2,min(slots,5))
    base=trimesh.creation.box(extents=(width,depth,wall)); base.apply_translation((0,0,wall/2))
    parts=[base]
    for i in range(slots+1):
        x=-width/2 + i*(width/slots)
        divider=trimesh.creation.box(extents=(wall,depth*0.75,height)); divider.apply_translation((x,0,height/2))
        parts.append(divider)
    return trimesh.util.concatenate(parts)
BUILDER=build
