from __future__ import annotations

from typing import Dict, Any
import math
import trimesh

NAME = "laptop_stand"
SLUGS = ["laptop-stand", "tablet-stand", "soporte-portatil"]

DEFAULTS = {
    "width": 260.0,
    "depth": 240.0,
    "angle_deg": 18.0,
    "lip_h": 8.0,
    "vent_slot": 12.0,
    "wall": 4.0,
}

def _num(p: Dict[str, Any], key: str, default: float, *aliases: str) -> float:
    for k in (key, *aliases):
        if k in p and p[k] is not None:
            try:
                return float(str(p[k]).replace(",", "."))
            except Exception:
                pass
    return float(default)

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    width = max(180.0, _num(params, "width", DEFAULTS["width"], "length_mm"))
    depth = max(140.0, _num(params, "depth", DEFAULTS["depth"], "width_mm"))
    angle_deg = min(35.0, max(8.0, _num(params, "angle_deg", DEFAULTS["angle_deg"])))
    lip_h = max(5.0, _num(params, "lip_h", DEFAULTS["lip_h"]))
    vent_slot = max(6.0, min(width * 0.5, _num(params, "vent_slot", DEFAULTS["vent_slot"])))
    wall = max(2.5, _num(params, "wall", DEFAULTS["wall"], "thickness_mm"))

    angle = math.radians(angle_deg)
    horizontal_depth = depth * math.cos(angle)
    rise = depth * math.sin(angle)

    panel_width = max(25.0, (width - vent_slot) / 2.0)

    def sloped_panel(x_center: float) -> trimesh.Trimesh:
        panel = trimesh.creation.box(extents=(panel_width, wall, depth))
        panel.apply_transform(
            trimesh.transformations.rotation_matrix(-angle, [1, 0, 0])
        )
        panel.apply_translation((x_center, wall / 2 + rise / 2, 0.0))
        return panel

    x_offset = vent_slot / 2 + panel_width / 2
    left = sloped_panel(-x_offset)
    right = sloped_panel(+x_offset)

    # Base trasera al suelo: estabiliza el soporte.
    rear_base = trimesh.creation.box(extents=(width, max(18.0, wall * 5), wall))
    rear_base.apply_translation((0.0, wall / 2, horizontal_depth / 2 - wall))

    # Dos patas posteriores soportan la elevación.
    leg_h = max(15.0, rise)
    leg_w = max(14.0, wall * 4)
    legs = []
    for x in (-width / 2 + leg_w / 2, width / 2 - leg_w / 2):
        leg = trimesh.creation.box(extents=(leg_w, leg_h, wall * 2.0))
        leg.apply_translation((x, leg_h / 2, horizontal_depth / 2 - wall))
        legs.append(leg)

    # Labio frontal para impedir deslizamiento del equipo.
    lip = trimesh.creation.box(extents=(width, lip_h, wall))
    lip.apply_translation((0.0, lip_h / 2, -horizontal_depth / 2 - wall / 2))

    # Traviesas frontal/trasera sobre el plano inclinado.
    cross_front = trimesh.creation.box(extents=(width, wall, wall * 2.0))
    cross_front.apply_translation((0.0, wall, -horizontal_depth / 2 + wall))
    cross_rear = trimesh.creation.box(extents=(width, wall, wall * 2.0))
    cross_rear.apply_translation((0.0, rise, horizontal_depth / 2 - wall))

    mesh = trimesh.util.concatenate(
        [left, right, rear_base, *legs, lip, cross_front, cross_rear]
    )
    mesh.metadata = {
        "name": "laptop_stand",
        "unit": "mm",
        "angle_deg": angle_deg,
        "vent_slot_mm": vent_slot,
    }
    return mesh

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make_model(params)

BUILD = {"make": make, "build": make_model}
