from __future__ import annotations
import trimesh

def build(p):
    length=float(p.get("length",130)); width=float(p.get("width",85)); height=float(p.get("height",45)); wall=float(p.get("wall",3)); lid=float(p.get("lid",3))
    floor=trimesh.creation.box(extents=(length,width,wall)); floor.apply_translation((0,0,wall/2))
    left=trimesh.creation.box(extents=(wall,width,height)); left.apply_translation((-length/2+wall/2,0,height/2))
    right=trimesh.creation.box(extents=(wall,width,height)); right.apply_translation((length/2-wall/2,0,height/2))
    front=trimesh.creation.box(extents=(length,wall,height)); front.apply_translation((0,-width/2+wall/2,height/2))
    back=trimesh.creation.box(extents=(length,wall,height)); back.apply_translation((0,width/2-wall/2,height/2))
    cover=trimesh.creation.box(extents=(length+wall,width+wall,lid)); cover.apply_translation((0,0,height+lid/2+2))
    return trimesh.util.concatenate([floor,left,right,front,back,cover])
BUILDER=build
