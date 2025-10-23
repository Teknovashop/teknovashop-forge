# apps/stl-service/models/wall_hook.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import trimesh

NAME  = "wall_hook"
SLUGS = ["wall-hook", "wall-bracket-hook"]

DEFAULTS: Dict[str, float] = {
    "base_w": 40.0,
    "base_h": 60.0,
    "wall": 3.5,          # grosor de placa
    "hook_depth": 35.0,   # cuanto sobresale el gancho
    "hook_height": 35.0,  # altura del labio
    "hook_t": 8.0,        # grosor del gancho (sección)
    "hole_d": 4.5,
    "hole_off": 12.0,     # separación a bordes
}

def _num(p: Dict[str, Any], k: str, fb: float) -> float:
    try:
        return float(str(p.get(k, fb)).replace(",", "."))
    except Exception:
        return fb

def _holes_grid(w: float, h: float, off: float, d: float) -> List[Tuple[float,float,float]]:
    # 2 agujeros en vertical (centrados en X)
    return [(0.0,  h*0.5 - off, d), (0.0, -h*0.5 + off, d)]

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    bw = _num(params, "base_w",       DEFAULTS["base_w"])
    bh = _num(params, "base_h",       DEFAULTS["base_h"])
    t  = _num(params, "wall",         DEFAULTS["wall"])
    gd = _num(params, "hook_depth",   DEFAULTS["hook_depth"])
    gh = _num(params, "hook_height",  DEFAULTS["hook_height"])
    gt = _num(params, "hook_t",       DEFAULTS["hook_t"])
    hd = _num(params, "hole_d",       DEFAULTS["hole_d"])
    off= _num(params, "hole_off",     DEFAULTS["hole_off"])

    # Placa base con agujeros
    plate = trimesh.creation.box(extents=(bw, bh, t))
    holes = _holes_grid(bw, bh, off, hd)
    cutters: List[trimesh.Trimesh] = []
    for (x, y, d) in holes:
        c = trimesh.creation.cylinder(radius=d*0.5, height=t*1.4, sections=72)
        c.apply_translation((x, y, 0.0))
        cutters.append(c)
    if cutters:
        cutter = trimesh.util.concatenate(cutters)
        engine = "scad" if getattr(trimesh.interfaces.scad, "exists", False) else None
        diff = plate.difference(cutter, engine=engine)
        plate = diff if isinstance(diff, trimesh.Trimesh) else plate

    # Gancho en forma de "L": brazo + labio (misma altura Z=t)
    arm  = trimesh.creation.box(extents=(gd, gt, t))
    lip  = trimesh.creation.box(extents=(gt, gh, t))

    # Colocación (plano X-Y es la placa; el gancho sale hacia +X)
    arm.apply_translation(( bw/2 + gd/2, -bh/2 + gt/2 + 2.0, 0.0))
    lip.apply_translation(( bw/2 + gd - gt/2, -bh/2 + gh/2 + 2.0, 0.0))

    return trimesh.util.concatenate([plate, arm, lip])

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make}
__all__ = ["NAME", "SLUGS", "DEFAULTS", "make", "make_model", "BUILD"]
