from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

import numpy as np
import trimesh

PILOT_CAPABILITIES = {
    "cable-tray": {"hole", "slot", "cutout_rect", "cutout_circle", "counterbore", "pocket_rect", "hole_pattern", "vent_linear", "vent_hex", "scallop_pattern", "rib", "boss", "wave_ribs", "cable_channel"},
    "vesa-adapter": {"hole", "slot", "cutout_rect", "cutout_circle", "counterbore", "pocket_rect", "hole_pattern", "vesa_pattern", "scallop_pattern", "rib", "boss", "wave_ribs"},
    "enclosure-ip65": {"hole", "slot", "cutout_rect", "cutout_circle", "counterbore", "hole_pattern", "vent_linear", "vent_hex", "rib", "wave_ribs", "cable_channel"},
}


@dataclass
class ValidationIssue:
    code: str
    message: str
    level: str = "error"

    def as_dict(self) -> Dict[str, str]:
        return {"code": self.code, "message": self.message, "level": self.level}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if np.isfinite(out) else default


def _op_type(op: Dict[str, Any]) -> str:
    return str(op.get("type") or "").strip().lower()


def validate_operations(slug: str, operations: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    allowed = PILOT_CAPABILITIES.get(slug, set())
    issues: List[ValidationIssue] = []
    ops = list(operations or [])

    if len(ops) > 24:
        issues.append(ValidationIssue("too_many_operations", "Máximo 24 operaciones por diseño V2."))

    seen = set()
    for index, op in enumerate(ops):
        op_id = str(op.get("id") or "").strip()
        typ = _op_type(op)
        version = op.get("version", 1)

        if version != 1:
            issues.append(
                ValidationIssue(
                    "unsupported_operation_version",
                    f"{op_id or index + 1}: versión de operación no soportada.",
                )
            )

        if not op_id:
            issues.append(ValidationIssue("missing_id", f"Operación {index + 1}: falta id."))
        elif op_id in seen:
            issues.append(ValidationIssue("duplicate_id", f"Operación {op_id}: id duplicado."))
        else:
            seen.add(op_id)

        if typ not in allowed:
            issues.append(
                ValidationIssue(
                    "unsupported_operation",
                    f"{slug}: la operación '{typ or 'desconocida'}' no está habilitada.",
                )
            )
            continue

        params = op.get("params") or {}
        if typ == "hole":
            d = _num(params.get("diameter_mm"), 0)
            if d < 2 or d > 40:
                issues.append(ValidationIssue("hole_diameter", f"{op_id}: diámetro permitido 2–40 mm."))
        elif typ == "slot":
            length = _num(params.get("length_mm"), 0)
            width = _num(params.get("width_mm"), 0)
            if length < 4 or width < 2 or length < width:
                issues.append(ValidationIssue("slot_size", f"{op_id}: ranura inválida."))
        elif typ == "cutout_rect":
            width = _num(params.get("width_mm"), 0)
            height = _num(params.get("height_mm"), 0)
            if width < 2 or height < 2:
                issues.append(ValidationIssue("cutout_size", f"{op_id}: corte rectangular inválido."))
        elif typ == "cutout_circle":
            d = _num(params.get("diameter_mm"), 0)
            if d < 4 or d > 90:
                issues.append(ValidationIssue("cutout_circle", f"{op_id}: diámetro permitido 4–90 mm."))
        elif typ == "counterbore":
            through_d = _num(params.get("through_diameter_mm"), 0)
            bore_d = _num(params.get("bore_diameter_mm"), 0)
            bore_depth = _num(params.get("bore_depth_mm"), 0)
            if through_d < 2 or through_d > 20 or bore_d <= through_d or bore_d > 45 or bore_depth < 0.5 or bore_depth > 12:
                issues.append(ValidationIssue("counterbore", f"{op_id}: rebaje cilíndrico inválido."))

        elif typ == "pocket_rect":
            width = _num(params.get("width_mm"), 0)
            height = _num(params.get("height_mm"), 0)
            pocket_depth = _num(params.get("depth_mm"), 0)
            if width < 4 or height < 4 or pocket_depth < 0.4 or pocket_depth > 12:
                issues.append(ValidationIssue("pocket_rect", f"{op_id}: rebaje rectangular inválido."))
        elif typ == "pocket_rect":
            width = _num(params.get("width_mm"))
            height = _num(params.get("height_mm"))
            pocket_depth = _num(params.get("depth_mm"))
            if not _fits_xy(out, x, y, width / 2, height / 2):
                raise ValueError(f"{op_id}: rebaje demasiado cerca del borde")
            target = (op.get("target") or {}).get("face", "top")
            lo_z = float(out.bounds[0][2])
            hi_z = float(out.bounds[1][2])
            shallow_h = pocket_depth + 0.6
            shallow_z = (hi_z - pocket_depth / 2 + 0.3) if target == "top" else (lo_z + pocket_depth / 2 - 0.3)
            cutter = trimesh.creation.box(extents=(width, height, shallow_h))
            cutter.apply_translation((x, y, shallow_z))
            out = _subtract(out, cutter, op_id)

        elif typ == "hole_pattern":
            d = _num(params.get("diameter_mm"), 0)
            rows = int(round(_num(params.get("rows"), 0)))
            cols = int(round(_num(params.get("cols"), 0)))
            sx = _num(params.get("spacing_x_mm"), 0)
            sy = _num(params.get("spacing_y_mm"), 0)
            if d < 2 or d > 24 or rows < 1 or cols < 1 or rows * cols > 24 or sx < d or sy < d:
                issues.append(ValidationIssue("hole_pattern", f"{op_id}: patrón de agujeros inválido."))
        elif typ == "vesa_pattern":
            pitch = _num(params.get("pitch_mm"), 0)
            d = _num(params.get("diameter_mm"), 0)
            if pitch not in {50.0, 75.0, 100.0, 200.0} or d < 3 or d > 10:
                issues.append(ValidationIssue("vesa_pattern", f"{op_id}: patrón VESA inválido."))
        elif typ == "vent_linear":
            count = int(round(_num(params.get("count"), 0)))
            length = _num(params.get("length_mm"), 0)
            width = _num(params.get("width_mm"), 0)
            spacing = _num(params.get("spacing_mm"), 0)
            if count < 2 or count > 16 or length < 6 or width < 2 or spacing < width:
                issues.append(ValidationIssue("vent_linear", f"{op_id}: ventilación lineal inválida."))
        elif typ == "scallop_pattern":
            count = int(round(_num(params.get("count"), 0)))
            diameter = _num(params.get("diameter_mm"), 0)
            spacing = _num(params.get("spacing_mm"), 0)
            if count < 2 or count > 12 or diameter < 3 or diameter > 24 or spacing < diameter * 0.5:
                issues.append(ValidationIssue("scallop_pattern", f"{op_id}: patrón de muescas inválido."))
        elif typ == "scallop_pattern":
            count = int(round(_num(params.get("count"))))
            diameter = _num(params.get("diameter_mm"))
            spacing = _num(params.get("spacing_mm"))
            rotation_deg = _num((op.get("placement") or {}).get("rotation_deg"), 0)
            total = (count - 1) * spacing + diameter
            if not _fits_xy(out, x, y, total / 2, diameter / 2):
                raise ValueError(f"{op_id}: patrón de muescas demasiado cerca del borde")
            cutters = []
            angle = np.radians(rotation_deg)
            for i in range(count):
                offset = (i - (count - 1) / 2) * spacing
                px = x + np.cos(angle) * offset
                py = y + np.sin(angle) * offset
                cutter = trimesh.creation.cylinder(radius=diameter / 2, height=depth, sections=48)
                cutter.apply_translation((px, py, z))
                cutters.append(cutter)
            for cutter in cutters:
                out = _subtract(out, cutter, op_id)

        elif typ == "vent_hex":
            rows = int(round(_num(params.get("rows"), 0)))
            cols = int(round(_num(params.get("cols"), 0)))
            radius = _num(params.get("radius_mm"), 0)
            gap = _num(params.get("gap_mm"), 0)
            if rows < 1 or cols < 1 or rows * cols > 30 or radius < 2 or radius > 12 or gap < 1:
                issues.append(ValidationIssue("vent_hex", f"{op_id}: rejilla hexagonal inválida."))
        elif typ == "rib":
            length = _num(params.get("length_mm"), 0)
            width = _num(params.get("width_mm"), 0)
            height = _num(params.get("height_mm"), 0)
            if length < 6 or width < 2 or height < 1 or height > 30:
                issues.append(ValidationIssue("rib_size", f"{op_id}: refuerzo inválido."))
        elif typ == "boss":
            diameter = _num(params.get("diameter_mm"), 0)
            height = _num(params.get("height_mm"), 0)
            if diameter < 4 or diameter > 40 or height < 1 or height > 30:
                issues.append(ValidationIssue("boss", f"{op_id}: boss cilíndrico inválido."))
        elif typ == "wave_ribs":
            length = _num(params.get("length_mm"), 0)
            rib_width = _num(params.get("rib_width_mm"), 0)
            amplitude = _num(params.get("amplitude_mm"), 0)
            count = int(round(_num(params.get("count"), 0)))
            spacing = _num(params.get("spacing_mm"), 0)
            if length < 10 or rib_width < 1 or rib_width > 8 or amplitude < 0.8 or amplitude > 12 or count < 3 or count > 14 or spacing < rib_width:
                issues.append(ValidationIssue("wave_ribs", f"{op_id}: ondulación/refuerzo inválido."))
        elif typ == "cable_channel":
            length = _num(params.get("length_mm"), 0)
            width = _num(params.get("width_mm"), 0)
            if length < 8 or width < 3:
                issues.append(ValidationIssue("cable_channel", f"{op_id}: canal de cable inválido."))

        target = (op.get("target") or {}).get("face", "top")
        if target not in {"top", "bottom"}:
            issues.append(
                ValidationIssue(
                    "target_face",
                    f"{op_id}: en la primera iteración V2 solo se permiten caras top/bottom.",
                )
            )

    return [issue.as_dict() for issue in issues]


def _through_height(mesh: trimesh.Trimesh) -> float:
    return max(float(mesh.extents[2]) * 3.0, 20.0)


def _placement_xy(mesh: trimesh.Trimesh, op: Dict[str, Any]) -> tuple[float, float]:
    placement = op.get("placement") or {}
    center = mesh.bounds.mean(axis=0)
    return (
        float(center[0]) + _num(placement.get("x"), 0),
        float(center[1]) + _num(placement.get("y"), 0),
    )


def _fits_xy(mesh: trimesh.Trimesh, x: float, y: float, half_w: float, half_h: float, margin: float = 1.2) -> bool:
    lo, hi = mesh.bounds
    return (
        x - half_w >= float(lo[0]) + margin
        and x + half_w <= float(hi[0]) - margin
        and y - half_h >= float(lo[1]) + margin
        and y + half_h <= float(hi[1]) - margin
    )


def _subtract(mesh: trimesh.Trimesh, cutter: trimesh.Trimesh, op_id: str) -> trimesh.Trimesh:
    try:
        # V2 never uses the legacy "concatenate on boolean failure" fallback.
        # A subtractive operation must be a real Manifold boolean or fail closed.
        result = trimesh.boolean.difference([mesh, cutter], engine="manifold")
    except Exception as exc:
        raise ValueError(f"{op_id}: boolean difference failed: {exc}") from exc

    if not isinstance(result, trimesh.Trimesh) or not len(result.faces):
        raise ValueError(f"{op_id}: la operación no produjo una malla válida")
    if not result.is_watertight or not result.is_winding_consistent:
        raise ValueError(f"{op_id}: la operación produciría una malla no estanca")
    return result


def _union(mesh: trimesh.Trimesh, addition: trimesh.Trimesh, op_id: str) -> trimesh.Trimesh:
    try:
        result = trimesh.boolean.union([mesh, addition], engine="manifold")
    except Exception as exc:
        raise ValueError(f"{op_id}: boolean union failed: {exc}") from exc

    if not isinstance(result, trimesh.Trimesh) or not len(result.faces):
        raise ValueError(f"{op_id}: el refuerzo no produjo una malla válida")
    if not result.is_watertight or not result.is_winding_consistent:
        raise ValueError(f"{op_id}: el refuerzo produciría una malla no estanca")
    return result


def _rotated_box(length: float, width: float, depth: float, rotation_deg: float) -> trimesh.Trimesh:
    box = trimesh.creation.box(extents=(length, width, depth))
    if rotation_deg:
        box.apply_transform(
            trimesh.transformations.rotation_matrix(np.deg2rad(rotation_deg), [0, 0, 1])
        )
    return box


def apply_operations(mesh: trimesh.Trimesh, slug: str, operations: Iterable[Dict[str, Any]]) -> trimesh.Trimesh:
    ops = [op for op in (operations or []) if op.get("enabled", True)]
    issues = validate_operations(slug, ops)
    if issues:
        raise ValueError("; ".join(issue["message"] for issue in issues))

    out = mesh.copy()
    for index, op in enumerate(ops):
        op_id = str(op.get("id") or f"op_{index + 1}")
        typ = _op_type(op)
        params = op.get("params") or {}
        x, y = _placement_xy(out, op)
        z = float(out.bounds.mean(axis=0)[2])
        depth = _through_height(out)

        if typ == "hole":
            d = _num(params.get("diameter_mm"))
            if not _fits_xy(out, x, y, d / 2, d / 2):
                raise ValueError(f"{op_id}: agujero demasiado cerca del borde")
            cutter = trimesh.creation.cylinder(radius=d / 2, height=depth, sections=48)
            cutter.apply_translation((x, y, z))
            out = _subtract(out, cutter, op_id)

        elif typ == "slot":
            length = _num(params.get("length_mm"))
            width = _num(params.get("width_mm"))
            rotation_deg = _num((op.get("placement") or {}).get("rotation_deg"), 0)
            if not _fits_xy(out, x, y, length / 2, width / 2):
                raise ValueError(f"{op_id}: ranura demasiado cerca del borde")
            cutter = trimesh.creation.box(extents=(length, width, depth))
            if rotation_deg:
                cutter.apply_transform(
                    trimesh.transformations.rotation_matrix(
                        np.deg2rad(rotation_deg), [0, 0, 1]
                    )
                )
            cutter.apply_translation((x, y, z))
            out = _subtract(out, cutter, op_id)

        elif typ == "cutout_rect":
            width = _num(params.get("width_mm"))
            height = _num(params.get("height_mm"))
            if not _fits_xy(out, x, y, width / 2, height / 2):
                raise ValueError(f"{op_id}: corte demasiado cerca del borde")
            cutter = trimesh.creation.box(extents=(width, height, depth))
            cutter.apply_translation((x, y, z))
            out = _subtract(out, cutter, op_id)

        elif typ == "cutout_circle":
            d = _num(params.get("diameter_mm"))
            if not _fits_xy(out, x, y, d / 2, d / 2):
                raise ValueError(f"{op_id}: corte circular demasiado cerca del borde")
            cutter = trimesh.creation.cylinder(radius=d / 2, height=depth, sections=64)
            cutter.apply_translation((x, y, z))
            out = _subtract(out, cutter, op_id)

        elif typ == "counterbore":
            through_d = _num(params.get("through_diameter_mm"))
            bore_d = _num(params.get("bore_diameter_mm"))
            bore_depth = _num(params.get("bore_depth_mm"))
            if not _fits_xy(out, x, y, bore_d / 2, bore_d / 2):
                raise ValueError(f"{op_id}: rebaje demasiado cerca del borde")
            through = trimesh.creation.cylinder(radius=through_d / 2, height=depth, sections=48)
            through.apply_translation((x, y, z))
            out = _subtract(out, through, op_id)
            target = (op.get("target") or {}).get("face", "top")
            lo_z = float(out.bounds[0][2])
            hi_z = float(out.bounds[1][2])
            shallow_h = bore_depth + 0.6
            shallow_z = (hi_z - bore_depth / 2 + 0.3) if target == "top" else (lo_z + bore_depth / 2 - 0.3)
            bore = trimesh.creation.cylinder(radius=bore_d / 2, height=shallow_h, sections=64)
            bore.apply_translation((x, y, shallow_z))
            out = _subtract(out, bore, op_id)

        elif typ == "hole_pattern":
            d = _num(params.get("diameter_mm"))
            rows = int(round(_num(params.get("rows"))))
            cols = int(round(_num(params.get("cols"))))
            sx = _num(params.get("spacing_x_mm"))
            sy = _num(params.get("spacing_y_mm"))
            total_w = (cols - 1) * sx + d
            total_h = (rows - 1) * sy + d
            if not _fits_xy(out, x, y, total_w / 2, total_h / 2):
                raise ValueError(f"{op_id}: patrón demasiado cerca del borde")
            for row in range(rows):
                for col in range(cols):
                    px = x + (col - (cols - 1) / 2) * sx
                    py = y + (row - (rows - 1) / 2) * sy
                    cutter = trimesh.creation.cylinder(radius=d / 2, height=depth, sections=36)
                    cutter.apply_translation((px, py, z))
                    out = _subtract(out, cutter, op_id)

        elif typ == "vesa_pattern":
            pitch = _num(params.get("pitch_mm"))
            d = _num(params.get("diameter_mm"))
            half = pitch / 2
            if not _fits_xy(out, x, y, half + d / 2, half + d / 2):
                raise ValueError(f"{op_id}: patrón VESA fuera de la cara")
            for dx in (-half, half):
                for dy in (-half, half):
                    cutter = trimesh.creation.cylinder(radius=d / 2, height=depth, sections=36)
                    cutter.apply_translation((x + dx, y + dy, z))
                    out = _subtract(out, cutter, op_id)

        elif typ == "vent_linear":
            count = int(round(_num(params.get("count"))))
            length = _num(params.get("length_mm"))
            width = _num(params.get("width_mm"))
            spacing = _num(params.get("spacing_mm"))
            rotation_deg = _num((op.get("placement") or {}).get("rotation_deg"), 0)
            span = (count - 1) * spacing + width
            if not _fits_xy(out, x, y, length / 2, span / 2):
                raise ValueError(f"{op_id}: ventilación fuera de la cara")
            for i in range(count):
                py = y + (i - (count - 1) / 2) * spacing
                cutter = _rotated_box(length, width, depth, rotation_deg)
                cutter.apply_translation((x, py, z))
                out = _subtract(out, cutter, op_id)

        elif typ == "vent_hex":
            rows = int(round(_num(params.get("rows"))))
            cols = int(round(_num(params.get("cols"))))
            radius = _num(params.get("radius_mm"))
            gap = _num(params.get("gap_mm"))
            pitch_x = radius * 1.75 + gap
            pitch_y = radius * 1.52 + gap
            total_w = max(radius * 2, (cols - 1) * pitch_x + radius * 2 + pitch_x / 2)
            total_h = max(radius * 2, (rows - 1) * pitch_y + radius * 2)
            if not _fits_xy(out, x, y, total_w / 2, total_h / 2):
                raise ValueError(f"{op_id}: rejilla hexagonal fuera de la cara")
            for row in range(rows):
                offset = pitch_x / 2 if row % 2 else 0
                for col in range(cols):
                    px = x + (col - (cols - 1) / 2) * pitch_x + offset
                    py = y + (row - (rows - 1) / 2) * pitch_y
                    cutter = trimesh.creation.cylinder(radius=radius, height=depth, sections=6)
                    cutter.apply_translation((px, py, z))
                    out = _subtract(out, cutter, op_id)

        elif typ == "cable_channel":
            length = _num(params.get("length_mm"))
            width = _num(params.get("width_mm"))
            rotation_deg = _num((op.get("placement") or {}).get("rotation_deg"), 0)
            if not _fits_xy(out, x, y, length / 2, width / 2):
                raise ValueError(f"{op_id}: canal demasiado cerca del borde")
            cutter = _rotated_box(length, width, depth, rotation_deg)
            cutter.apply_translation((x, y, z))
            out = _subtract(out, cutter, op_id)

        elif typ == "rib":
            length = _num(params.get("length_mm"))
            width = _num(params.get("width_mm"))
            height = _num(params.get("height_mm"))
            rotation_deg = _num((op.get("placement") or {}).get("rotation_deg"), 0)
            if not _fits_xy(out, x, y, length / 2, width / 2):
                raise ValueError(f"{op_id}: refuerzo demasiado cerca del borde")
            z_top = float(out.bounds[1][2])
            rib = _rotated_box(length, width, height, rotation_deg)
            rib.apply_translation((x, y, z_top + height / 2 - 0.25))
            out = _union(out, rib, op_id)

        elif typ == "boss":
            diameter = _num(params.get("diameter_mm"))
            height = _num(params.get("height_mm"))
            if not _fits_xy(out, x, y, diameter / 2, diameter / 2):
                raise ValueError(f"{op_id}: boss demasiado cerca del borde")
            target = (op.get("target") or {}).get("face", "top")
            lo_z = float(out.bounds[0][2])
            hi_z = float(out.bounds[1][2])
            boss = trimesh.creation.cylinder(radius=diameter / 2, height=height, sections=56)
            boss_z = (hi_z + height / 2 - 0.25) if target == "top" else (lo_z - height / 2 + 0.25)
            boss.apply_translation((x, y, boss_z))
            out = _union(out, boss, op_id)

        elif typ == "wave_ribs":
            length = _num(params.get("length_mm"))
            rib_width = _num(params.get("rib_width_mm"))
            amplitude = _num(params.get("amplitude_mm"))
            count = int(round(_num(params.get("count"))))
            spacing = _num(params.get("spacing_mm"))
            rotation_deg = _num((op.get("placement") or {}).get("rotation_deg"), 0)
            span = (count - 1) * spacing + rib_width
            if not _fits_xy(out, x, y, length / 2, span / 2):
                raise ValueError(f"{op_id}: ondulación demasiado cerca del borde")
            z_top = float(out.bounds[1][2])
            for i in range(count):
                phase = (i / max(1, count - 1)) * np.pi * 2.0
                height = max(0.8, amplitude * (0.55 + 0.45 * (np.sin(phase) + 1.0) / 2.0))
                py = y + (i - (count - 1) / 2) * spacing
                rib = _rotated_box(length, rib_width, height, rotation_deg)
                rib.apply_translation((x, py, z_top + height / 2 - 0.25))
                out = _union(out, rib, op_id)

    return out
