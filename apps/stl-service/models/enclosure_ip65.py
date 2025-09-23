# apps/stl-service/models/enclosure_ip65.py
from typing import Dict, Any
import trimesh

NAME = "enclosure_ip65"

TYPES = {
    "length": "float",
    "width": "float",
    "height": "float",
    "wall": "float",
    "holes": "list[]",  # por ahora ignorados (solidez primero). Se pueden taladrar más tarde.
}

DEFAULTS = {
    "length": 120.0,
    "width": 68.0,
    "height": 45.0,
    "wall": 3.0,
    "holes": [],
}

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    L = float(params.get("length", DEFAULTS["length"]))
    W = float(params.get("width", DEFAULTS["width"]))
    H = float(params.get("height", DEFAULTS["height"]))
    # Caja sólida estable (sin CSG), apoyada en Y=0
    box = trimesh.creation.box(extents=(L, H, W))
    box.apply_translation((0, H / 2.0, 0))
    return box
