from __future__ import annotations
import trimesh

def build(p):
    width=float(p.get("width",120)); height=float(p.get("height",90)); thickness=float(p.get("thickness",5)); rail=float(p.get("rail",10))
    plate=trimesh.creation.box(extents=(width,height,thickness)); plate.apply_translation((0,0,thickness/2))
    top=trimesh.creation.box(extents=(width,rail,thickness*1.6)); top.apply_translation((0,height/2-rail/2,thickness*0.8))
    bottom=trimesh.creation.box(extents=(width,rail,thickness*1.6)); bottom.apply_translation((0,-height/2+rail/2,thickness*0.8))
    return trimesh.util.concatenate([plate,top,bottom])
BUILDER=build
