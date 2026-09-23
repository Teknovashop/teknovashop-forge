from __future__ import annotations
from typing import Dict, Any, List
import math
import trimesh

NAME = "go_pro_mount"
SLUGS = ["go-pro-mount", "gopro-mount"]

DEFAULTS = {
    "fork_pitch": 17.5,
    "ear_t": 3.2,
    "hole_d": 5.2,
    "base_w": 30.0,
    "base_l": 35.0,
    "wall": 3.0,
    "finger_h": 18.0,
}

def _num(p: Dict[str, Any], key: str, default: float) -> float:
    try:
        return float(str(p.get(key, default)).replace(",", "."))
    except Exception:
        return float(default)

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    base_w = max(24.0, _num(params, "base_w", DEFAULTS["base_w"]))
    base_l = max(28.0, _num(params, "base_l", DEFAULTS["base_l"]))
    base_t = max(2.4, _num(params, "wall", DEFAULTS["wall"]))
    ear_t = max(2.4, _num(params, "ear_t", DEFAULTS["ear_t"]))
    hole_d = max(4.5, _num(params, "hole_d", DEFAULTS["hole_d"]))
    pitch = max(14.0, _num(params, "fork_pitch", DEFAULTS["fork_pitch"]))
    finger_h = max(14.0, _num(params, "finger_h", DEFAULTS["finger_h"]))

    base = trimesh.creation.box(extents=(base_w, base_l, base_t))
    base.apply_translation((0, 0, base_t / 2))

    # Tres dedos reconocibles estilo GoPro, separados en X.
    gap = max(2.4, (pitch - 3 * ear_t) / 2.0)
    centers = [-(ear_t + gap), 0.0, +(ear_t + gap)]
    fingers: List[trimesh.Trimesh] = []

    for x in centers:
        finger = trimesh.creation.box(extents=(ear_t, base_l * 0.42, finger_h))
        finger.apply_translation((x, 0, base_t + finger_h / 2))

        pin = trimesh.creation.cylinder(radius=hole_d / 2, height=ear_t * 1.8, sections=72)
        pin.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
        pin.apply_translation((x, 0, base_t + finger_h * 0.68))
        try:
            cut = finger.difference(pin)
            finger = cut if isinstance(cut, trimesh.Trimesh) else finger
        except Exception:
            pass
        fingers.append(finger)

    mesh = trimesh.util.concatenate([base] + fingers)
    mesh.metadata = {"name": "go_pro_mount", "unit": "mm"}
    return mesh

BUILD = {"make": make}
