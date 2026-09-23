from __future__ import annotations
from typing import Dict, Any, List, Tuple
import trimesh

NAME = "raspi_case"
SLUGS = ["raspi-case", "raspberry-pi-4-case"]

DEFAULTS = {
    "board_w": 85.0,
    "board_l": 56.0,
    "board_h": 17.0,
    "port_clear": 1.0,
    "wall": 2.2,
    "bottom": 2.4,
    "lid_t": 2.2,
    "standoff_h": 4.0,
}

def _num(p: Dict[str, Any], key: str, default: float) -> float:
    try:
        return float(str(p.get(key, default)).replace(",", "."))
    except Exception:
        return float(default)

def _safe_difference(base: trimesh.Trimesh, cutter: trimesh.Trimesh) -> trimesh.Trimesh:
    try:
        out = base.difference(cutter)
        if isinstance(out, trimesh.Trimesh):
            return out
    except Exception:
        pass
    return base

def _standoff(x: float, y: float, z0: float, h: float) -> trimesh.Trimesh:
    outer = trimesh.creation.cylinder(radius=3.2, height=h, sections=64)
    outer.apply_translation((x, y, z0 + h / 2))
    inner = trimesh.creation.cylinder(radius=1.45, height=h * 1.6, sections=64)
    inner.apply_translation((x, y, z0 + h / 2))
    return _safe_difference(outer, inner)

def make(params: Dict[str, Any]) -> trimesh.Trimesh:
    # Raspberry Pi 4 Model B nominal PCB envelope: 85 x 56 mm.
    # Defaults intentionally match the official mechanical specification.
    board_l = max(80.0, _num(params, "board_w", DEFAULTS["board_w"]))
    board_w = max(50.0, _num(params, "board_l", DEFAULTS["board_l"]))
    board_h = max(12.0, _num(params, "board_h", DEFAULTS["board_h"]))
    clear = max(0.5, _num(params, "port_clear", DEFAULTS["port_clear"]))
    wall = max(1.8, _num(params, "wall", DEFAULTS["wall"]))
    bottom_t = max(1.8, _num(params, "bottom", DEFAULTS["bottom"]))
    lid_t = max(1.8, _num(params, "lid_t", DEFAULTS["lid_t"]))
    standoff_h = max(2.5, _num(params, "standoff_h", DEFAULTS["standoff_h"]))

    inner_l = board_l + 2 * clear
    inner_w = board_w + 2 * clear
    case_h = board_h + standoff_h + 5.0
    outer_l = inner_l + 2 * wall
    outer_w = inner_w + 2 * wall

    outer = trimesh.creation.box(extents=(outer_l, outer_w, case_h))
    outer.apply_translation((0, 0, case_h / 2))

    inner = trimesh.creation.box(
        extents=(inner_l, inner_w, case_h - bottom_t + wall)
    )
    inner.apply_translation((0, 0, bottom_t + (case_h - bottom_t + wall) / 2))
    shell = _safe_difference(outer, inner)

    # Two large connector windows: USB/Ethernet side and HDMI/power side.
    io_short = trimesh.creation.box(
        extents=(wall * 3.0, min(39.0 + clear * 2, outer_w - 2 * wall), 18.0)
    )
    io_short.apply_translation((outer_l / 2, 3.0, bottom_t + standoff_h + 8.5))
    shell = _safe_difference(shell, io_short)

    io_long = trimesh.creation.box(
        extents=(min(43.0 + clear * 2, outer_l - 2 * wall), wall * 3.0, 12.5)
    )
    io_long.apply_translation((-9.0, -outer_w / 2, bottom_t + standoff_h + 6.0))
    shell = _safe_difference(shell, io_long)

    # Four Raspberry Pi mounting bosses. For Pi 4 the official mechanical
    # pattern is 58 x 49 mm; the left pair is 3.5 mm from the PCB edges.
    x0 = -board_l / 2 + 3.5
    y0 = -board_w / 2 + 3.5
    hole_positions: List[Tuple[float, float]] = [
        (x0, y0),
        (x0 + 58.0, y0),
        (x0, y0 + 49.0),
        (x0 + 58.0, y0 + 49.0),
    ]
    standoffs = [
        _standoff(x, y, bottom_t, standoff_h)
        for x, y in hole_positions
    ]

    # Ventilated removable lid, shown separated above the enclosure.
    lid_z = case_h + 3.0
    lid = trimesh.creation.box(extents=(outer_l, outer_w, lid_t))
    lid.apply_translation((0, 0, lid_z + lid_t / 2))

    # Five longitudinal vent slots.
    for x in (-24.0, -12.0, 0.0, 12.0, 24.0):
        if abs(x) + 7.0 >= outer_l / 2:
            continue
        vent = trimesh.creation.box(
            extents=(5.0, max(20.0, outer_w * 0.55), lid_t * 2.2)
        )
        vent.apply_translation((x, 0, lid_z + lid_t / 2))
        lid = _safe_difference(lid, vent)

    # Inner lip that centres the lid.
    lip_outer = trimesh.creation.box(
        extents=(outer_l - wall, outer_w - wall, wall)
    )
    lip_inner = trimesh.creation.box(
        extents=(inner_l - wall * 0.5, inner_w - wall * 0.5, wall * 1.5)
    )
    lip = _safe_difference(lip_outer, lip_inner)
    lip.apply_translation((0, 0, lid_z - wall / 2))

    mesh = trimesh.util.concatenate([shell, *standoffs, lid, lip])
    mesh.metadata = {
        "name": "raspberry_pi_4_model_b_case",
        "unit": "mm",
        "board_nominal_mm": [85.0, 56.0],
        "mounting_pattern_mm": [58.0, 49.0],
    }
    return mesh

def make_model(params: Dict[str, Any]) -> trimesh.Trimesh:
    return make(params)

BUILD = {"make": make, "build": make_model}
