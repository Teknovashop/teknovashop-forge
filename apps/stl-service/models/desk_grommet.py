from __future__ import annotations
import trimesh

def build(p):
    outer_d=float(p.get("outer_d",65)); inner_d=float(p.get("inner_d",50)); height=float(p.get("height",18)); flange=float(p.get("flange",4))
    outer=trimesh.creation.cylinder(radius=outer_d/2,height=height,sections=72); outer.apply_translation((0,0,height/2))
    inner=trimesh.creation.cylinder(radius=inner_d/2,height=height*2,sections=72); inner.apply_translation((0,0,height/2))
    ring=trimesh.boolean.difference([outer,inner],engine="manifold")
    fl=trimesh.creation.cylinder(radius=(outer_d+flange*2)/2,height=flange,sections=72); fl.apply_translation((0,0,flange/2))
    fl_inner=trimesh.creation.cylinder(radius=inner_d/2,height=flange*3,sections=72); fl_inner.apply_translation((0,0,flange/2))
    flange_mesh=trimesh.boolean.difference([fl,fl_inner],engine="manifold")
    return trimesh.util.concatenate([ring,flange_mesh])
BUILDER=build
