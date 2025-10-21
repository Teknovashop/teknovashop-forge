# apps/stl-service/models/monitor_stand.py
from __future__ import annotations
from typing import Dict, Any
import trimesh

NAME = "monitor_stand"

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    # UI: width, depth, height, wall
    w = float(params.get("width", 400))
    d = float(params.get("depth", 200))
    h = float(params.get("height", 70))
    t = float(params.get("wall", 4))

    top = trimesh.creation.box(extents=(w, d, t))
    top.apply_translation((0, 0, h + t/2))

    leg_w = t * 2
    leg = trimesh.creation.box(extents=(leg_w, d, h))
    left_leg = leg.copy()
    left_leg.apply_translation((-w/2 + leg_w/2, 0, h/2))
    right_leg = leg.copy()
    right_leg.apply_translation((w/2 - leg_w/2, 0, h/2))

    return trimesh.util.concatenate([top, left_leg, right_leg])

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make}
__all__ = ["NAME", "make_model", "make", "BUILD"]
